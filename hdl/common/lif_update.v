// The LIF update rule as pure combinational logic. No clock, no state:
// given the stored membrane and this timestep's input current, produce the
// next membrane and the spike bit. Where the membrane actually lives is the
// caller's business -- a register in the M2 single neuron, a BRAM word in the
// M3 dense engine, the same BRAM word in the M6 event-driven engine. All
// three MUST use this one module: the golden-model rule only has to be proven
// once per circuit, and this is the circuit.
//
//   pending = (v_in > threshold)                     ...delayed reset, D0002
//   v_out   = v_in - (v_in >>> LEAK_SHIFT)           ...beta = 0.875, D0007
//             + current_in - pending*threshold
//   spike   = (v_out > threshold)                    ...strict >, D0002
//
// Verified via the M2 testbench (sim/run_lif_tb.sh), which wraps this in a
// register exactly as lif_neuron does.

`default_nettype none

module lif_update #(
    parameter WIDTH = 16,
    parameter LEAK_SHIFT = 3,
    parameter signed [15:0] THRESHOLD = 64
) (
    input  wire signed [WIDTH-1:0] v_in,
    input  wire signed [WIDTH-1:0] current_in,
    output wire signed [WIDTH-1:0] v_out,
    output wire                    spike
);

    wire                    pending = (v_in > THRESHOLD);
    wire signed [WIDTH-1:0] leaked  = v_in - (v_in >>> LEAK_SHIFT);

    assign v_out = leaked + current_in
                 - (pending ? THRESHOLD : {WIDTH{1'b0}});
    assign spike = (v_out > THRESHOLD);

endmodule

`default_nettype wire
