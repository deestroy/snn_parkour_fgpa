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
// which takes a GOLDEN FLAT index and is translated to (bank, offset) here,
// so ed_conv_layer, the sweep and every testbench are K-agnostic.
//
// UNVERIFIED until sim/run_ed_scatter_tb.sh passes at the chosen K.

`default_nettype none

module ed_scatter #(
    parameter C_IN  = 2,  H_IN  = 34, W_IN  = 34,
    parameter C_OUT = 16, H_OUT = 17, W_OUT = 17,
    parameter K = 1,
    parameter WIDTH = 16,
    parameter WT_FILE = "sim/vectors/ed_c1_wt.hex",
    parameter IN_BITS = C_IN * H_IN * W_IN,
    parameter NEURONS = C_OUT * H_OUT * W_OUT,
    parameter BANK_N  = NEURONS / K              // neurons per bank
) (
    input  wire                        clk,
    input  wire                        rst,
    input  wire                        clear,

    input  wire                        spk_we,
    input  wire [$clog2(IN_BITS)-1:0]  spk_addr,
    output reg                         busy,

    // I access for the sweep / testbench, GOLDEN flat index
    input  wire [$clog2(NEURONS)-1:0]  i_addr,
    output wire signed [WIDTH-1:0]     i_rdata,     // registered read
    input  wire                        i_we,
    input  wire signed [WIDTH-1:0]     i_wdata
);

    // --- memories ---------------------------------------------------------
    // W_T as one byte-addressed ROM; the K-wide read is K parallel lookups
    // at consecutive addresses (a synthesis tool maps this onto a K-byte-wide
    // BRAM word; in simulation it is K reads).
    reg signed [7:0]        wt [0:C_IN*9*C_OUT-1];
    initial $readmemh(WT_FILE, wt);
    // K banks of the accumulator
    reg signed [WIDTH-1:0]  imem [0:K-1][0:BANK_N-1];

    // --- flat <-> (bank, offset) for the external port -------------------
    // flat = (oc*H_OUT + oy)*W_OUT + ox;  bank = oc % K;
    // offset = ((oc/K)*H_OUT + oy)*W_OUT + ox
    localparam HW = H_OUT * W_OUT;
    wire [31:0] p_oc  = i_addr / HW;
    wire [31:0] p_pos = i_addr % HW;
    wire [31:0] p_bank = p_oc % K;
    wire [31:0] p_off  = (p_oc / K) * HW + p_pos;

    reg signed [WIDTH-1:0] i_rdata_r;
    always @(posedge clk) i_rdata_r <= imem[p_bank][p_off];
    assign i_rdata = i_rdata_r;

    // --- decode the spike address -----------------------------------------
    reg [$clog2(IN_BITS)-1:0] a_r;
    integer ic, iy, ix;
    integer oy_lo, oy_hi, ox_lo, ox_hi;
    integer oy, ox, oc;
    reg     ic_wait;

    function integer lo_of(input integer i); begin lo_of = (i == 0) ? 0 : (i >> 1); end endfunction
    function integer hi_of(input integer i, input integer hmax);
        begin hi_of = ((i + 1) >> 1); if (hi_of > hmax - 1) hi_of = hmax - 1; end endfunction

    wire [1:0]  ky = iy - 2*oy + 1;
    wire [1:0]  kx = ix - 2*ox + 1;
    wire [31:0] wt_row = ((ic*3 + ky)*3 + kx)*C_OUT + oc;   // W_T[ic][ky][kx][oc..oc+K-1]
    // bank offset for channel oc+j at (oy,ox): ((oc+j)/K == oc/K since oc%K==0)
    wire [31:0] off_r = ((oc / K) * H_OUT + oy) * W_OUT + ox;

    // --- FSM --------------------------------------------------------------
    localparam S_IDLE = 0, S_DEC = 1, S_RD = 2, S_ADD = 3, S_NEXT = 4;
    reg [2:0] state;

    reg signed [7:0]       w_r [0:K-1];
    reg signed [WIDTH-1:0] i_r [0:K-1];
    reg [31:0]             off_hold;
    integer j, clr;

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
            end else if (i_we) begin
                imem[p_bank][p_off] <= i_wdata;             // sweep zeroing I
            end
        end

        S_DEC: begin
            ic <= a_r / (H_IN*W_IN);
            iy <= (a_r % (H_IN*W_IN)) / W_IN;
            ix <= a_r % W_IN;
            state <= S_RD; ic_wait <= 1'b1;
        end

        S_RD: begin
            if (ic_wait) begin
                oy_lo <= lo_of(iy); oy_hi <= hi_of(iy, H_OUT);
                ox_lo <= lo_of(ix); ox_hi <= hi_of(ix, W_OUT);
                oy <= lo_of(iy); ox <= lo_of(ix); oc <= 0;
                ic_wait <= 1'b0;
            end else begin
                // K-wide read: weights oc..oc+K-1 for this tap, and the K
                // accumulators they target -- one per bank, no conflicts
                for (j = 0; j < K; j = j + 1) begin
                    w_r[j] <= wt[wt_row + j];
                    i_r[j] <= imem[j][off_r];      // bank j holds channel oc+j
                end
                off_hold <= off_r;
                state <= S_ADD;
            end
        end

        S_ADD: begin   // K read-modify-writes, one per bank, this cycle
            for (j = 0; j < K; j = j + 1)
                imem[j][off_hold] <= i_r[j] + {{(WIDTH-8){w_r[j][7]}}, w_r[j]};
            if (oc + K < C_OUT) begin
                oc <= oc + K; state <= S_RD;
            end else begin
                oc <= 0;
                if (ox < ox_hi) begin ox <= ox + 1; state <= S_RD; end
                else begin
                    ox <= ox_lo;
                    if (oy < oy_hi) begin oy <= oy + 1; state <= S_RD; end
                    else state <= S_IDLE;
                end
            end
        end

        S_NEXT: begin  // clear: zero all banks, one offset per cycle
            for (j = 0; j < K; j = j + 1) imem[j][clr] <= 0;
            if (clr == BANK_N-1) state <= S_IDLE;
            else clr <= clr + 1;
        end

        endcase
    end

endmodule

`default_nettype wire
