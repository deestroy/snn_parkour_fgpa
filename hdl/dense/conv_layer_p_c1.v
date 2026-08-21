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
module conv_layer_p_c1 #(
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
    // BAKED weights (c1), inlined -- no $readmemh for Vivado to lose
    initial begin
        wrom_all[0] = 8'hf7;
        wrom_all[1] = 8'h10;
        wrom_all[2] = 8'hd8;
        wrom_all[3] = 8'hcf;
        wrom_all[4] = 8'he6;
        wrom_all[5] = 8'h26;
        wrom_all[6] = 8'h07;
        wrom_all[7] = 8'h38;
        wrom_all[8] = 8'h16;
        wrom_all[9] = 8'h06;
        wrom_all[10] = 8'hfd;
        wrom_all[11] = 8'hfb;
        wrom_all[12] = 8'hb8;
        wrom_all[13] = 8'hd9;
        wrom_all[14] = 8'hdf;
        wrom_all[15] = 8'h0e;
        wrom_all[16] = 8'h26;
        wrom_all[17] = 8'h2a;
        wrom_all[18] = 8'hdf;
        wrom_all[19] = 8'h01;
        wrom_all[20] = 8'h22;
        wrom_all[21] = 8'h2f;
        wrom_all[22] = 8'h08;
        wrom_all[23] = 8'h3b;
        wrom_all[24] = 8'hf2;
        wrom_all[25] = 8'h19;
        wrom_all[26] = 8'h40;
        wrom_all[27] = 8'hd2;
        wrom_all[28] = 8'hf3;
        wrom_all[29] = 8'hf8;
        wrom_all[30] = 8'he9;
        wrom_all[31] = 8'h29;
        wrom_all[32] = 8'hd9;
        wrom_all[33] = 8'hde;
        wrom_all[34] = 8'hc8;
        wrom_all[35] = 8'h9d;
        wrom_all[36] = 8'hea;
        wrom_all[37] = 8'h41;
        wrom_all[38] = 8'h19;
        wrom_all[39] = 8'h28;
        wrom_all[40] = 8'h01;
        wrom_all[41] = 8'he5;
        wrom_all[42] = 8'h05;
        wrom_all[43] = 8'hc2;
        wrom_all[44] = 8'hd1;
        wrom_all[45] = 8'he0;
        wrom_all[46] = 8'h21;
        wrom_all[47] = 8'h1c;
        wrom_all[48] = 8'hee;
        wrom_all[49] = 8'h05;
        wrom_all[50] = 8'h31;
        wrom_all[51] = 8'h2f;
        wrom_all[52] = 8'h11;
        wrom_all[53] = 8'h0e;
        wrom_all[54] = 8'h1b;
        wrom_all[55] = 8'hd9;
        wrom_all[56] = 8'h02;
        wrom_all[57] = 8'hc9;
        wrom_all[58] = 8'hc9;
        wrom_all[59] = 8'hc1;
        wrom_all[60] = 8'h1e;
        wrom_all[61] = 8'h0c;
        wrom_all[62] = 8'hcd;
        wrom_all[63] = 8'h1e;
        wrom_all[64] = 8'h25;
        wrom_all[65] = 8'hf8;
        wrom_all[66] = 8'h14;
        wrom_all[67] = 8'h15;
        wrom_all[68] = 8'h24;
        wrom_all[69] = 8'h3b;
        wrom_all[70] = 8'hdb;
        wrom_all[71] = 8'hee;
        wrom_all[72] = 8'h1a;
        wrom_all[73] = 8'h4c;
        wrom_all[74] = 8'h42;
        wrom_all[75] = 8'h3e;
        wrom_all[76] = 8'h1d;
        wrom_all[77] = 8'hd9;
        wrom_all[78] = 8'hf5;
        wrom_all[79] = 8'hdc;
        wrom_all[80] = 8'hc9;
        wrom_all[81] = 8'h32;
        wrom_all[82] = 8'h30;
        wrom_all[83] = 8'hd1;
        wrom_all[84] = 8'h0e;
        wrom_all[85] = 8'hfe;
        wrom_all[86] = 8'h02;
        wrom_all[87] = 8'he6;
        wrom_all[88] = 8'h14;
        wrom_all[89] = 8'hdf;
        wrom_all[90] = 8'h1e;
        wrom_all[91] = 8'h31;
        wrom_all[92] = 8'h33;
        wrom_all[93] = 8'h1a;
        wrom_all[94] = 8'hdf;
        wrom_all[95] = 8'hdc;
        wrom_all[96] = 8'h28;
        wrom_all[97] = 8'h0e;
        wrom_all[98] = 8'hd3;
        wrom_all[99] = 8'he2;
        wrom_all[100] = 8'h40;
        wrom_all[101] = 8'h34;
        wrom_all[102] = 8'hdc;
        wrom_all[103] = 8'he3;
        wrom_all[104] = 8'hae;
        wrom_all[105] = 8'hfe;
        wrom_all[106] = 8'hb5;
        wrom_all[107] = 8'he7;
        wrom_all[108] = 8'h06;
        wrom_all[109] = 8'h17;
        wrom_all[110] = 8'hed;
        wrom_all[111] = 8'h2d;
        wrom_all[112] = 8'hf5;
        wrom_all[113] = 8'h2d;
        wrom_all[114] = 8'h33;
        wrom_all[115] = 8'hdf;
        wrom_all[116] = 8'he7;
        wrom_all[117] = 8'h18;
        wrom_all[118] = 8'h09;
        wrom_all[119] = 8'h05;
        wrom_all[120] = 8'h27;
        wrom_all[121] = 8'hfa;
        wrom_all[122] = 8'hcf;
        wrom_all[123] = 8'h24;
        wrom_all[124] = 8'hb9;
        wrom_all[125] = 8'hb3;
        wrom_all[126] = 8'hee;
        wrom_all[127] = 8'hd4;
        wrom_all[128] = 8'hda;
        wrom_all[129] = 8'hd5;
        wrom_all[130] = 8'hea;
        wrom_all[131] = 8'hff;
        wrom_all[132] = 8'he1;
        wrom_all[133] = 8'hfc;
        wrom_all[134] = 8'h27;
        wrom_all[135] = 8'hfd;
        wrom_all[136] = 8'h05;
        wrom_all[137] = 8'hf5;
        wrom_all[138] = 8'h20;
        wrom_all[139] = 8'h32;
        wrom_all[140] = 8'h3a;
        wrom_all[141] = 8'h25;
        wrom_all[142] = 8'h3b;
        wrom_all[143] = 8'h06;
        wrom_all[144] = 8'hdb;
        wrom_all[145] = 8'h19;
        wrom_all[146] = 8'h44;
        wrom_all[147] = 8'hed;
        wrom_all[148] = 8'hc2;
        wrom_all[149] = 8'hb8;
        wrom_all[150] = 8'he4;
        wrom_all[151] = 8'hbd;
        wrom_all[152] = 8'hcf;
        wrom_all[153] = 8'h32;
        wrom_all[154] = 8'h2e;
        wrom_all[155] = 8'hc6;
        wrom_all[156] = 8'h3f;
        wrom_all[157] = 8'hec;
        wrom_all[158] = 8'hf8;
        wrom_all[159] = 8'h00;
        wrom_all[160] = 8'h0f;
        wrom_all[161] = 8'h02;
        wrom_all[162] = 8'he0;
        wrom_all[163] = 8'hbe;
        wrom_all[164] = 8'hf4;
        wrom_all[165] = 8'he8;
        wrom_all[166] = 8'hd5;
        wrom_all[167] = 8'h11;
        wrom_all[168] = 8'hba;
        wrom_all[169] = 8'hfd;
        wrom_all[170] = 8'h34;
        wrom_all[171] = 8'hf4;
        wrom_all[172] = 8'h3d;
        wrom_all[173] = 8'h1e;
        wrom_all[174] = 8'hd5;
        wrom_all[175] = 8'h32;
        wrom_all[176] = 8'h03;
        wrom_all[177] = 8'hf4;
        wrom_all[178] = 8'h3d;
        wrom_all[179] = 8'hd7;
        wrom_all[180] = 8'h0d;
        wrom_all[181] = 8'h00;
        wrom_all[182] = 8'h36;
        wrom_all[183] = 8'h16;
        wrom_all[184] = 8'h23;
        wrom_all[185] = 8'h22;
        wrom_all[186] = 8'hec;
        wrom_all[187] = 8'hef;
        wrom_all[188] = 8'hd1;
        wrom_all[189] = 8'h18;
        wrom_all[190] = 8'h31;
        wrom_all[191] = 8'h32;
        wrom_all[192] = 8'hd1;
        wrom_all[193] = 8'h00;
        wrom_all[194] = 8'he6;
        wrom_all[195] = 8'hd4;
        wrom_all[196] = 8'hdc;
        wrom_all[197] = 8'h0f;
        wrom_all[198] = 8'he6;
        wrom_all[199] = 8'hf4;
        wrom_all[200] = 8'h02;
        wrom_all[201] = 8'h28;
        wrom_all[202] = 8'hcc;
        wrom_all[203] = 8'hb5;
        wrom_all[204] = 8'hf2;
        wrom_all[205] = 8'h25;
        wrom_all[206] = 8'he9;
        wrom_all[207] = 8'h32;
        wrom_all[208] = 8'h20;
        wrom_all[209] = 8'h10;
        wrom_all[210] = 8'h02;
        wrom_all[211] = 8'h01;
        wrom_all[212] = 8'h0e;
        wrom_all[213] = 8'he7;
        wrom_all[214] = 8'h05;
        wrom_all[215] = 8'h0a;
        wrom_all[216] = 8'hc4;
        wrom_all[217] = 8'hd4;
        wrom_all[218] = 8'h30;
        wrom_all[219] = 8'hbe;
        wrom_all[220] = 8'hf2;
        wrom_all[221] = 8'h3b;
        wrom_all[222] = 8'h0d;
        wrom_all[223] = 8'h04;
        wrom_all[224] = 8'hd9;
        wrom_all[225] = 8'h26;
        wrom_all[226] = 8'hde;
        wrom_all[227] = 8'hf0;
        wrom_all[228] = 8'hff;
        wrom_all[229] = 8'h05;
        wrom_all[230] = 8'hfe;
        wrom_all[231] = 8'h37;
        wrom_all[232] = 8'h0c;
        wrom_all[233] = 8'h36;
        wrom_all[234] = 8'h22;
        wrom_all[235] = 8'he7;
        wrom_all[236] = 8'h23;
        wrom_all[237] = 8'hdb;
        wrom_all[238] = 8'hfb;
        wrom_all[239] = 8'h15;
        wrom_all[240] = 8'h12;
        wrom_all[241] = 8'h3e;
        wrom_all[242] = 8'hea;
        wrom_all[243] = 8'h13;
        wrom_all[244] = 8'h19;
        wrom_all[245] = 8'h9f;
        wrom_all[246] = 8'h2c;
        wrom_all[247] = 8'hc9;
        wrom_all[248] = 8'he7;
        wrom_all[249] = 8'hf9;
        wrom_all[250] = 8'hd7;
        wrom_all[251] = 8'h09;
        wrom_all[252] = 8'h2a;
        wrom_all[253] = 8'hf2;
        wrom_all[254] = 8'he2;
        wrom_all[255] = 8'hce;
        wrom_all[256] = 8'hc2;
        wrom_all[257] = 8'hf8;
        wrom_all[258] = 8'hd1;
        wrom_all[259] = 8'hcc;
        wrom_all[260] = 8'hd3;
        wrom_all[261] = 8'h28;
        wrom_all[262] = 8'h28;
        wrom_all[263] = 8'h39;
        wrom_all[264] = 8'h22;
        wrom_all[265] = 8'hff;
        wrom_all[266] = 8'h03;
        wrom_all[267] = 8'h17;
        wrom_all[268] = 8'h34;
        wrom_all[269] = 8'h20;
        wrom_all[270] = 8'he4;
        wrom_all[271] = 8'hcb;
        wrom_all[272] = 8'ha9;
        wrom_all[273] = 8'h18;
        wrom_all[274] = 8'hde;
        wrom_all[275] = 8'hbc;
        wrom_all[276] = 8'h40;
        wrom_all[277] = 8'hef;
        wrom_all[278] = 8'h07;
        wrom_all[279] = 8'h14;
        wrom_all[280] = 8'h03;
        wrom_all[281] = 8'hd9;
        wrom_all[282] = 8'he6;
        wrom_all[283] = 8'h39;
        wrom_all[284] = 8'h15;
        wrom_all[285] = 8'h36;
        wrom_all[286] = 8'hfe;
        wrom_all[287] = 8'h1d;
    end

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
    // stepped word/bit indices of each bank's current neuron in out_words:
    // flat_j = (og*P + j)*HW + oy*W_OUT + ox; +1 per neuron step (bit carry),
    // += P*HW at each og wrap (constant word/bit increments)
    reg [$clog2((NEURONS+31)/32)-1:0] ow_w [0:P-1];
    reg [4:0]                          ow_b [0:P-1];

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
    // C0035: spikes ALSO land in a word-organised register file, bit-set as
    // each neuron group updates (P independent bit writes per cycle -- a
    // flop array, not BRAM; ~NEURONS bits of flops, the price of word reads)
    localparam WORDS_OUT = (NEURONS + 31) / 32;
    reg [31:0] out_words [0:WORDS_OUT-1];
    always @(posedge clk) out_w_data <= out_words[out_w_addr];

    genvar g;
    generate for (g = 0; g < P; g = g + 1) begin : g_bank
        reg signed [WIDTH-1:0] vmem [0:BN-1];
        reg                    smem [0:BN-1];
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
                for (j = 0; j < P; j = j + 1) begin
                    acc[j] <= 0;
                    ow_w[j] <= (j * HW) >> 5;       // constants per j
                    ow_b[j] <= (j * HW) & 31;
                end
                prime <= 1'b1;
                n_off <= 0; wb_a <= 0; wb <= -(W_IN + 1); in_a <= -(W_IN + 1);
                busy <= 1'b1; state <= S_MAC;
            end
        end

        S_CLEAR: begin
            if (clr < WORDS_OUT) out_words[clr[$clog2(WORDS_OUT)-1:0]] <= 32'b0;
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

        S_UPDATE: begin            // P banks each write their neuron (we_upd)
            for (j = 0; j < P; j = j + 1) begin
                acc[j] <= 0;
                out_words[ow_w[j]][ow_b[j]] <= spike_next[j];  // word file (C0035)
            end
            prime <= 1'b1;
            if (ox != W_OUT-1) begin
                ox <= ox + 1; wb <= wb + 2; in_a <= wb + 2;
                n_off <= n_off + 1;
                wb_a <= og * TAPS;
                for (j = 0; j < P; j = j + 1) begin      // flat_j += 1
                    if (ow_b[j] == 31) begin ow_b[j] <= 0; ow_w[j] <= ow_w[j] + 1; end
                    else ow_b[j] <= ow_b[j] + 1;
                end
            end else begin ox <= 0;
                if (oy != H_OUT-1) begin
                    oy <= oy + 1;
                    wb <= wb + (2*W_IN - 2*(W_OUT-1)); in_a <= wb + (2*W_IN - 2*(W_OUT-1));
                    n_off <= n_off + 1;
                    wb_a <= og * TAPS;
                    for (j = 0; j < P; j = j + 1) begin  // flat_j += 1
                        if (ow_b[j] == 31) begin ow_b[j] <= 0; ow_w[j] <= ow_w[j] + 1; end
                        else ow_b[j] <= ow_b[j] + 1;
                    end
                end else begin oy <= 0;
                    if (og != GB-1) begin
                        og <= og + 1;
                        wb <= -(W_IN + 1); in_a <= -(W_IN + 1);
                        n_off <= n_off + 1;
                        wb_a <= (og + 1) * TAPS;
                        for (j = 0; j < P; j = j + 1) begin
                            // flat_j += P*HW - HW + 1 (constant): split into
                            // word/bit increments with carry
                            if (ow_b[j] + ((P*HW - HW + 1) & 31) > 31) begin
                                ow_b[j] <= ow_b[j] + ((P*HW - HW + 1) & 31) - 32;
                                ow_w[j] <= ow_w[j] + ((P*HW - HW + 1) >> 5) + 1;
                            end else begin
                                ow_b[j] <= ow_b[j] + ((P*HW - HW + 1) & 31);
                                ow_w[j] <= ow_w[j] + ((P*HW - HW + 1) >> 5);
                            end
                        end
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
