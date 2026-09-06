// Dense (clock-driven) spiking conv layer, P-WIDE (C0029): the fair dense
// baseline. Identical walk to conv_layer.v, but P output channels advance
// together: for a fixed tap (ic,ky,kx) the INPUT BIT is the same for every
// output channel -- only the weight differs -- so one input read feeds P
// weight reads and P accumulators per cycle. Weights and membranes are
// banked by oc mod P, exactly the partition ed_scatter uses for K (D0017),
// so the comparison at P == K is matched-parallelism by construction.
//
// P=1 must equal conv_layer.v cycle-for-cycle and bit-for-bit; the same
// harness verifies both. Sign-off rules applied from the start: one write
// + one read port per bank, stepped/sliced addresses, membrane read issued
// early and re-registered, use_dsp = "no".
//
// UNVERIFIED until sim/run_conv_p_tb.sh passes bit-identical.

`default_nettype none

(* use_dsp = "no" *)
module conv_layer_p #(
    parameter C_IN  = 2,  H_IN  = 34, W_IN  = 34,
    parameter C_OUT = 16, H_OUT = 17, W_OUT = 17,
    parameter P = 4,                  // output channels in parallel; divides C_OUT
    parameter WIDTH = 16, LEAK_SHIFT = 3,
    parameter signed [15:0] THRESHOLD = 64,
    parameter WEIGHT_FILE = "sim/vectors/conv_c1_w.hex",
    parameter IN_BITS  = C_IN * H_IN * W_IN,
    parameter NEURONS  = C_OUT * H_OUT * W_OUT,
    parameter TAPS     = C_IN * 9,
    parameter GB       = C_OUT / P    // channel groups
) (
    input  wire        clk,
    input  wire        rst,
    input  wire        clear,
    input  wire        start,
    output reg         busy,
    output reg         done,

    // word-parallel input load (C0035): one 32-bit word per cycle
    input  wire                        in_w_we,
    input  wire [$clog2((IN_BITS+31)/32)-1:0] in_w_addr,
    input  wire [31:0]                 in_w_data,

    input  wire [$clog2(NEURONS)-1:0]  out_addr, // golden flat order (legacy bit port)
    output wire                        out_data,
    // word-parallel output read (C0035)
    input  wire [$clog2((NEURONS+31)/32)-1:0] out_w_addr,
    output reg  [31:0]                 out_w_data,
    input  wire [$clog2(NEURONS)-1:0]  v_addr,
    output wire signed [WIDTH-1:0]     v_data
);

    // --- input spike buffer: WORD-organised (C0035). The wrapper writes a
    //     whole word per accepted beat; the engine reads one bit per cycle
    //     through a word latch + registered bit select (same one-cycle
    //     contract as the old bit RAM: issue address, consume next cycle).
    localparam WORDS_IN = (IN_BITS + 31) / 32;
    reg [31:0] in_words [0:WORDS_IN-1];
    always @(posedge clk) if (in_w_we) in_words[in_w_addr] <= in_w_data;
    reg [31:0] in_word_q;
    reg [4:0]  in_bit_sel;
    reg        in_bounds_q;

    // --- weight banks: bank p holds channels oc == p (mod P), consecutive
    //     within the bank at offset ((oc/P)*C_IN + ic)*9 + (ky*3 + kx).
    //     Loaded from the same golden hex by re-indexing at init.
    localparam WB_N = GB * TAPS;              // words per bank
    reg signed [7:0] wrom_all [0:C_OUT*TAPS-1];
    initial $readmemh(WEIGHT_FILE, wrom_all);

    // --- membrane / output banks: neuron (oc,oy,ox) -> bank oc mod P,
    //     offset ((oc/P)*H_OUT + oy)*W_OUT + ox (the D0017 partition)
    localparam BN = NEURONS / P;
    localparam AB = $clog2(BN);
    localparam HW = H_OUT * W_OUT;

    // FSM ------------------------------------------------------------------
    localparam S_IDLE = 0, S_CLEAR = 1, S_MAC = 2, S_TAIL = 3,
               S_VRD = 4, S_VREG = 5, S_UPDATE = 6;
    reg [2:0] state;
    reg prime;
    integer og, oy, ox;         // channel GROUP + position of the P neurons
    integer ic, ky, kx;
    integer clr;
    integer j;

    // stepped addresses (never formulas into memories) ---------------------
    integer in_a, wb_a, wb;     // input addr, weight offset in bank, window base
    reg [AB-1:0] n_off;         // bank offset of the current P-neuron group
    wire signed [31:0] iy = 2*oy + ky - 1;
    wire signed [31:0] ix = 2*ox + kx - 1;
    wire in_bounds = (iy >= 0) && (iy < H_IN) && (ix >= 0) && (ix < W_IN);

    wire in_bit_r = in_bounds_q ? in_word_q[in_bit_sel] : 1'b0;
    reg signed [7:0]       w_r [0:P-1];
    reg signed [WIDTH-1:0] acc [0:P-1];

    // banked memories: ONE write + ONE read port each ----------------------
    wire we_upd = (state == S_UPDATE);
    wire we_clr = (state == S_CLEAR);
    wire [AB-1:0] mem_waddr = we_clr ? clr[AB-1:0] : n_off;
    // external reads use the golden flat address, translated by slices:
    // flat = (oc*H_OUT+oy)*W_OUT+ox; oc = flat / HW (a constant divide kept
    // OFF the datapath: it feeds only the external read port, registered)
    wire [31:0] x_oc_o = out_addr / HW;
    wire [31:0] x_off_o = (x_oc_o / P) * HW + (out_addr % HW);
    wire [31:0] x_oc_v = v_addr / HW;
    wire [31:0] x_off_v = (x_oc_v / P) * HW + (v_addr % HW);
    reg [31:0] x_bank_o_r, x_bank_v_r;
    always @(posedge clk) begin
        x_bank_o_r <= x_oc_o % P;
        x_bank_v_r <= x_oc_v % P;
    end

    wire signed [WIDTH-1:0] v_next [0:P-1];
    wire                    spike_next [0:P-1];
    wire [P*WIDTH-1:0] v_flat;
    wire [P-1:0]       s_flat;
    // C0035 rev 2: spikes ALSO land in a PER-BANK flop bit file (obits,
    // inside g_bank), written at the same address as vmem/smem -- ONE
    // writer per bank. The first version was a single global word file
    // with P concurrent bit writes: legal on flops, but each of ~NEURONS
    // flops needed P address comparators and dense P=4 failed timing at
    // WNS -3.2 on exactly those write cones (2026-09-06 impl log). The
    // word read port below is pure constant wiring computed at
    // elaboration: bit (w,b) of the flat golden order lives at a
    // compile-time-known (bank, offset).
    localparam WORDS_OUT = (NEURONS + 31) / 32;
    wire [31:0] word_bits [0:WORDS_OUT-1];
    always @(posedge clk) out_w_data <= word_bits[out_w_addr];

    genvar g;
    generate for (g = 0; g < P; g = g + 1) begin : g_bank
        reg signed [WIDTH-1:0] vmem [0:BN-1];
        reg                    smem [0:BN-1];
        reg [BN-1:0]           obits;   // this bank's spikes, one flop each
        reg signed [WIDTH-1:0] v_lat, v_r2;
        reg                    s_lat;
        // per-bank weights, re-indexed from the shared hex at time zero
        reg signed [7:0] wrom [0:WB_N-1];
        integer gi, ti;
        initial begin
            #0;
            for (gi = 0; gi < GB; gi = gi + 1)
                for (ti = 0; ti < TAPS; ti = ti + 1)
                    wrom[gi*TAPS + ti] = wrom_all[((gi*P + g)*TAPS) + ti];
        end
        always @(posedge clk) begin
            w_r[g] <= wrom[wb_a];
            if (we_upd || we_clr) begin
                vmem[mem_waddr] <= we_clr ? {WIDTH{1'b0}} : v_next[g];
                smem[mem_waddr] <= we_clr ? 1'b0 : spike_next[g];
                obits[mem_waddr] <= we_clr ? 1'b0 : spike_next[g];
            end
            v_lat <= vmem[(state == S_TAIL || state == S_VRD) ? n_off : x_off_v[AB-1:0]];
            v_r2  <= v_lat;
            s_lat <= smem[x_off_o[AB-1:0]];
        end
        assign v_flat[g*WIDTH +: WIDTH] = v_lat;   // 1-cycle external read
        assign s_flat[g] = s_lat;
        lif_update #(.WIDTH(WIDTH), .LEAK_SHIFT(LEAK_SHIFT), .THRESHOLD(THRESHOLD)) upd (
            .v_in(v_r2), .current_in(acc[g]), .v_out(v_next[g]), .spike(spike_next[g])
        );
    end endgenerate

    // external reads keep conv_layer's 1-cycle contract: the bank latch is
    // the register; the bank select (x_bank_*_r, captured the same edge)
    // is combinational after it. External ports are exercised only when
    // the engine is idle (testbench / wrapper readout), never during MAC.
    localparam PB = (P > 1) ? $clog2(P) : 1;   // P=1: bank index is constant 0
    wire [PB-1:0] sel_o = (P > 1) ? x_bank_o_r[PB-1:0] : {PB{1'b0}};
    wire [PB-1:0] sel_v = (P > 1) ? x_bank_v_r[PB-1:0] : {PB{1'b0}};
    assign out_data = s_flat[sel_o];
    assign v_data   = v_flat[sel_v*WIDTH +: WIDTH];

    // word gather: golden flat bit gw*32+gb2 -> (bank, offset), all indices
    // compile-time constants (the / and % below are elaboration-only) ------
    genvar gw, gb2;
    generate for (gw = 0; gw < WORDS_OUT; gw = gw + 1) begin : g_ow
        for (gb2 = 0; gb2 < 32; gb2 = gb2 + 1) begin : g_ob
            if (gw*32 + gb2 < NEURONS) begin : g_in
                localparam integer FLAT  = gw*32 + gb2;
                localparam integer OC    = FLAT / HW;
                localparam integer LANE  = OC % P;
                localparam integer LOCAL = (OC / P) * HW + (FLAT % HW);
                assign word_bits[gw][gb2] = g_bank[LANE].obits[LOCAL];
            end else begin : g_pad
                assign word_bits[gw][gb2] = 1'b0;   // padding past NEURONS
            end
        end
    end endgenerate

    always @(posedge clk) begin
        done <= 1'b0;
        if (rst) begin
            state <= S_IDLE; busy <= 1'b0;
        end else case (state)

        S_IDLE: begin
            busy <= 1'b0;
            if (clear) begin
                clr <= 0; busy <= 1'b1; state <= S_CLEAR;
            end else if (start) begin
                og <= 0; oy <= 0; ox <= 0;
                ic <= 0; ky <= 0; kx <= 0;
                for (j = 0; j < P; j = j + 1) acc[j] <= 0;
                prime <= 1'b1;
                n_off <= 0; wb_a <= 0; wb <= -(W_IN + 1); in_a <= -(W_IN + 1);
                busy <= 1'b1; state <= S_MAC;
            end
        end

        S_CLEAR: begin  // banks clear vmem/smem/obits at mem_waddr = clr
            if (clr == BN-1) begin state <= S_IDLE; done <= 1'b1; end
            else clr <= clr + 1;
        end

        S_MAC: begin  // one input bit + P weights per cycle
            in_word_q  <= in_words[in_a[31:5]];
            in_bit_sel <= in_a[4:0];
            in_bounds_q <= in_bounds;
            if (!prime && in_bit_r)
                for (j = 0; j < P; j = j + 1)
                    acc[j] <= acc[j] + {{(WIDTH-8){w_r[j][7]}}, w_r[j]};
            prime <= 1'b0;
            wb_a <= wb_a + 1;
            if (kx != 2) begin kx <= kx + 1; in_a <= in_a + 1; end
            else begin kx <= 0;
                if (ky != 2) begin ky <= ky + 1; in_a <= in_a + (W_IN - 2); end
                else begin ky <= 0;
                    if (ic != C_IN-1) begin
                        ic <= ic + 1; in_a <= in_a + (H_IN*W_IN - 2*W_IN - 2);
                    end else begin ic <= 0; state <= S_TAIL; end
                end
            end
        end

        S_TAIL: begin  // consume the last read; banks issue the vmem read (n_off)
            if (in_bit_r)
                for (j = 0; j < P; j = j + 1)
                    acc[j] <= acc[j] + {{(WIDTH-8){w_r[j][7]}}, w_r[j]};
            state <= S_VRD;
        end

        S_VRD:  state <= S_VREG;   // v_lat valid
        S_VREG: state <= S_UPDATE; // v_r2 valid (fabric FF feeds the LIF)

        S_UPDATE: begin            // P banks each write their neuron (we_upd);
                                   // obits takes the spike at the same address
            for (j = 0; j < P; j = j + 1) acc[j] <= 0;
            prime <= 1'b1;
            if (ox != W_OUT-1) begin
                ox <= ox + 1; wb <= wb + 2; in_a <= wb + 2;
                n_off <= n_off + 1;
                wb_a <= og * TAPS;
            end else begin ox <= 0;
                if (oy != H_OUT-1) begin
                    oy <= oy + 1;
                    wb <= wb + (2*W_IN - 2*(W_OUT-1)); in_a <= wb + (2*W_IN - 2*(W_OUT-1));
                    n_off <= n_off + 1;
                    wb_a <= og * TAPS;
                end else begin oy <= 0;
                    if (og != GB-1) begin
                        og <= og + 1;
                        wb <= -(W_IN + 1); in_a <= -(W_IN + 1);
                        n_off <= n_off + 1;
                        wb_a <= (og + 1) * TAPS;
                    end else begin state <= S_IDLE; done <= 1'b1; end
                end
            end
            if (!(ox == W_OUT-1 && oy == H_OUT-1 && og == GB-1))
                state <= S_MAC;
        end

        endcase
    end

endmodule

`default_nettype wire
