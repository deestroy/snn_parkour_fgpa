// Event-driven conv layer (M6): scatter unit + sweep + membrane memory,
// behind the D0020 interface. K = 1.
//
//   spk_we/spk_addr  push input spike addresses; they queue in a small FIFO
//                    (the per-layer address list of D0016) and the scatter
//                    unit drains it, one spike at a time, as they arrive
//   start            pulse: when the queue is drained and scatter is idle,
//                    run the SWEEP -- for every neuron n:
//                        (V[n], s[n]) = lif_update(V[n], I[n]);  I[n] = 0
//                    -- the one LIF update per neuron per timestep, using the
//                    SAME lif_update.v as the M2 neuron and the dense engine.
//   done             one-cycle pulse when the sweep finishes: out/v valid
//   out_addr/out_data, v_addr/v_data  registered read ports, golden order
//   clear            pulse: zero V and I (new sample)
//
// The sweep is the fixed cost of the event-driven design: NEURONS cycles per
// timestep regardless of activity (D0016). Scatter is the variable cost.
//
// Because integer addition is associative, this layer must produce exactly
// the dense engine's V and spikes from the same inputs (D0018) -- and it is
// checked against exactly the same golden traces, in the same harness
// (sim/run_ed_tb.sh c1 ed_conv_layer). Simulation only until it passes.

