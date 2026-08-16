// One leaky integrate-and-fire neuron: lif_update plus a membrane register.
//
// This is the M2 module. Since the M3 refactor it holds no arithmetic of its
// own -- the update rule lives in lif_update.v, shared with the dense and
// event-driven engines, so a fix or change there is automatically tested here
// by sim/run_lif_tb.sh.
//
// Timing contract (D0010): hold current_in with en=1; on the clock edge the
// neuron advances one timestep, after which v_out = V[n] and spike = s[n].
// rst is synchronous and returns the neuron to V = 0, as the golden model
// does at the start of every sample.

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

    wire signed [WIDTH-1:0] v_next;
    wire                    spike_next;

    lif_update #(
        .WIDTH(WIDTH), .LEAK_SHIFT(LEAK_SHIFT), .THRESHOLD(THRESHOLD)
    ) update (
        .v_in(v_out), .current_in(current_in),
        .v_out(v_next), .spike(spike_next)
    );

    always @(posedge clk) begin
        if (rst) begin
            v_out <= {WIDTH{1'b0}};
            spike <= 1'b0;
        end else if (en) begin
            v_out <= v_next;
            spike <= spike_next;
        end
    end

endmodule

`default_nettype wire
