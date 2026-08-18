// Event-driven scatter unit (M6, D0018), K = 1.
//
// Given ONE input spike address, add that spike's weight into the input
// accumulator I of every output neuron it touches. Nothing else. The dense
// engine asks every neuron "which of your inputs fired?"; this asks one
// spike "which neurons do you reach?" and never visits the rest.
//
//   decode a -> (ic, iy, ix)
//   for each output position (oy, ox) whose 3x3/stride-2/pad-1 window
//   contains (iy, ix)  -- at most a 2x2 block:
//       ky = iy - 2*oy + 1,  kx = ix - 2*ox + 1          (the one tap that links them)
//       for oc in 0 .. C_OUT-1:                          <-- the K seam (see below)
//           I[(oc,oy,ox)] += W_T[ic][ky][kx][oc]         read-modify-write, no multiplier
//
// I is the ACCUMULATOR, not the membrane (D0019): the sweep does the one
// LIF update per neuron from (V, I) and zeroes I. This unit only adds.
//
// Weights are the TRANSPOSED table W_T[ic][ky][kx][oc] (D0018): the C_OUT
// weights for one tap are contiguous, so one row address serves the whole
// inner loop. Same 288 bytes as the dense engine for C1, different order.
//
// The K seam: the inner loop is written as `oc <= oc + K` over K banks so
// that K=4 is a fan-out of the RMW datapath, not a rewrite. At K=1 (this
// file's tested configuration) it is the plain sequential loop.
//
// Interface:
//   spk_we/spk_addr   push one input spike address (accepted when !busy)
//   busy              high while scattering; do not push
//   I read/write port for the sweep and the testbench: i_addr / i_rdata
//   (registered, 1-cycle) and i_we/i_wdata (used by the sweep to zero I;
//   the scatter unit's own RMW has priority when busy)
//   clear             pulse: zero the whole I array (new sample)
//
// UNVERIFIED until sim/run_ed_scatter_tb.sh passes against the Python
// engine's post-scatter I dump. Simulation only.