`default_nettype none

module ed_conv_layer #(
    parameter C_IN  = 2,  H_IN  = 34, W_IN  = 34,
    parameter C_OUT = 16, H_OUT = 17, W_OUT = 17,
    parameter K = 1,
    parameter WIDTH = 16, LEAK_SHIFT = 3,
    parameter signed [15:0] THRESHOLD = 64,
    parameter WEIGHT_FILE = "sim/vectors/conv_c1_w.hex",   // accepted for
                                                            // harness symmetry; unused
    parameter WT_FILE = "sim/vectors/ed_c1_wt.hex",         // transposed weights
    parameter BAKED_WEIGHTS = 0,   // 1: use ed_scatter_c1 (W_T inlined, for synthesis)
    // The input address list (D0016). Sized for the worst case -- every input
    // firing once in a timestep -- so it can NEVER overflow. Anything smaller
    // silently drops spikes under a burst (a 64-deep FIFO dropped 81% of
    // C1's on the first run). One BRAM for C1 (2312 x 12 bits).
    // Rounded UP to a power of two so the ring pointers wrap exactly at the
    // array end. (2312 entries with 12-bit pointers indexed past the array
    // once wr_p crossed 2312 -- sample 1, timestep 2 -- and read garbage.)
    parameter LIST_DEPTH = 1 << $clog2(C_IN * H_IN * W_IN),
    parameter IN_BITS = C_IN * H_IN * W_IN,
    parameter NEURONS = C_OUT * H_OUT * W_OUT,
    // Address FIELDS (D0020 rev 2): spk_addr = {ic, iy, ix}; the scatter
    // unit's i_addr = {oc, pos}. See ed_scatter.v header.
    parameter IC_W = (C_IN  > 1) ? $clog2(C_IN)  : 1,
    parameter IY_W = $clog2(H_IN), IX_W = $clog2(W_IN),
    parameter OC_W = (C_OUT > 1) ? $clog2(C_OUT) : 1,
    parameter POS_W = $clog2(H_OUT * W_OUT),
    parameter SPK_W = IC_W + IY_W + IX_W,
    parameter IA_W  = OC_W + POS_W
) (
    input  wire                        clk,
    input  wire                        rst,
    input  wire                        clear,
    input  wire                        spk_we,
    input  wire [SPK_W-1:0]            spk_addr,      // {ic, iy, ix}
    input  wire                        start,
    output wire                        busy,
    output reg                         done,
    input  wire [$clog2(NEURONS)-1:0]  out_addr,
    output wire                        out_data,
    input  wire [$clog2(NEURONS)-1:0]  v_addr,
    output wire signed [WIDTH-1:0]     v_data
);

    // --- the input address list (D0016): a queue that cannot overflow ------
    reg [SPK_W-1:0] fifo [0:LIST_DEPTH-1];
    reg [$clog2(LIST_DEPTH):0] wr_p, rd_p;          // one extra bit: full/empty
    wire fifo_empty = (wr_p == rd_p);
    wire fifo_full  = (wr_p[$clog2(LIST_DEPTH)] != rd_p[$clog2(LIST_DEPTH)]) &&
                      (wr_p[$clog2(LIST_DEPTH)-1:0] == rd_p[$clog2(LIST_DEPTH)-1:0]);
    always @(posedge clk) if (spk_we && !fifo_full) fifo[wr_p[$clog2(LIST_DEPTH)-1:0]] <= spk_addr;
    // fifo_full can only be reached if a producer pushes more addresses than
    // there are inputs -- a protocol violation, not a design condition.

    // --- scatter unit -----------------------------------------------------
    reg                        sc_we;
    reg  [SPK_W-1:0]           sc_addr;
    wire                       sc_busy;
    reg  [IA_W-1:0]            i_addr;      // {oc, pos} of neuron n
    wire signed [WIDTH-1:0]    i_rdata;
    reg                        i_we;
    reg  signed [WIDTH-1:0]    i_wdata;
    reg                        sc_clear;

    generate if (BAKED_WEIGHTS) begin : g_baked
        ed_scatter_c1 #(
            .C_IN(C_IN), .H_IN(H_IN), .W_IN(W_IN),
            .C_OUT(C_OUT), .H_OUT(H_OUT), .W_OUT(W_OUT),
            .K(K), .WIDTH(WIDTH)
        ) scatter (
            .clk(clk), .rst(rst), .clear(sc_clear),
            .spk_we(sc_we), .spk_addr(sc_addr), .busy(sc_busy),
            .i_addr(i_addr), .i_rdata(i_rdata), .i_we(i_we), .i_wdata(i_wdata)
        );
    end else begin : g_file
        ed_scatter #(
            .C_IN(C_IN), .H_IN(H_IN), .W_IN(W_IN),
            .C_OUT(C_OUT), .H_OUT(H_OUT), .W_OUT(W_OUT),
            .K(K), .WIDTH(WIDTH), .WT_FILE(WT_FILE)
        ) scatter (
            .clk(clk), .rst(rst), .clear(sc_clear),
            .spk_we(sc_we), .spk_addr(sc_addr), .busy(sc_busy),
            .i_addr(i_addr), .i_rdata(i_rdata), .i_we(i_we), .i_wdata(i_wdata)
        );
    end endgenerate

    // --- membrane memory + output spikes ---------------------------------
    reg signed [WIDTH-1:0] vmem [0:NEURONS-1];
    reg                    out_mem [0:NEURONS-1];
    reg                    out_data_r;
    reg signed [WIDTH-1:0] v_data_r;
    always @(posedge clk) begin
        out_data_r <= out_mem[out_addr];
        v_data_r   <= vmem[v_addr];
    end
    assign out_data = out_data_r;
    assign v_data   = v_data_r;

    // the shared LIF rule (D0019: V from vmem, I from the scatter unit)
    // v_r / i_rdata are block-RAM output latches (2.5 ns clock-to-out); the
    // LIF chain fed straight from them was 0.42 ns over a 10 ns clock
    // (2026-08-19). v_r2 / i_r2 are plain flip-flops captured in the wait
    // state that already exists, so the LIF logic starts from a fast source
    // and the sweep's cycle timing is unchanged.
    reg  signed [WIDTH-1:0] v_r, v_r2, i_r2;
    wire signed [WIDTH-1:0] v_next;
    wire                    spike_next;
    lif_update #(.WIDTH(WIDTH), .LEAK_SHIFT(LEAK_SHIFT), .THRESHOLD(THRESHOLD)) update (
        .v_in(v_r2), .current_in(i_r2), .v_out(v_next), .spike(spike_next)
    );

    // --- control FSM ------------------------------------------------------
    localparam S_IDLE = 0, S_FEED = 1, S_SW_ZERO = 2, S_CLR = 3, S_CLRW = 4,
               S_SW_RD = 5, S_SW_WAIT = 6, S_SW_UPD = 7;
    reg [2:0] state;
    integer n;                    // sweep index (flat, for vmem/out_mem)
    reg [OC_W-1:0]  sw_oc;        // the same index as fields, for i_addr
    reg [POS_W-1:0] sw_pos;
    reg             up_valid;     // pipeline: an update is in flight
    integer         n_up;         // the neuron being updated (= read-1)
    reg start_pend;               // start seen while draining

    assign busy = (state != S_IDLE) || sc_busy || !fifo_empty;

    always @(posedge clk) begin
        done <= 1'b0; sc_we <= 1'b0; i_we <= 1'b0; sc_clear <= 1'b0;
        if (rst) begin
            state <= S_IDLE; wr_p <= 0; rd_p <= 0; start_pend <= 1'b0;
        end else begin
            if (spk_we && !fifo_full) wr_p <= wr_p + 1;
            if (start) start_pend <= 1'b1;

            case (state)
            S_IDLE: begin
                if (clear) begin
                    sc_clear <= 1'b1; n <= 0; state <= S_CLR;
                end else if (!fifo_empty && !sc_busy) begin
                    // hand the next queued spike to the scatter unit
                    sc_we <= 1'b1; sc_addr <= fifo[rd_p[$clog2(LIST_DEPTH)-1:0]];
                    rd_p <= rd_p + 1;
                    state <= S_FEED;
                end else if (start_pend && fifo_empty && !sc_busy) begin
                    start_pend <= 1'b0; n <= 0; sw_oc <= 0; sw_pos <= 0;
                    i_addr <= 0;                      // neuron 0's I read starts now
                    up_valid <= 1'b0;
                    state <= S_SW_RD;
                end
            end

            S_FEED: state <= S_IDLE;     // scatter has taken it; back to the pump

            S_CLR: begin                 // zero V and out; scatter zeroes I itself
                vmem[n] <= 0; out_mem[n] <= 1'b0;
                if (n == NEURONS-1) state <= S_CLRW; else n <= n + 1;
            end
            S_CLRW: if (!sc_busy) begin state <= S_IDLE; done <= 1'b1; end

            // --- the PIPELINED sweep (C0030): TWO cycles per neuron. Beat A
            //     presents neuron n_rd's addresses (vmem latch + bank latch
            //     capture at the A->B edge) and, from the second beat on,
            //     simultaneously UPDATES neuron n_rd-1 (write vmem/out, zero
            //     its I through the banks' separate write port). Beat B
            //     re-registers the latches into fabric FFs for the LIF chain.
            //     Reads and writes always target different neurons, so the
            //     one-read-one-write port discipline holds per memory.
            S_SW_RD: begin                          // beat A
                v_r <= vmem[n];                     // latch neuron n_rd
                if (up_valid) begin
                    vmem[n_up]    <= v_next;        // update neuron n_rd-1
                    out_mem[n_up] <= spike_next;
                    i_we <= 1'b1; i_wdata <= 0;     // zero I[n_rd] AT THE READ
                    // edge: the bank is read-first, so the latch captures
                    // I[n_rd] and the same edge clears it -- each neuron's I
                    // is zeroed when read, one beat before its update, and
                    // nothing else writes I during the sweep (scatter idle).
                end
                state <= S_SW_WAIT;
            end
            S_SW_WAIT: begin                        // beat B
                v_r2 <= v_r; i_r2 <= i_rdata;       // fast sources for the LIF
                up_valid <= 1'b1; n_up <= n;
                if (n == NEURONS-1) begin
                    state <= S_SW_UPD;              // epilogue: last update only
                end else begin
                    n <= n + 1;
                    if (sw_pos == H_OUT*W_OUT-1) begin
                        sw_pos <= 0; sw_oc <= sw_oc + 1;
                        i_addr <= {sw_oc + 1'b1, {POS_W{1'b0}}};
                    end else begin
                        sw_pos <= sw_pos + 1;
                        i_addr <= {sw_oc, sw_pos + 1'b1};
                    end
                    state <= S_SW_RD;
                end
            end
            S_SW_UPD: begin                         // epilogue beat A (no new read)
                vmem[n_up]    <= v_next;
                out_mem[n_up] <= spike_next;
                i_we <= 1'b1; i_wdata <= 0;
                up_valid <= 1'b0;
                state <= S_SW_ZERO;
            end
            S_SW_ZERO: begin                        // final zero lands; done
                state <= S_IDLE; done <= 1'b1;
            end
            endcase
        end
    end

endmodule

`default_nettype wire
