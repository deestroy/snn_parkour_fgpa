// Interface shim: presents the M6 event-driven conv interface (spike ADDRESS
// list in, D0016) on top of the verified dense engine (spike BIT buffer in).
//
// Purpose: let sim/tb_ed_conv.v -- the testbench the real event-driven RTL
// will be checked against -- be built and proven NOW, with the dense engine
// standing in as the DUT. D0018 says both engines must produce identical
// spikes and membranes; this shim makes that testable before a line of
// event-driven RTL exists. When ed_conv_layer.v arrives it replaces this
// module in the testbench with no other change.
//
// Protocol (the M6 engine's contract, fixed here):
//   clear            pulse: zero all membranes (new sample)
//   spk_we/spk_addr  push one input spike address for the coming timestep;
//                    any number of pushes, in any order, before `start`
//   start            pulse: run the timestep (scatter all pushed spikes,
//                    then sweep every neuron)
//   done             one-cycle pulse when the timestep's outputs are valid
//   out_addr/out_data, v_addr/v_data   registered read ports, golden order
//
// The shim turns spk pushes into bit-buffer writes and clears the buffer
// after each timestep -- which is exactly the state the address list
// represents. Simulation only.

`default_nettype none

module ed_iface_shim #(
    parameter C_IN  = 2,  H_IN  = 34, W_IN  = 34,
    parameter C_OUT = 16, H_OUT = 17, W_OUT = 17,
    parameter signed [15:0] THRESHOLD = 64,
    parameter WEIGHT_FILE = "sim/vectors/conv_c1_w.hex",
    parameter IN_BITS = C_IN * H_IN * W_IN,
    parameter NEURONS = C_OUT * H_OUT * W_OUT,
    parameter IC_W = (C_IN > 1) ? $clog2(C_IN) : 1,
    parameter IY_W = $clog2(H_IN), IX_W = $clog2(W_IN),
    parameter SPK_W = IC_W + IY_W + IX_W
) (
    input  wire                        clk,
    input  wire                        rst,
    input  wire                        clear,
    input  wire                        spk_we,
    input  wire [SPK_W-1:0]            spk_addr,   // {ic, iy, ix} (D0020 rev 2)
    input  wire                        start,
    output wire                        busy,
    output wire                        done,
    input  wire [$clog2(NEURONS)-1:0]  out_addr,
    output wire                        out_data,
    input  wire [$clog2(NEURONS)-1:0]  v_addr,
    output wire signed [15:0]          v_data
);

    // Track which addresses were pushed so we can zero them after the
    // timestep (the dense engine's buffer persists; the address list does not).
    reg [$clog2(IN_BITS)-1:0] pushed [0:IN_BITS-1];
    // fields -> the dense engine's flat bit index (simulation-only shim,
    // so the multiply is fine here)
    wire [$clog2(IN_BITS)-1:0] spk_flat =
        (spk_addr[SPK_W-1 -: IC_W] * H_IN + spk_addr[IX_W +: IY_W]) * W_IN + spk_addr[IX_W-1:0];
    integer n_pushed = 0;
    integer clr_i;

    localparam S_IDLE = 0, S_RUN = 1, S_WIPE = 2;
    reg [1:0] state = S_IDLE;

    reg                        in_we;
    reg [$clog2(IN_BITS)-1:0]  in_addr;
    reg                        in_data;
    reg                        eng_start;
    wire                       eng_done, eng_busy;

    conv_layer #(
        .C_IN(C_IN), .H_IN(H_IN), .W_IN(W_IN),
        .C_OUT(C_OUT), .H_OUT(H_OUT), .W_OUT(W_OUT),
        .THRESHOLD(THRESHOLD), .WEIGHT_FILE(WEIGHT_FILE)
    ) engine (
        .clk(clk), .rst(rst), .clear(clear), .start(eng_start),
        .busy(eng_busy), .done(eng_done),
        .in_we(in_we), .in_addr(in_addr), .in_data(in_data),
        .out_addr(out_addr), .out_data(out_data),
        .v_addr(v_addr), .v_data(v_data)
    );

    assign busy = eng_busy || (state != S_IDLE);
    // done = engine's done, but only after our wipe finishes so the next
    // timestep's pushes see a clean buffer. We wipe BEFORE running instead
    // (see below), so engine done is the real done.
    assign done = eng_done;

    always @(posedge clk) begin
        in_we <= 1'b0;
        eng_start <= 1'b0;
        if (rst) begin
            state <= S_IDLE; n_pushed <= 0;
        end else case (state)
        S_IDLE: begin
            if (spk_we) begin
                in_we <= 1'b1; in_addr <= spk_flat; in_data <= 1'b1;
                pushed[n_pushed] <= spk_flat;
                n_pushed <= n_pushed + 1;
            end
            if (start) begin
                eng_start <= 1'b1;
                state <= S_RUN;
            end
        end
        S_RUN: if (eng_done) begin
            clr_i <= 0;
            state <= (n_pushed > 0) ? S_WIPE : S_IDLE;
        end
        S_WIPE: begin   // zero the bits we set, so the buffer = empty list
            in_we <= 1'b1; in_addr <= pushed[clr_i]; in_data <= 1'b0;
            if (clr_i == n_pushed - 1) begin n_pushed <= 0; state <= S_IDLE; end
            else clr_i <= clr_i + 1;
        end
        endcase
    end

endmodule

`default_nettype wire
