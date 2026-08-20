// Dense (clock-driven) spiking conv layer: 3x3, stride 2, pad 1.
//
// This is the baseline datapath of the thesis: every timestep it visits every
// output neuron whether anything spiked or not. One shared arithmetic unit,
// membranes in RAM -- the opposite of one-module-per-neuron.
//
//   for oc, oy, ox:                          outer FSM counters
//       acc = 0
//       for ic, ky, kx:                      inner FSM counters
//           iy = 2*oy + ky - 1               (pad 1, stride 2)
//           ix = 2*ox + kx - 1
//           if in bounds and spike_in[ic,iy,ix]:
//               acc += W[oc,ic,ky,kx]        no multiplier: spikes are 0/1
//       (V, spike) = lif_update(vmem[oc,oy,ox], acc)   the M2-verified core
//
// Address formulas match sim/export_conv_vectors.py line for line; that
// agreement is verified by the testbench, not assumed.
//
// Interface: pulse `clear` once per sample (zeroes membranes), then per
// timestep fill the input buffer through the write port and pulse `start`;
// `done` pulses when the sweep finishes. Spike and membrane read ports exist
// for the testbench and, later, the next layer.
//
// All memory reads are REGISTERED (address on one edge, data the next) so
// synthesis can map wrom/in_mem/vmem onto block RAM -- the D0012 pass.
// External read ports carry the same one-cycle latency. Weight loading
// still uses $readmemh, which Vivado honours at synthesis if the hex file
// is added as a project source.
//
// UNVERIFIED until sim/run_conv_tb.sh passes. Never synthesised.

