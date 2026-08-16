// One leaky integrate-and-fire neuron.
//
// This is golden/network.py's lif_update() as a circuit. Per timestep n:
//
//   pending = (V[n-1] > threshold)                    ...from the STORED V
//   V[n]    = V[n-1] - (V[n-1] >>> 3) + I[n] - pending*threshold
//   s[n]    = (V[n] > threshold)
//
// The delayed reset (D0002) needs no extra storage: `pending` is recomputed
// from the membrane register with a comparator. The leak (D0007) is a shift
// and subtract. The threshold (D0008) is a power-of-two constant. There is no
// multiplier anywhere in this file, which is the point of those decisions.
//
// Timing contract (D0010): hold current_in with en=1; on the clock edge the
// neuron advances one timestep, after which v_out = V[n] and spike = s[n].
// rst is synchronous and returns the neuron to V = 0, as the golden model
// does at the start of every sample.
//
// UNVERIFIED until sim/run_lif_tb.sh passes it against the golden traces.
// Never synthesised; never run on hardware.

`default_nettype none

module lif_neuron #(
    parameter WIDTH = 16,
    parameter LEAK_SHIFT = 3,
    parameter signed [15:0] THRESHOLD = 64
) (
    input  wire                    clk,
    input  wire                    rst,
    input  wire                    en,
    input  wire signed [WIDTH-1:0] current_in,
    output reg  signed [WIDTH-1:0] v_out,
    output reg                     spike
);

    // All of this is combinational: it settles between clock edges and
    // costs nothing per-cycle beyond its silicon.
    wire               pending = (v_out > THRESHOLD);
    wire signed [WIDTH-1:0] leaked = v_out - (v_out >>> LEAK_SHIFT);
    wire signed [WIDTH-1:0] v_next =
        leaked + current_in - (pending ? THRESHOLD : {WIDTH{1'b0}});

    always @(posedge clk) begin
        if (rst) begin
            v_out <= {WIDTH{1'b0}};
            spike <= 1'b0;
        end else if (en) begin
            v_out <= v_next;
            spike <= (v_next > THRESHOLD);
        end
    end

endmodule

`default_nettype wire
