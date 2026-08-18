// Synthesis top for the C1 accelerator: axis_conv plus the two adaptations
// Vivado's block-design flow expects.
//
// 1. Active-LOW reset. Xilinx IP and the connection automation supply
//    aresetn (reset asserted when low); our RTL uses active-high rst. The
//    inversion lives here, once, so nobody debugs a permanently-reset
//    engine on hardware day.
// 2. X_INTERFACE attributes so Vivado associates the clock with both
//    streams and knows the reset's polarity. The s_axis_*/m_axis_* names
//    themselves are what makes Vivado infer the AXI-Stream interfaces.
//
// Weights are BAKED into the RTL (BAKED_WEIGHTS=1 -> hdl/dense/weights/
// conv1_w.vh), so synthesis has no $readmemh file to find -- Vivado fails
// that lookup silently and would hand you a zero ROM. The simulation
// testbench sets BAKED_WEIGHTS=0 and reads the hex, and both paths are
// checked against golden, so they must agree.
//
// Verified by sim/run_axis_tb.sh, which instantiates THIS module -- the
// thing that gets synthesised is the thing that got tested.

`default_nettype none

module axis_conv_top #(
    parameter WEIGHT_FILE = "conv_c1_w.hex",
    parameter BAKED_WEIGHTS = 1,
    // ENGINE 0 = dense (M4 BOARD PASS design), 1 = event-driven (M6). ED_K =
    // banks. Both share this top and the AXIS wrapper: identical framing is
    // what makes the M7 dense-vs-event-driven comparison apples to apples.
    parameter ENGINE = 0,
    parameter ED_K = 4,
    parameter WT_FILE = "ed_c1_wt.hex"
) (
    (* X_INTERFACE_INFO = "xilinx.com:signal:clock:1.0 aclk CLK",
       X_INTERFACE_PARAMETER = "ASSOCIATED_BUSIF s_axis:m_axis, ASSOCIATED_RESET aresetn" *)
    input  wire        aclk,
    (* X_INTERFACE_INFO = "xilinx.com:signal:reset:1.0 aresetn RST",
       X_INTERFACE_PARAMETER = "POLARITY ACTIVE_LOW" *)
    input  wire        aresetn,

    input  wire [31:0] s_axis_tdata,
    input  wire        s_axis_tvalid,
    output wire        s_axis_tready,
    input  wire        s_axis_tlast,

    output wire [31:0] m_axis_tdata,
    output wire        m_axis_tvalid,
    input  wire        m_axis_tready,
    output wire        m_axis_tlast
);

    axis_conv #(
        .C_IN(2), .H_IN(34), .W_IN(34),
        .C_OUT(16), .H_OUT(17), .W_OUT(17),
        .T(4), .THRESHOLD(64),
        .WEIGHT_FILE(WEIGHT_FILE), .BAKED_WEIGHTS(BAKED_WEIGHTS),
        .ENGINE(ENGINE), .ED_K(ED_K), .WT_FILE(WT_FILE)
    ) core (
        .clk(aclk), .rst(~aresetn),
        .s_axis_tdata(s_axis_tdata), .s_axis_tvalid(s_axis_tvalid),
        .s_axis_tready(s_axis_tready), .s_axis_tlast(s_axis_tlast),
        .m_axis_tdata(m_axis_tdata), .m_axis_tvalid(m_axis_tvalid),
        .m_axis_tready(m_axis_tready), .m_axis_tlast(m_axis_tlast)
    );

endmodule

`default_nettype wire