`default_nettype none

module ed_scatter #(
    parameter C_IN  = 2,  H_IN  = 34, W_IN  = 34,
    parameter C_OUT = 16, H_OUT = 17, W_OUT = 17,
    parameter K = 1,                                  // banks (1 tested)
    parameter WIDTH = 16,
    parameter WT_FILE = "sim/vectors/ed_c1_wt.hex",   // W_T, C_IN*9*C_OUT int8
    parameter IN_BITS = C_IN * H_IN * W_IN,
    parameter NEURONS = C_OUT * H_OUT * W_OUT
) (
    input  wire                        clk,
    input  wire                        rst,
    input  wire                        clear,

    input  wire                        spk_we,
    input  wire [$clog2(IN_BITS)-1:0]  spk_addr,
    output reg                         busy,

    // I access for the sweep / testbench (golden flat neuron index)
    input  wire [$clog2(NEURONS)-1:0]  i_addr,
    output wire signed [WIDTH-1:0]     i_rdata,     // registered read
    input  wire                        i_we,
    input  wire signed [WIDTH-1:0]     i_wdata
);

    // --- memories ---------------------------------------------------------
    reg signed [7:0]        wt   [0:C_IN*9*C_OUT-1];   // W_T
    reg signed [WIDTH-1:0]  imem [0:NEURONS-1];        // accumulator I
    initial $readmemh(WT_FILE, wt);

    // --- decode the spike address -----------------------------------------
    // a = (ic*H_IN + iy)*W_IN + ix
    reg [$clog2(IN_BITS)-1:0] a_r;
    integer ic, iy, ix;                 // decoded, held for the whole spike
    integer oy_lo, oy_hi, ox_lo, ox_hi; // the <=2x2 output block
    integer oy, ox, oc;                 // loop counters
    reg     ic_wait;

    // The block: oy in [ceil((iy-1)/2), floor((iy+1)/2)] clipped to [0,H_OUT-1].
    // For iy>=1: lo=(iy)/2 (integer div of iy-1+1 .. careful: (iy-1+1)>>1 = iy>>1),
    // hi=(iy+1)>>1. For iy=0: lo=0, hi=0. Same for ix.
    function integer lo_of(input integer i); begin lo_of = (i == 0) ? 0 : (i >> 1); end endfunction
    function integer hi_of(input integer i, input integer hmax);
        begin hi_of = ((i + 1) >> 1); if (hi_of > hmax - 1) hi_of = hmax - 1; end endfunction

    // kernel tap linking (iy,ix) to (oy,ox)
    wire [1:0] ky = iy - 2*oy + 1;
    wire [1:0] kx = ix - 2*ox + 1;

    // weight row address for this tap, plus oc
    wire [31:0] wt_addr = ((ic*3 + ky)*3 + kx)*C_OUT + oc;
    // target neuron in golden flat order (K=1: bank offset == flat index)
    wire [31:0] n_addr  = (oc*H_OUT + oy)*W_OUT + ox;

    // --- FSM: per spike, walk the block; per position, walk oc ------------
    localparam S_IDLE = 0, S_DEC = 1, S_RD = 2, S_ADD = 3, S_NEXT = 4;
    reg [2:0] state;

    reg signed [7:0]       w_r;
    reg signed [WIDTH-1:0] i_r;
    reg [31:0]             n_r;

    // registered read port for the sweep/testbench (D0012 style)
    reg signed [WIDTH-1:0] i_rdata_r;
    always @(posedge clk) i_rdata_r <= imem[i_addr];
    assign i_rdata = i_rdata_r;

    integer clr;
    always @(posedge clk) begin
        if (rst) begin
            state <= S_IDLE; busy <= 1'b0;
        end else case (state)

        S_IDLE: begin
            busy <= 1'b0;
            if (clear) begin
                clr <= 0; busy <= 1'b1; state <= S_NEXT;   // reuse S_NEXT as clear sweep
            end else if (spk_we) begin
                a_r <= spk_addr; busy <= 1'b1; state <= S_DEC;
            end else if (i_we) begin
                imem[i_addr] <= i_wdata;                   // sweep zeroing I
            end
        end

        S_DEC: begin   // split a into (ic, iy, ix); set up the block
            ic <= a_r / (H_IN*W_IN);
            iy <= (a_r % (H_IN*W_IN)) / W_IN;
            ix <= a_r % W_IN;
            state <= S_RD; ic_wait <= 1'b1;
        end

        S_RD: begin
            if (ic_wait) begin           // one cycle for the decode to settle
                oy_lo <= lo_of(iy); oy_hi <= hi_of(iy, H_OUT);
                ox_lo <= lo_of(ix); ox_hi <= hi_of(ix, W_OUT);
                oy <= lo_of(iy); ox <= lo_of(ix); oc <= 0;
                ic_wait <= 1'b0;
            end else begin
                // issue the two reads for (oc, oy, ox)
                w_r <= wt[wt_addr];
                i_r <= imem[n_addr];
                n_r <= n_addr;
                state <= S_ADD;
            end
        end

        S_ADD: begin   // the read-modify-write: I[n] += w
            imem[n_r] <= i_r + {{(WIDTH-8){w_r[7]}}, w_r};
            // advance: oc fastest (THE K SEAM: oc <= oc + K, K RMWs per cycle at K>1)
            if (oc + K < C_OUT) begin
                oc <= oc + K; state <= S_RD;
            end else begin
                oc <= 0;
                if (ox < ox_hi) begin ox <= ox + 1; state <= S_RD; end
                else begin
                    ox <= ox_lo;
                    if (oy < oy_hi) begin oy <= oy + 1; state <= S_RD; end
                    else state <= S_IDLE;                 // spike done
                end
            end
        end

        S_NEXT: begin  // clear sweep: zero I
            imem[clr] <= 0;
            if (clr == NEURONS-1) state <= S_IDLE;
            else clr <= clr + 1;
        end

        endcase
    end

endmodule

`default_nettype wire
