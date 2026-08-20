// Event-driven scatter unit (M6, D0018), parameterised by K banks (D0017).
//
// Given ONE input spike address, add that spike's weight into the input
// accumulator I of every output neuron it touches. Nothing else.
//
//   decode a -> (ic, iy, ix)
//   for each output position (oy, ox) whose 3x3/stride-2/pad-1 window
//   contains (iy, ix)  -- at most a 2x2 block:
//       ky = iy - 2*oy + 1,  kx = ix - 2*ox + 1
//       for oc in 0, K, 2K, ... :                        (C_OUT/K iterations)
//           for j in 0..K-1  IN PARALLEL:                (K RMWs this cycle)
//               I[bank j][off(oc+j,oy,ox)] += W_T[ic][ky][kx][oc+j]
//
// Banking (D0017): channel oc lives in bank oc mod K at offset
// ((oc / K) * H_OUT + oy) * W_OUT + ox. For a fixed (oy,ox), channels
// oc..oc+K-1 land in K distinct banks, so the K RMWs never collide -- no
// arbiter, no stall. K=1 is the plain sequential loop (verified first);
// K=4 is the same code with the loop fanned out.
//
// The transposed weight table W_T[ic][ky][kx][oc] puts channels oc..oc+K-1
// at K consecutive bytes, so one K-wide word read feeds all K RMWs.
//
// I is the ACCUMULATOR (D0019). The sweep reads/zeroes it through i_addr,
// which carries the golden neuron as FIELDS {oc, pos} (D0020 rev 2) and is
// translated to (bank, offset) here, so ed_conv_layer, the sweep and every
// testbench are K-agnostic.
//
// ADDRESS FORMAT (D0020 rev 2, 2026-08-18): both addresses are packed
// fields, not flat indices --
//     spk_addr = {ic, iy, ix}   widths clog2(C_IN), clog2(H_IN), clog2(W_IN)
//     i_addr   = {oc, pos}      widths clog2(C_OUT), clog2(H_OUT*W_OUT)
// -- because decoding a flat index costs a divide-by-constant (17 logic
// levels, 13.3 ns, WNS -3.5 ns on the first board build), while the
// producers (the AXIS unpacker, the sweep) walk in order and get the fields
// for free from counters. Golden ORDER is unchanged: fields are the flat
// index's mixed-radix digits.
//
// UNVERIFIED until sim/run_ed_scatter_tb.sh passes at the chosen K.

