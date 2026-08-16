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
// Sim-only caveats, deliberate for now (see docs/decisions.md D0012):
// memories are read combinationally and loaded with $readmemh -- fine in
// iverilog, but BRAM inference for synthesis wants registered reads and a
// COE/mem flow. That pass happens at M4, against this same testbench.
//
// UNVERIFIED until sim/run_conv_tb.sh passes. Never synthesised.

`default_nettype none

module conv_layer #(
    parameter C_IN  = 2,  H_IN  = 34, W_IN  = 34,
    parameter C_OUT = 16, H_OUT = 17, W_OUT = 17,
    parameter WIDTH = 16, LEAK_SHIFT = 3,
    parameter signed [15:0] THRESHOLD = 64,
    parameter WEIGHT_FILE = "sim/vectors/conv_c1_w.hex",
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

    assign out_data = out_mem[out_addr];
    assign v_data   = vmem[v_addr];

    always @(posedge clk)
        if (in_we) in_mem[in_addr] <= in_data;

    // --- FSM --------------------------------------------------------------
    localparam S_IDLE = 0, S_CLEAR = 1, S_ACC = 2, S_UPDATE = 3;
    reg [1:0] state = S_IDLE;

    // counters are 32-bit signed `integer`s for clarity; synthesis prunes
    integer oc, oy, ox;         // which output neuron
    integer ic, ky, kx;         // where in its kernel window
    integer clr;                // clear sweep address
    reg signed [WIDTH-1:0] acc;

    // input coordinate for the CURRENT counter values (combinational)
    wire signed [31:0] iy = 2*oy + ky - 1;
    wire signed [31:0] ix = 2*ox + kx - 1;
    wire in_bounds = (iy >= 0) && (iy < H_IN) && (ix >= 0) && (ix < W_IN);
    wire spike_here = in_bounds && in_mem[(ic*H_IN + iy)*W_IN + ix];
    wire signed [7:0] w_here = wrom[((oc*C_IN + ic)*3 + ky)*3 + kx];

    wire [31:0] neuron_addr = (oc*H_OUT + oy)*W_OUT + ox;

    // the one shared LIF update -- same module the M2 testbench verified
    wire signed [WIDTH-1:0] v_next;
    wire                    spike_next;
    lif_update #(
        .WIDTH(WIDTH), .LEAK_SHIFT(LEAK_SHIFT), .THRESHOLD(THRESHOLD)
    ) update (
        .v_in(vmem[neuron_addr]), .current_in(acc),
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
                acc <= 0; busy <= 1'b1; state <= S_ACC;
            end
        end

        S_CLEAR: begin
            vmem[clr] <= 0;
            out_mem[clr] <= 1'b0;
            if (clr == NEURONS-1) begin state <= S_IDLE; done <= 1'b1; end
            else clr <= clr + 1;
        end

        S_ACC: begin
            if (spike_here) acc <= acc + w_here;
            if (kx != 2)      kx <= kx + 1;
            else begin kx <= 0;
                if (ky != 2)  ky <= ky + 1;
                else begin ky <= 0;
                    if (ic != C_IN-1) ic <= ic + 1;
                    else begin ic <= 0; state <= S_UPDATE; end
                end
            end
        end

        S_UPDATE: begin
            vmem[neuron_addr]    <= v_next;
            out_mem[neuron_addr] <= spike_next;
            acc <= 0;
            if (ox != W_OUT-1) ox <= ox + 1;
            else begin ox <= 0;
                if (oy != H_OUT-1) oy <= oy + 1;
                else begin oy <= 0;
                    if (oc != C_OUT-1) oc <= oc + 1;
                    else begin state <= S_IDLE; done <= 1'b1; end
                end
            end
            if (!(ox == W_OUT-1 && oy == H_OUT-1 && oc == C_OUT-1))
                state <= S_ACC;
        end

        endcase
    end

endmodule

`default_nettype wire
