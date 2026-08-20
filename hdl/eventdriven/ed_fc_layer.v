// Event-driven FC layer (D0023): queue + scatter + sweep in one module,
// with the 2x2 sum-pool folded in exactly as the dense fc_layer folds it.
//
// A spike at (c, y, x) with y<4 and x<4 belongs to pool window
// j = (c*2 + y/2)*2 + x/2 and adds the weight COLUMN W[., j] into the
// accumulator of EVERY output neuron -- uniform fan-out, no window logic.
// Spikes at y==4 or x==4 fall outside the floor-cropped pool and are
// dropped AT ENQUEUE (they contribute nothing; the queue holds only work).
// The pool's /4 lives in THRESHOLD = 256 (D0004/D0013), so no division.
//
//   per spike:   for n = 0, K, 2K, ...:  I[n..n+K-1] += W_T[j][n..n+K-1]
//   on start (queue drained): sweep n = 0..N_OUT-1:
//       (V, s) = lif_update(V[n], I[n]);  I[n] = 0
//
// Banking as D0017: neuron n lives in bank n mod K at offset n / K
// (bit-slices; K a power of two dividing N_OUT); a spike walks n in steps
// of K, so the K read-modify-writes per cycle are conflict-free by
// construction. Each bank has ONE write port and ONE read port; addresses
// are stepped registers; the sweep re-registers V and I before the LIF
// chain; use_dsp = "no". These are the sign-off rules learned on the conv
// engine (decisions log, 2026-08-18/19), applied from the start.
//
// Interface: D0020 (spk_addr carries FIELDS {c, y, x}). Simulation only;
// weights via $readmemh (no baked variant until a board target needs one).
// UNVERIFIED until sim/run_ed_fc_tb.sh passes bit-identical.