`default_nettype none

// use_dsp="no": any remaining variable-x-constant multiply (all address
// bookkeeping, all register-to-register with a full cycle to settle) is
// built from fabric logic, not a DSP48. The datapath itself has no
// multiplies -- spikes are binary, the leak is a shift (D0007) -- so the
// engines' DSP count is zero BY CONSTRUCTION, and the utilization report
// now checks that property instead of hiding it.
(* use_dsp = "no" *)
module ed_scatter_r1 #(
    parameter C_IN  = 2,  H_IN  = 34, W_IN  = 34,
    parameter C_OUT = 16, H_OUT = 17, W_OUT = 17,
    parameter K = 1,
    parameter WIDTH = 16,
    parameter WT_FILE = "sim/vectors/ed_c1_wt.hex",
    parameter IN_BITS = C_IN * H_IN * W_IN,
    parameter NEURONS = C_OUT * H_OUT * W_OUT,
    parameter BANK_N  = NEURONS / K,             // neurons per bank
    // field widths (D0020 rev 2)
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
    input  wire [SPK_W-1:0]            spk_addr,     // {ic, iy, ix}
    output reg                         busy,

    // I access for the sweep / testbench, golden neuron as {oc, pos}
    input  wire [IA_W-1:0]             i_addr,
    output wire signed [WIDTH-1:0]     i_rdata,     // registered read
    input  wire                        i_we,
    input  wire signed [WIDTH-1:0]     i_wdata
);

    // --- memories ---------------------------------------------------------
    // W_T as one byte-addressed ROM; the K-wide read is K parallel lookups
    // at consecutive addresses (a synthesis tool maps this onto a K-byte-wide
    // BRAM word; in simulation it is K reads).
    reg signed [7:0]        wt [0:C_IN*9*C_OUT-1];
    // DISTILLED r1 W_T (P1), inlined -- no $readmemh
    initial begin
        wt[0] = 8'hee;
        wt[1] = 8'h09;
        wt[2] = 8'h0e;
        wt[3] = 8'h00;
        wt[4] = 8'hef;
        wt[5] = 8'hf9;
        wt[6] = 8'hfe;
        wt[7] = 8'hf6;
        wt[8] = 8'hcf;
        wt[9] = 8'hdc;
        wt[10] = 8'h09;
        wt[11] = 8'h06;
        wt[12] = 8'hdf;
        wt[13] = 8'h0e;
        wt[14] = 8'h02;
        wt[15] = 8'h19;
        wt[16] = 8'h0a;
        wt[17] = 8'h0b;
        wt[18] = 8'h20;
        wt[19] = 8'hc8;
        wt[20] = 8'hdb;
        wt[21] = 8'h05;
        wt[22] = 8'hd5;
        wt[23] = 8'hf7;
        wt[24] = 8'h06;
        wt[25] = 8'h22;
        wt[26] = 8'h05;
        wt[27] = 8'h20;
        wt[28] = 8'h05;
        wt[29] = 8'hf6;
        wt[30] = 8'hfd;
        wt[31] = 8'h07;
        wt[32] = 8'hd7;
        wt[33] = 8'hf3;
        wt[34] = 8'h0c;
        wt[35] = 8'hfe;
        wt[36] = 8'hd7;
        wt[37] = 8'h48;
        wt[38] = 8'hf3;
        wt[39] = 8'h1c;
        wt[40] = 8'hda;
        wt[41] = 8'h18;
        wt[42] = 8'he6;
        wt[43] = 8'h1c;
        wt[44] = 8'h01;
        wt[45] = 8'hd0;
        wt[46] = 8'hea;
        wt[47] = 8'h1c;
        wt[48] = 8'he3;
        wt[49] = 8'hfe;
        wt[50] = 8'h16;
        wt[51] = 8'h0d;
        wt[52] = 8'h08;
        wt[53] = 8'hfc;
        wt[54] = 8'hd8;
        wt[55] = 8'h20;
        wt[56] = 8'h0e;
        wt[57] = 8'hf2;
        wt[58] = 8'h11;
        wt[59] = 8'he5;
        wt[60] = 8'h05;
        wt[61] = 8'h09;
        wt[62] = 8'h10;
        wt[63] = 8'he2;
        wt[64] = 8'hd5;
        wt[65] = 8'ha4;
        wt[66] = 8'h16;
        wt[67] = 8'hd3;
        wt[68] = 8'hcf;
        wt[69] = 8'h25;
        wt[70] = 8'h14;
        wt[71] = 8'hfe;
        wt[72] = 8'hbf;
        wt[73] = 8'h0b;
        wt[74] = 8'h0a;
        wt[75] = 8'he7;
        wt[76] = 8'h0c;
        wt[77] = 8'h41;
        wt[78] = 8'h01;
        wt[79] = 8'hcf;
        wt[80] = 8'hf6;
        wt[81] = 8'h11;
        wt[82] = 8'hd4;
        wt[83] = 8'h0f;
        wt[84] = 8'h08;
        wt[85] = 8'h25;
        wt[86] = 8'h0d;
        wt[87] = 8'hea;
        wt[88] = 8'h07;
        wt[89] = 8'h0c;
        wt[90] = 8'hf6;
        wt[91] = 8'hdf;
        wt[92] = 8'h23;
        wt[93] = 8'h0e;
        wt[94] = 8'h12;
        wt[95] = 8'hfe;
        wt[96] = 8'h10;
        wt[97] = 8'hf5;
        wt[98] = 8'hed;
        wt[99] = 8'hf6;
        wt[100] = 8'hf8;
        wt[101] = 8'h05;
        wt[102] = 8'he6;
        wt[103] = 8'h23;
        wt[104] = 8'hcf;
        wt[105] = 8'hf7;
        wt[106] = 8'h1d;
        wt[107] = 8'h16;
        wt[108] = 8'hf5;
        wt[109] = 8'h16;
        wt[110] = 8'hfc;
        wt[111] = 8'hf5;
        wt[112] = 8'he4;
        wt[113] = 8'hee;
        wt[114] = 8'h03;
        wt[115] = 8'h03;
        wt[116] = 8'hff;
        wt[117] = 8'h10;
        wt[118] = 8'h1c;
        wt[119] = 8'h0e;
        wt[120] = 8'hf8;
        wt[121] = 8'h00;
        wt[122] = 8'hf6;
        wt[123] = 8'h12;
        wt[124] = 8'h10;
        wt[125] = 8'hd5;
        wt[126] = 8'hdf;
        wt[127] = 8'hfe;
        wt[128] = 8'hea;
        wt[129] = 8'h0f;
        wt[130] = 8'h0d;
        wt[131] = 8'hdf;
        wt[132] = 8'h13;
        wt[133] = 8'hf4;
        wt[134] = 8'h05;
        wt[135] = 8'hde;
        wt[136] = 8'h11;
        wt[137] = 8'h03;
        wt[138] = 8'h08;
        wt[139] = 8'h0b;
        wt[140] = 8'h0c;
        wt[141] = 8'h0e;
        wt[142] = 8'h04;
        wt[143] = 8'h11;
        wt[144] = 8'hf6;
        wt[145] = 8'h0a;
        wt[146] = 8'hdc;
        wt[147] = 8'h09;
        wt[148] = 8'he5;
        wt[149] = 8'h0c;
        wt[150] = 8'h05;
        wt[151] = 8'hf5;
        wt[152] = 8'hd3;
        wt[153] = 8'h00;
        wt[154] = 8'h10;
        wt[155] = 8'hff;
        wt[156] = 8'hff;
        wt[157] = 8'hfc;
        wt[158] = 8'h20;
        wt[159] = 8'hf7;
        wt[160] = 8'heb;
        wt[161] = 8'he5;
        wt[162] = 8'hfc;
        wt[163] = 8'hf4;
        wt[164] = 8'h06;
        wt[165] = 8'h0b;
        wt[166] = 8'hf2;
        wt[167] = 8'h27;
        wt[168] = 8'h09;
        wt[169] = 8'hfb;
        wt[170] = 8'hf7;
        wt[171] = 8'h07;
        wt[172] = 8'hf2;
        wt[173] = 8'he8;
        wt[174] = 8'h39;
        wt[175] = 8'he3;
        wt[176] = 8'h09;
        wt[177] = 8'hff;
        wt[178] = 8'hed;
        wt[179] = 8'h31;
        wt[180] = 8'h0c;
        wt[181] = 8'h03;
        wt[182] = 8'h09;
        wt[183] = 8'hfb;
        wt[184] = 8'hce;
        wt[185] = 8'he9;
        wt[186] = 8'h06;
        wt[187] = 8'he6;
        wt[188] = 8'hfe;
        wt[189] = 8'hf8;
        wt[190] = 8'h11;
        wt[191] = 8'hf3;
        wt[192] = 8'hf7;
        wt[193] = 8'h26;
        wt[194] = 8'hd9;
        wt[195] = 8'h09;
        wt[196] = 8'h10;
        wt[197] = 8'h04;
        wt[198] = 8'he8;
        wt[199] = 8'hdc;
        wt[200] = 8'h03;
        wt[201] = 8'h22;
        wt[202] = 8'h00;
        wt[203] = 8'h09;
        wt[204] = 8'h05;
        wt[205] = 8'hfa;
        wt[206] = 8'h26;
        wt[207] = 8'hf3;
        wt[208] = 8'h15;
        wt[209] = 8'he2;
        wt[210] = 8'h08;
        wt[211] = 8'h04;
        wt[212] = 8'h12;
        wt[213] = 8'h09;
        wt[214] = 8'h03;
        wt[215] = 8'hea;
        wt[216] = 8'hfb;
        wt[217] = 8'h22;
        wt[218] = 8'hf5;
        wt[219] = 8'hd7;
        wt[220] = 8'h23;
        wt[221] = 8'h0b;
        wt[222] = 8'h06;
        wt[223] = 8'h08;
        wt[224] = 8'he8;
        wt[225] = 8'h1b;
        wt[226] = 8'hdf;
        wt[227] = 8'h06;
        wt[228] = 8'h04;
        wt[229] = 8'h28;
        wt[230] = 8'hfd;
        wt[231] = 8'hec;
        wt[232] = 8'hfb;
        wt[233] = 8'hf1;
        wt[234] = 8'h0e;
        wt[235] = 8'hfb;
        wt[236] = 8'h05;
        wt[237] = 8'h1b;
        wt[238] = 8'hdf;
        wt[239] = 8'h03;
        wt[240] = 8'h41;
        wt[241] = 8'h08;
        wt[242] = 8'h2f;
        wt[243] = 8'h59;
        wt[244] = 8'hf8;
        wt[245] = 8'hf9;
        wt[246] = 8'h1d;
        wt[247] = 8'h0b;
        wt[248] = 8'h05;
        wt[249] = 8'he9;
        wt[250] = 8'hff;
        wt[251] = 8'h05;
        wt[252] = 8'h0a;
        wt[253] = 8'h09;
        wt[254] = 8'hf1;
        wt[255] = 8'h09;
        wt[256] = 8'h18;
        wt[257] = 8'h0e;
        wt[258] = 8'hf8;
        wt[259] = 8'h34;
        wt[260] = 8'he1;
        wt[261] = 8'hf9;
        wt[262] = 8'h0f;
        wt[263] = 8'hff;
        wt[264] = 8'hd0;
        wt[265] = 8'h17;
        wt[266] = 8'hfa;
        wt[267] = 8'h0d;
        wt[268] = 8'hd3;
        wt[269] = 8'hfc;
        wt[270] = 8'hf8;
        wt[271] = 8'h20;
        wt[272] = 8'he0;
        wt[273] = 8'hea;
        wt[274] = 8'h07;
        wt[275] = 8'h05;
        wt[276] = 8'he2;
        wt[277] = 8'h0b;
        wt[278] = 8'hdf;
        wt[279] = 8'hde;
        wt[280] = 8'h11;
        wt[281] = 8'hf6;
        wt[282] = 8'h15;
        wt[283] = 8'h01;
        wt[284] = 8'h07;
        wt[285] = 8'he1;
        wt[286] = 8'h00;
        wt[287] = 8'h1d;
    end
    // --- flat <-> (bank, offset) for the external port -------------------
    // flat = (oc*H_OUT + oy)*W_OUT + ox;  bank = oc % K;
    // offset = ((oc/K)*H_OUT + oy)*W_OUT + ox
    localparam HW = H_OUT * W_OUT;
    localparam AB = $clog2(BANK_N);              // bank address bits
    wire [31:0] p_oc  = i_addr[IA_W-1 -: OC_W];       // field slices, no divide
    wire [31:0] p_pos = i_addr[POS_W-1:0];
    wire [31:0] p_bank = p_oc % K;
    wire [31:0] p_off  = (p_oc / K) * HW + p_pos;

    // --- decode the spike address -----------------------------------------
    reg [SPK_W-1:0] a_r;
    integer ic, iy, ix;
    integer oy_lo, oy_hi, ox_lo, ox_hi;
    integer oy, ox, oc;
    reg     ic_wait;

    function integer lo_of(input integer i); begin lo_of = (i == 0) ? 0 : (i >> 1); end endfunction
    function integer hi_of(input integer i, input integer hmax);
        begin hi_of = ((i + 1) >> 1); if (hi_of > hmax - 1) hi_of = hmax - 1; end endfunction

    // wt_row = ((ic*3 + ky)*3 + kx)*C_OUT + oc     W_T[ic][ky][kx][oc..oc+K-1]
    // off_r  = ((oc / K) * H_OUT + oy) * W_OUT + ox    bank offset for channel oc+j
    // Both are REGISTERS stepped incrementally as (oc, ox, oy) advance, not
    // recomputed from the counters each cycle. The first board build did the
    // latter and the offset became two chained DSP multipliers feeding the
    // BRAM address port -- 13.8 ns on a 10 ns clock, WNS -4.5 ns (2026-08-18).
    // Steps: oc += K  -> off += HW,           row += K
    //        ox += 1  -> off += 1,            row -= 2*C_OUT   (kx -= 2)
    //        oy += 1, ox -> ox_lo
    //                 -> off += W_OUT - (ox - ox_lo),
    //                    row += 2*C_OUT*(ox - ox_lo) - 6*C_OUT   (ky -= 2)
    //        and oc -> 0 on the last two: off -= (C_OUT/K - 1)*HW, row -= C_OUT-K
    reg [15:0] wt_row, off_r;
    localparam OC_WRAP = (C_OUT/K - 1) * HW;
    wire [15:0] ky0 = iy - 2*lo_of(iy) + 1;      // tap at the block's first row/col
    wire [15:0] kx0 = ix - 2*lo_of(ix) + 1;

    // --- FSM --------------------------------------------------------------
    localparam S_IDLE = 0, S_DEC = 1, S_RD = 2, S_ADD = 3, S_NEXT = 4;
    reg [2:0] state;

    reg signed [7:0]       w_r [0:K-1];
    reg [31:0]             off_hold;
    integer j, clr;

    // --- the K accumulator banks: ONE write port + ONE read port each -----
    // This shape is what a synthesis tool maps onto a block RAM. The first
    // version wrote imem from three different addresses (sweep zero, scatter
    // add, clear) and read it from two; Vivado could not put that on BRAM
    // and built 4,624 x 16 bits of flip-flops plus two 4,624:1 mux trees --
    // 62k LUTs on a 53k-LUT chip. Simulation never noticed (2026-08-18).
    // The FSM now steers ONE write address/data/enable and ONE read address
    // per bank; every access below lands on the same clock edge as before,
    // so ed_conv_layer's sweep timing is unchanged.
    wire we_add  = (state == S_ADD);                       // K RMWs land
    wire we_clr  = (state == S_NEXT);                      // clear, one row
    wire we_ext  = (state == S_IDLE) && i_we && !clear && !spk_we;  // sweep zero
    wire [AB-1:0] waddr = we_add ? off_hold[AB-1:0] :
                          we_clr ? clr[AB-1:0]      : p_off[AB-1:0];
    wire [AB-1:0] raddr = (state == S_IDLE) ? p_off[AB-1:0] : off_r[AB-1:0];
    wire [K*WIDTH-1:0] rd_flat;                            // bank j read data
    reg  [31:0] p_bank_r;

    genvar g;
    generate for (g = 0; g < K; g = g + 1) begin : g_bank
        reg signed [WIDTH-1:0] mem [0:BANK_N-1];
        reg signed [WIDTH-1:0] rd_q;
        wire we = we_add || we_clr || (we_ext && p_bank == g);
        wire signed [WIDTH-1:0] wdata =
            we_add ? rd_q + {{(WIDTH-8){w_r[g][7]}}, w_r[g]} :
            we_clr ? {WIDTH{1'b0}} : i_wdata;
        always @(posedge clk) begin
            if (we) mem[waddr] <= wdata;
            rd_q <= mem[raddr];
        end
        assign rd_flat[g*WIDTH +: WIDTH] = rd_q;
    end endgenerate

    always @(posedge clk) p_bank_r <= p_bank;
    assign i_rdata = rd_flat[p_bank_r*WIDTH +: WIDTH];    // registered, 1 cycle

    always @(posedge clk) begin
        if (rst) begin
            state <= S_IDLE; busy <= 1'b0;
        end else case (state)

        S_IDLE: begin
            busy <= 1'b0;
            if (clear) begin
                clr <= 0; busy <= 1'b1; state <= S_NEXT;
            end else if (spk_we) begin
                a_r <= spk_addr; busy <= 1'b1; state <= S_DEC;
            end
            // else if (i_we): the sweep's zero-write, handled by we_ext above
        end

        S_DEC: begin
            ic <= a_r[SPK_W-1 -: IC_W];              // field slices, no divide
            iy <= a_r[IX_W +: IY_W];
            ix <= a_r[IX_W-1:0];
            state <= S_RD; ic_wait <= 1'b1;
        end

        S_RD: begin
            if (ic_wait) begin
                oy_lo <= lo_of(iy); oy_hi <= hi_of(iy, H_OUT);
                ox_lo <= lo_of(ix); ox_hi <= hi_of(ix, W_OUT);
                oy <= lo_of(iy); ox <= lo_of(ix); oc <= 0;
                // starting offset / row for (oc=0, oy_lo, ox_lo): shift-adds
                // on 6-bit values, register to register
                off_r  <= lo_of(iy) * W_OUT + lo_of(ix);
                wt_row <= ((ic*3 + ky0)*3 + kx0) * C_OUT;
                ic_wait <= 1'b0;
            end else begin
                // K-wide read: weights oc..oc+K-1 for this tap; the K
                // accumulators they target are read by the banks themselves
                // this cycle (raddr = off_r) -- one per bank, no conflicts
                for (j = 0; j < K; j = j + 1)
                    w_r[j] <= wt[wt_row + j];
                off_hold <= off_r;
                state <= S_ADD;
            end
        end

        S_ADD: begin   // K read-modify-writes land this cycle (we_add)
            if (oc + K < C_OUT) begin
                oc <= oc + K; state <= S_RD;
                off_r <= off_r + HW;  wt_row <= wt_row + K;
            end else begin
                oc <= 0;
                if (ox < ox_hi) begin
                    ox <= ox + 1; state <= S_RD;
                    off_r  <= off_r - OC_WRAP + 1;
                    wt_row <= wt_row - (C_OUT - K) - 2*C_OUT;
                end else begin
                    ox <= ox_lo;
                    if (oy < oy_hi) begin
                        oy <= oy + 1; state <= S_RD;
                        off_r  <= off_r - OC_WRAP + W_OUT - (ox - ox_lo);
                        wt_row <= wt_row - (C_OUT - K) + 2*C_OUT*(ox - ox_lo) - 6*C_OUT;
                    end else state <= S_IDLE;
                end
            end
        end

        S_NEXT: begin  // clear: zero all banks, one offset per cycle (we_clr)
            if (clr == BANK_N-1) state <= S_IDLE;
            else clr <= clr + 1;
        end

        endcase
    end

endmodule

`default_nettype wire
