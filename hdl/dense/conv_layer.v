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

module conv_layer #(
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

    initial $readmemh(WEIGHT_FILE, wrom);

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