`default_nettype none

(* use_dsp = "no" *)
module ed_fc_layer #(
    parameter C_IN = 64, H_IN = 5, W_IN = 5,
    parameter N_OUT = 128,
    parameter K = 4,
    parameter WIDTH = 16, LEAK_SHIFT = 3,
    parameter signed [15:0] THRESHOLD = 256,
    parameter WT_FILE = "sim/vectors/ed_fc_wt.hex",   // W_T[j][n], j-major
    parameter IN_BITS = C_IN * H_IN * W_IN,
    parameter N_POOL  = C_IN * 4,
    // fields (D0020 rev 2): spk_addr = {c, y, x}
    parameter C_W = $clog2(C_IN), Y_W = $clog2(H_IN), X_W = $clog2(W_IN),
    parameter SPK_W = C_W + Y_W + X_W,
    parameter LIST_DEPTH = 1 << $clog2(IN_BITS),      // worst case, D0016
    parameter BANK_N = N_OUT / K
) (
    input  wire                       clk,
    input  wire                       rst,
    input  wire                       clear,
    input  wire                       spk_we,
    input  wire [SPK_W-1:0]           spk_addr,     // {c, y, x}
    input  wire                       start,
    output wire                       busy,
    output reg                        done,
    input  wire [$clog2(N_OUT)-1:0]   out_addr,
    output wire                       out_data,
    input  wire [$clog2(N_OUT)-1:0]   v_addr,
    output wire signed [WIDTH-1:0]    v_data
);

    // --- weights: W_T[j*N_OUT + n], so a spike's column is consecutive ---
    reg signed [7:0] wt [0:N_POOL*N_OUT-1];
    initial $readmemh(WT_FILE, wt);

    // --- enqueue: drop cropped positions (y==4 or x==4) at the door ------
    wire [C_W-1:0] e_c = spk_addr[SPK_W-1 -: C_W];
    wire [Y_W-1:0] e_y = spk_addr[X_W +: Y_W];
    wire [X_W-1:0] e_x = spk_addr[X_W-1:0];
    wire e_keep = (e_y < H_IN-1) && (e_x < W_IN-1);   // floor crop (4 -> out)
    // stored entry: the pool window j = {c, y[1], x[1]}, precomputed by slicing
    wire [$clog2(N_POOL)-1:0] e_j = {e_c, e_y[1], e_x[1]};

    reg [$clog2(N_POOL)-1:0] fifo [0:LIST_DEPTH-1];
    reg [$clog2(LIST_DEPTH):0] wr_p, rd_p;
    wire fifo_empty = (wr_p == rd_p);
    wire fifo_full  = (wr_p[$clog2(LIST_DEPTH)] != rd_p[$clog2(LIST_DEPTH)]) &&
                      (wr_p[$clog2(LIST_DEPTH)-1:0] == rd_p[$clog2(LIST_DEPTH)-1:0]);
    always @(posedge clk)
        if (spk_we && e_keep && !fifo_full)
            fifo[wr_p[$clog2(LIST_DEPTH)-1:0]] <= e_j;

    // --- membrane + output memories (sweep side) --------------------------
    reg signed [WIDTH-1:0] vmem [0:N_OUT-1];
    reg                    out_mem [0:N_OUT-1];
    reg                    out_data_r;
    reg signed [WIDTH-1:0] v_data_r;
    always @(posedge clk) begin
        out_data_r <= out_mem[out_addr];
        v_data_r   <= vmem[v_addr];
    end
    assign out_data = out_data_r;
    assign v_data   = v_data_r;

    // --- FSM ---------------------------------------------------------------
    localparam S_IDLE = 0, S_RD = 1, S_ADD = 2, S_CLR = 3,
               S_SW_RD = 4, S_SW_WAIT = 5, S_SW_UPD = 6, S_SW_ZERO = 7;
    reg [2:0] state;
    reg start_pend;
    integer n;                                     // scatter/sweep neuron index
    reg [$clog2(N_POOL*N_OUT)-1:0] wrow;           // = j*N_OUT + n, stepped
    reg signed [7:0] w_r [0:K-1];
    integer clr, kk;

    assign busy = (state != S_IDLE) || !fifo_empty;

    // --- K accumulator banks: one write + one read port each --------------
    localparam AB = $clog2(BANK_N);
    // scatter: read/write offset n/K; sweep: neuron sw_n -> bank sw_n%K.
    reg  [AB-1:0] off_r, off_hold;
    reg  [$clog2(N_OUT)-1:0] sw_n;
    wire we_add = (state == S_ADD);
    wire we_clr = (state == S_CLR);
    wire we_swz = (state == S_SW_ZERO);            // sweep zeroes I[sw_n]
    wire [AB-1:0] waddr = we_add ? off_hold : we_clr ? clr[AB-1:0]
                                            : sw_n[$clog2(N_OUT)-1:$clog2(K)];
    wire [AB-1:0] raddr = (state == S_SW_RD) ? sw_n[$clog2(N_OUT)-1:$clog2(K)]
                                             : off_r;
    wire [K*WIDTH-1:0] rd_flat;
    genvar g;
    generate for (g = 0; g < K; g = g + 1) begin : g_bank
        reg signed [WIDTH-1:0] mem [0:BANK_N-1];
        reg signed [WIDTH-1:0] rd_q;
        wire we = we_add || we_clr ||
                  (we_swz && sw_n[$clog2(K)-1:0] == g[$clog2(K)-1:0]);
        wire signed [WIDTH-1:0] wdata =
            we_add ? rd_q + {{(WIDTH-8){w_r[g][7]}}, w_r[g]} : {WIDTH{1'b0}};
        always @(posedge clk) begin
            if (we) mem[waddr] <= wdata;
            rd_q <= mem[raddr];
        end
        assign rd_flat[g*WIDTH +: WIDTH] = rd_q;
    end endgenerate

    // sweep-side registered I read: bank select AFTER the bank's own register
    reg [$clog2(K)-1:0] sw_bank_r;
    always @(posedge clk) sw_bank_r <= sw_n[$clog2(K)-1:0];
    wire signed [WIDTH-1:0] i_rd = rd_flat[sw_bank_r*WIDTH +: WIDTH];

    // the shared LIF rule, fed from re-registered fabric FFs (v_r2/i_r2)
    reg signed [WIDTH-1:0] v_r, v_r2, i_r2;
    wire signed [WIDTH-1:0] v_next;
    wire                    spike_next;
    lif_update #(.WIDTH(WIDTH), .LEAK_SHIFT(LEAK_SHIFT), .THRESHOLD(THRESHOLD)) update (
        .v_in(v_r2), .current_in(i_r2), .v_out(v_next), .spike(spike_next)
    );

    always @(posedge clk) begin
        done <= 1'b0;
        if (rst) begin
            state <= S_IDLE; wr_p <= 0; rd_p <= 0; start_pend <= 1'b0;
        end else begin
            if (spk_we && e_keep && !fifo_full) wr_p <= wr_p + 1;
            if (start) start_pend <= 1'b1;

            case (state)
            S_IDLE: begin
                if (clear) begin
                    clr <= 0; n <= 0; state <= S_CLR;
                end else if (!fifo_empty) begin
                    rd_p <= rd_p + 1;
                    n <= 0; off_r <= 0;
                    wrow <= fifo[rd_p[$clog2(LIST_DEPTH)-1:0]] * N_OUT;
                    state <= S_RD;
                end else if (start_pend) begin
                    start_pend <= 1'b0; sw_n <= 0; state <= S_SW_RD;
                end
            end

            S_CLR: begin                       // zero V, out; banks zero I (we_clr).
                                               // BANK_N <= N_OUT, so running clr to
                                               // N_OUT-1 covers both (bank offset
                                               // wraps and rewrites zeros: harmless)
                vmem[clr] <= 0; out_mem[clr] <= 1'b0;
                if (clr == N_OUT-1) begin state <= S_IDLE; done <= 1'b1; end
                else clr <= clr + 1;
            end

            S_RD: begin                        // banks read off_r; fetch K weights
                for (kk = 0; kk < K; kk = kk + 1)
                    w_r[kk] <= wt[wrow + kk];
                off_hold <= off_r;
                state <= S_ADD;
            end
            S_ADD: begin                       // K RMWs land (we_add)
                if (n + K < N_OUT) begin
                    n <= n + K; off_r <= off_r + 1; wrow <= wrow + K;
                    state <= S_RD;
                end else state <= S_IDLE;      // next spike or sweep
            end

            S_SW_RD: begin                     // vmem latch + bank latch load
                v_r <= vmem[sw_n];
                state <= S_SW_WAIT;
            end
            S_SW_WAIT: begin                   // re-register into fabric FFs
                v_r2 <= v_r; i_r2 <= i_rd;
                state <= S_SW_UPD;
            end
            S_SW_UPD: begin
                vmem[sw_n]    <= v_next;
                out_mem[sw_n] <= spike_next;
                state <= S_SW_ZERO;            // bank zeroes I[sw_n] (we_swz)
            end
            S_SW_ZERO: begin
                if (sw_n == N_OUT-1) begin state <= S_IDLE; done <= 1'b1; end
                else begin sw_n <= sw_n + 1; state <= S_SW_RD; end
            end
            endcase
        end
    end

endmodule

`default_nettype wire