`default_nettype none

// use_dsp="no": any remaining variable-x-constant multiply (all address
// bookkeeping, all register-to-register with a full cycle to settle) is
// built from fabric logic, not a DSP48. The datapath itself has no
// multiplies -- spikes are binary, the leak is a shift (D0007) -- so the
// engines' DSP count is zero BY CONSTRUCTION, and the utilization report
// now checks that property instead of hiding it.
(* use_dsp = "no" *)
module conv_layer_r1 #(
    parameter C_IN  = 2,  H_IN  = 34, W_IN  = 34,
    parameter C_OUT = 16, H_OUT = 17, W_OUT = 17,
    parameter WIDTH = 16, LEAK_SHIFT = 3,
    parameter signed [15:0] THRESHOLD = 64,
    parameter WEIGHT_FILE = "sim/vectors/conv_c1_w.hex",
    parameter BAKED_WEIGHTS = 0,  // accepted for interface symmetry; this
                                  // module always reads WEIGHT_FILE. The
                                  // synthesis variant is conv_layer_c1.v.
    parameter IN_BITS  = C_IN * H_IN * W_IN,
    parameter NEURONS  = C_OUT * H_OUT * W_OUT
) (
    input  wire        clk,
    input  wire        rst,          // sync; aborts to IDLE
    input  wire        clear,        // pulse: zero membranes (new sample)
    input  wire        start,        // pulse: process one timestep
    output reg         busy,
    output reg         done,         // one-cycle pulse at timestep end

    input  wire                        in_we,    // input spike buffer write
    input  wire [$clog2(IN_BITS)-1:0]  in_addr,
    input  wire                        in_data,

    input  wire [$clog2(NEURONS)-1:0]  out_addr, // output spike read
    output wire                        out_data,
    input  wire [$clog2(NEURONS)-1:0]  v_addr,   // membrane read
    output wire signed [WIDTH-1:0]     v_data
);

    // --- memories ---------------------------------------------------------
    reg signed [7:0]        wrom [0:C_OUT*C_IN*9-1];
    reg                     in_mem [0:IN_BITS-1];
    reg                     out_mem [0:NEURONS-1];
    reg signed [WIDTH-1:0]  vmem [0:NEURONS-1];

    // DISTILLED r1 weights (P1), inlined -- no $readmemh
    initial begin
        wrom[0] = 8'hf6;
        wrom[1] = 8'h07;
        wrom[2] = 8'heb;
        wrom[3] = 8'heb;
        wrom[4] = 8'he9;
        wrom[5] = 8'hf5;
        wrom[6] = 8'h07;
        wrom[7] = 8'he5;
        wrom[8] = 8'he9;
        wrom[9] = 8'hfd;
        wrom[10] = 8'hf0;
        wrom[11] = 8'h12;
        wrom[12] = 8'hfe;
        wrom[13] = 8'h23;
        wrom[14] = 8'hec;
        wrom[15] = 8'h3d;
        wrom[16] = 8'h15;
        wrom[17] = 8'hdc;
        wrom[18] = 8'h08;
        wrom[19] = 8'h16;
        wrom[20] = 8'hf9;
        wrom[21] = 8'hfc;
        wrom[22] = 8'hbf;
        wrom[23] = 8'h0f;
        wrom[24] = 8'hf7;
        wrom[25] = 8'hef;
        wrom[26] = 8'h0c;
        wrom[27] = 8'h07;
        wrom[28] = 8'he2;
        wrom[29] = 8'hfc;
        wrom[30] = 8'h28;
        wrom[31] = 8'he3;
        wrom[32] = 8'h1d;
        wrom[33] = 8'h0a;
        wrom[34] = 8'h12;
        wrom[35] = 8'he8;
        wrom[36] = 8'h11;
        wrom[37] = 8'h0e;
        wrom[38] = 8'h0c;
        wrom[39] = 8'h19;
        wrom[40] = 8'h18;
        wrom[41] = 8'hda;
        wrom[42] = 8'he8;
        wrom[43] = 8'hfd;
        wrom[44] = 8'h0d;
        wrom[45] = 8'he0;
        wrom[46] = 8'hf9;
        wrom[47] = 8'h01;
        wrom[48] = 8'hda;
        wrom[49] = 8'h0a;
        wrom[50] = 8'he0;
        wrom[51] = 8'h2a;
        wrom[52] = 8'hec;
        wrom[53] = 8'h08;
        wrom[54] = 8'hfa;
        wrom[55] = 8'hc2;
        wrom[56] = 8'hfd;
        wrom[57] = 8'h12;
        wrom[58] = 8'hd0;
        wrom[59] = 8'h14;
        wrom[60] = 8'hef;
        wrom[61] = 8'hfc;
        wrom[62] = 8'hdd;
        wrom[63] = 8'h06;
        wrom[64] = 8'hf4;
        wrom[65] = 8'h2d;
        wrom[66] = 8'h04;
        wrom[67] = 8'h05;
        wrom[68] = 8'h07;
        wrom[69] = 8'h4e;
        wrom[70] = 8'h28;
        wrom[71] = 8'h09;
        wrom[72] = 8'hed;
        wrom[73] = 8'he9;
        wrom[74] = 8'he1;
        wrom[75] = 8'h04;
        wrom[76] = 8'he4;
        wrom[77] = 8'h0f;
        wrom[78] = 8'hf5;
        wrom[79] = 8'hf7;
        wrom[80] = 8'h15;
        wrom[81] = 8'he1;
        wrom[82] = 8'hff;
        wrom[83] = 8'h0b;
        wrom[84] = 8'h07;
        wrom[85] = 8'h12;
        wrom[86] = 8'h04;
        wrom[87] = 8'hf8;
        wrom[88] = 8'he1;
        wrom[89] = 8'hec;
        wrom[90] = 8'hea;
        wrom[91] = 8'hfc;
        wrom[92] = 8'h2e;
        wrom[93] = 8'hf5;
        wrom[94] = 8'h13;
        wrom[95] = 8'h14;
        wrom[96] = 8'h09;
        wrom[97] = 8'h11;
        wrom[98] = 8'hee;
        wrom[99] = 8'h0f;
        wrom[100] = 8'h0e;
        wrom[101] = 8'h00;
        wrom[102] = 8'h12;
        wrom[103] = 8'h06;
        wrom[104] = 8'h22;
        wrom[105] = 8'hfa;
        wrom[106] = 8'hf9;
        wrom[107] = 8'h18;
        wrom[108] = 8'hfc;
        wrom[109] = 8'hdf;
        wrom[110] = 8'hf6;
        wrom[111] = 8'hdd;
        wrom[112] = 8'h13;
        wrom[113] = 8'h15;
        wrom[114] = 8'he7;
        wrom[115] = 8'h1f;
        wrom[116] = 8'h05;
        wrom[117] = 8'h00;
        wrom[118] = 8'hed;
        wrom[119] = 8'h08;
        wrom[120] = 8'he4;
        wrom[121] = 8'h02;
        wrom[122] = 8'hf8;
        wrom[123] = 8'h2a;
        wrom[124] = 8'h15;
        wrom[125] = 8'he9;
        wrom[126] = 8'hf3;
        wrom[127] = 8'hf6;
        wrom[128] = 8'h21;
        wrom[129] = 8'h19;
        wrom[130] = 8'hf7;
        wrom[131] = 8'he2;
        wrom[132] = 8'h25;
        wrom[133] = 8'h0c;
        wrom[134] = 8'he2;
        wrom[135] = 8'hef;
        wrom[136] = 8'h28;
        wrom[137] = 8'hfd;
        wrom[138] = 8'hd5;
        wrom[139] = 8'he8;
        wrom[140] = 8'he7;
        wrom[141] = 8'h0d;
        wrom[142] = 8'h04;
        wrom[143] = 8'he2;
        wrom[144] = 8'heb;
        wrom[145] = 8'hfa;
        wrom[146] = 8'he9;
        wrom[147] = 8'h0d;
        wrom[148] = 8'hdf;
        wrom[149] = 8'hf5;
        wrom[150] = 8'he1;
        wrom[151] = 8'hf4;
        wrom[152] = 8'h08;
        wrom[153] = 8'he5;
        wrom[154] = 8'h06;
        wrom[155] = 8'hec;
        wrom[156] = 8'hf7;
        wrom[157] = 8'hff;
        wrom[158] = 8'hed;
        wrom[159] = 8'hf7;
        wrom[160] = 8'he4;
        wrom[161] = 8'h07;
        wrom[162] = 8'he0;
        wrom[163] = 8'h25;
        wrom[164] = 8'h23;
        wrom[165] = 8'hf4;
        wrom[166] = 8'h09;
        wrom[167] = 8'h0c;
        wrom[168] = 8'hfd;
        wrom[169] = 8'hfe;
        wrom[170] = 8'h07;
        wrom[171] = 8'h0b;
        wrom[172] = 8'h07;
        wrom[173] = 8'hf5;
        wrom[174] = 8'h31;
        wrom[175] = 8'h20;
        wrom[176] = 8'hf4;
        wrom[177] = 8'heb;
        wrom[178] = 8'h1c;
        wrom[179] = 8'hf6;
        wrom[180] = 8'h0a;
        wrom[181] = 8'h0f;
        wrom[182] = 8'hef;
        wrom[183] = 8'h14;
        wrom[184] = 8'h11;
        wrom[185] = 8'h00;
        wrom[186] = 8'h1b;
        wrom[187] = 8'hf2;
        wrom[188] = 8'h02;
        wrom[189] = 8'h18;
        wrom[190] = 8'hf8;
        wrom[191] = 8'h0f;
        wrom[192] = 8'h01;
        wrom[193] = 8'hf1;
        wrom[194] = 8'h0c;
        wrom[195] = 8'h00;
        wrom[196] = 8'hf7;
        wrom[197] = 8'h19;
        wrom[198] = 8'h09;
        wrom[199] = 8'h1e;
        wrom[200] = 8'h1a;
        wrom[201] = 8'he6;
        wrom[202] = 8'he4;
        wrom[203] = 8'he0;
        wrom[204] = 8'h17;
        wrom[205] = 8'h10;
        wrom[206] = 8'h0a;
        wrom[207] = 8'h05;
        wrom[208] = 8'h0d;
        wrom[209] = 8'hf1;
        wrom[210] = 8'h0d;
        wrom[211] = 8'hd8;
        wrom[212] = 8'hfe;
        wrom[213] = 8'h07;
        wrom[214] = 8'h0c;
        wrom[215] = 8'h01;
        wrom[216] = 8'he4;
        wrom[217] = 8'h09;
        wrom[218] = 8'h0a;
        wrom[219] = 8'hff;
        wrom[220] = 8'hfd;
        wrom[221] = 8'h21;
        wrom[222] = 8'hf6;
        wrom[223] = 8'h13;
        wrom[224] = 8'h0d;
        wrom[225] = 8'h02;
        wrom[226] = 8'he9;
        wrom[227] = 8'hfa;
        wrom[228] = 8'h01;
        wrom[229] = 8'h1d;
        wrom[230] = 8'hfe;
        wrom[231] = 8'h12;
        wrom[232] = 8'hd2;
        wrom[233] = 8'h0b;
        wrom[234] = 8'h12;
        wrom[235] = 8'hfb;
        wrom[236] = 8'hd9;
        wrom[237] = 8'h05;
        wrom[238] = 8'h3a;
        wrom[239] = 8'h09;
        wrom[240] = 8'h1b;
        wrom[241] = 8'hd4;
        wrom[242] = 8'h14;
        wrom[243] = 8'h05;
        wrom[244] = 8'he4;
        wrom[245] = 8'hf6;
        wrom[246] = 8'hfc;
        wrom[247] = 8'h03;
        wrom[248] = 8'h14;
        wrom[249] = 8'h0d;
        wrom[250] = 8'hfd;
        wrom[251] = 8'he0;
        wrom[252] = 8'hf9;
        wrom[253] = 8'hed;
        wrom[254] = 8'he0;
        wrom[255] = 8'h11;
        wrom[256] = 8'hff;
        wrom[257] = 8'h11;
        wrom[258] = 8'hfd;
        wrom[259] = 8'hd6;
        wrom[260] = 8'hf8;
        wrom[261] = 8'h1a;
        wrom[262] = 8'h2c;
        wrom[263] = 8'h09;
        wrom[264] = 8'h28;
        wrom[265] = 8'h0b;
        wrom[266] = 8'heb;
        wrom[267] = 8'hf0;
        wrom[268] = 8'hf8;
        wrom[269] = 8'h02;
        wrom[270] = 8'h18;
        wrom[271] = 8'h03;
        wrom[272] = 8'h21;
        wrom[273] = 8'hde;
        wrom[274] = 8'hcf;
        wrom[275] = 8'hf9;
        wrom[276] = 8'hfb;
        wrom[277] = 8'hf9;
        wrom[278] = 8'h0e;
        wrom[279] = 8'hf4;
        wrom[280] = 8'he1;
        wrom[281] = 8'hf1;
        wrom[282] = 8'hf3;
        wrom[283] = 8'h07;
        wrom[284] = 8'h03;
        wrom[285] = 8'h09;
        wrom[286] = 8'h1e;
        wrom[287] = 8'h1e;
    end

    // External read ports: REGISTERED (D0012). Present the address on one
    // clock edge; the data is valid after the next. This is the access
    // pattern block RAM physically provides.
    reg                    out_data_r;
    reg signed [WIDTH-1:0] v_data_r;
    always @(posedge clk) begin
        out_data_r <= out_mem[out_addr];
        v_data_r   <= vmem[v_addr];
    end
    assign out_data = out_data_r;
    assign v_data   = v_data_r;

    always @(posedge clk)
        if (in_we) in_mem[in_addr] <= in_data;

    // --- FSM --------------------------------------------------------------
    // Reads are registered (BRAM-style) AND pipelined: in S_MAC each cycle
    // issues the read for the current kernel position while accumulating the
    // one issued the cycle before. One prologue cycle per neuron (first
    // issue, nothing to consume yet, flagged by `prime`) and one epilogue
    // (S_TAIL consumes the final read). ~21 cycles/neuron vs 38 for the
    // unpipelined version; same bit-exact behaviour, same testbench.
    localparam S_IDLE = 0, S_CLEAR = 1, S_MAC = 2, S_TAIL = 3,
               S_VRD = 4, S_UPDATE = 5;
    reg [2:0] state;
    reg prime;  // first S_MAC cycle of a neuron: issue only, no consume

    // counters are 32-bit signed `integer`s for clarity; synthesis prunes
    integer oc, oy, ox;         // which output neuron
    integer ic, ky, kx;         // where in its kernel window
    integer clr;                // clear sweep address
    reg signed [WIDTH-1:0] acc;

    // registered memory outputs (the "one cycle later" data)
    reg                    in_bit_r;
    reg signed [7:0]       w_r;
    reg signed [WIDTH-1:0] v_r, v_r2;

    // input coordinate for the CURRENT counter values: small adder + compare,
    // used only for the bounds mask (cheap). The ADDRESSES are not computed
    // from the counters: on the first dense build checked for timing
    // (2026-08-19) the formulas (ic*H_IN+iy)*W_IN+ix and (oc*H_OUT+oy)*W_OUT+ox
    // became chained DSP multipliers feeding RAM address ports -- 13.7 ns on a
    // 10 ns clock, WNS -3.9 -- the same disease fixed in ed_scatter the night
    // before. All three addresses are now REGISTERS stepped by constants as
    // the loops advance (values identical; the testbench proves it).
    wire signed [31:0] iy = 2*oy + ky - 1;
    wire signed [31:0] ix = 2*ox + kx - 1;
    wire in_bounds = (iy >= 0) && (iy < H_IN) && (ix >= 0) && (ix < W_IN);

    // stepped address registers (see the walk in the FSM):
    //   n_a  = (oc*H_OUT + oy)*W_OUT + ox   raster order -> +1 per neuron
    //   w_a  = ((oc*C_IN + ic)*3 + ky)*3+kx consecutive within a window;
    //          per neuron it restarts at w_base = oc*C_IN*9
    //   in_a = (ic*H_IN + iy)*W_IN + ix     steps: kx +1 | ky +W_IN-2 |
    //          ic +H_IN*W_IN-2*W_IN-2; per neuron it restarts at the window
    //          base wb = (2*oy-1)*W_IN + (2*ox-1), itself stepped by the
    //          outer loops. Out-of-window values may be negative/garbage --
    //          harmless, the in_bounds mask zeroes the DATA, exactly as the
    //          old ternary did.
    integer n_a, w_a, w_base, in_a, wb;

    // the one shared LIF update -- same module the M2 testbench verified
    wire signed [WIDTH-1:0] v_next;
    wire                    spike_next;
    lif_update #(
        .WIDTH(WIDTH), .LEAK_SHIFT(LEAK_SHIFT), .THRESHOLD(THRESHOLD)
    ) update (
        .v_in(v_r2), .current_in(acc),
        .v_out(v_next), .spike(spike_next)
    );

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
                oc <= 0; oy <= 0; ox <= 0;
                ic <= 0; ky <= 0; kx <= 0;
                acc <= 0; prime <= 1'b1;
                n_a <= 0; w_a <= 0; w_base <= 0;
                wb <= -(W_IN + 1); in_a <= -(W_IN + 1);
                busy <= 1'b1; state <= S_MAC;
            end
        end

        S_CLEAR: begin
            vmem[clr] <= 0;
            out_mem[clr] <= 1'b0;
            if (clr == NEURONS-1) begin state <= S_IDLE; done <= 1'b1; end
            else clr <= clr + 1;
        end

        S_MAC: begin  // issue read for position k, consume position k-1
            in_bit_r <= in_bounds ? in_mem[in_a] : 1'b0;
            w_r      <= wrom[w_a];
            if (!prime && in_bit_r) acc <= acc + {{(WIDTH-8){w_r[7]}}, w_r};  // explicit sign-extend
            prime <= 1'b0;
            w_a <= w_a + 1;
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

        S_TAIL: begin  // consume the final read; issue the membrane read early
            if (in_bit_r) acc <= acc + {{(WIDTH-8){w_r[7]}}, w_r};  // explicit sign-extend
            v_r   <= vmem[n_a];
            state <= S_VRD;
        end

        S_VRD: begin  // re-register: BRAM output latch -> fabric FF, so the
                      // LIF chain in S_UPDATE starts from a fast source
                      // (0.5 ns) instead of the RAM latch (2.5 ns)
            v_r2  <= v_r;
            state <= S_UPDATE;
        end

        S_UPDATE: begin
            vmem[n_a]    <= v_next;
            out_mem[n_a] <= spike_next;
            acc <= 0;
            prime <= 1'b1;
            n_a <= n_a + 1;
            if (ox != W_OUT-1) begin ox <= ox + 1; wb <= wb + 2; in_a <= wb + 2; w_a <= w_base; end
            else begin ox <= 0;
                if (oy != H_OUT-1) begin
                    oy <= oy + 1;
                    wb <= wb + (2*W_IN - 2*(W_OUT-1)); in_a <= wb + (2*W_IN - 2*(W_OUT-1));
                    w_a <= w_base;
                end else begin oy <= 0;
                    if (oc != C_OUT-1) begin
                        oc <= oc + 1;
                        wb <= -(W_IN + 1); in_a <= -(W_IN + 1);
                        w_base <= w_base + C_IN*9; w_a <= w_base + C_IN*9;
                    end else begin state <= S_IDLE; done <= 1'b1; end
                end
            end
            if (!(ox == W_OUT-1 && oy == H_OUT-1 && oc == C_OUT-1))
                state <= S_MAC;
        end

        endcase
    end

endmodule

`default_nettype wire
