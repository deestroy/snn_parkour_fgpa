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
    parameter WT_FILE = "ed_c1_wt.hex",
    parameter N_ENGINES = 1,  // C0003: engine replication for metering
    parameter DENSE_P = 1,    // C0029/C0035: dense lanes (P == ED_K is matched)
    // DATASET (C0012): ONE knob selects the baked weight table AND the
    // geometry/threshold that go with it, so they cannot be mismatched
    // in the block-design dialog. Check it in the .hwh like ENGINE/ED_K.
    //   0 = N-MNIST C1:     2x34x34 -> 16x17x17, THRESHOLD 64  (conv_layer_p_c1 / ed_scatter_c1)
    //   1 = DVS-Gesture C1: 2x64x64 -> 16x32x32, THRESHOLD 128 (conv_layer_p_g1 / ed_scatter_g1)
    parameter DATASET = 0
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

    // N_ENGINES (C0003): replicate the engine so the metered delta rises
    // above baseline drift. Instance 0 talks to the DMA; replicas receive
    // the SAME input stream (identical FSMs from the same reset advance in
    // lockstep, so instance 0's tready speaks for all) and their outputs
    // are consumed unconditionally. DONT_TOUCH keeps synthesis from
    // pruning them. Per-engine energy is then delta-P / N_ENGINES, with N
    // stated (and checked in the .hwh) alongside every number.
    // geometry set from DATASET (see the parameter comment)
    localparam DS_H_IN  = (DATASET == 1) ? 64 : 34;
    localparam DS_W_IN  = (DATASET == 1) ? 64 : 34;
    localparam DS_H_OUT = (DATASET == 1) ? 32 : 17;
    localparam DS_W_OUT = (DATASET == 1) ? 32 : 17;
    localparam signed [15:0] DS_THRESHOLD = (DATASET == 1) ? 16'sd128 : 16'sd64;

    genvar gi;
    generate for (gi = 0; gi < N_ENGINES; gi = gi + 1) begin : g_rep
        wire [31:0] rep_tdata;
        wire rep_tvalid, rep_tready, rep_tlast;
        (* DONT_TOUCH = "true" *) axis_conv #(
            .C_IN(2), .H_IN(DS_H_IN), .W_IN(DS_W_IN),
            .C_OUT(16), .H_OUT(DS_H_OUT), .W_OUT(DS_W_OUT),
            .T(4), .THRESHOLD(DS_THRESHOLD),
            .WEIGHT_FILE(WEIGHT_FILE), .BAKED_WEIGHTS(BAKED_WEIGHTS), .DATASET(DATASET),
            .ENGINE(ENGINE), .ED_K(ED_K), .WT_FILE(WT_FILE), .DENSE_P(DENSE_P)
        ) core (
            .clk(aclk), .rst(~aresetn),
            // C0053: replicas must see the BUS HANDSHAKE, not raw tvalid.
            // Only instance 0's tready reaches the DMA, so a replica whose
            // own S_RX is asserted would accept on tvalid alone -- and while
            // instance 0 is still in S_TXSEND the DMA holds the SAME word on
            // the bus, so the replica latched it once per cycle and filled
            // its input buffer with duplicates of one word, then ran on that.
            // Gating with s_axis_tready makes a replica accept exactly on the
            // cycles a real transfer occurs. No-op for instance 0 (its own
            // tready IS s_axis_tready, and it only accepts in S_RX), and no
            // combinational loop: tready is a function of the state register.
            .s_axis_tdata(s_axis_tdata),
            .s_axis_tvalid(s_axis_tvalid & s_axis_tready),
            .s_axis_tready(rep_tready), .s_axis_tlast(s_axis_tlast),
            .m_axis_tdata(rep_tdata), .m_axis_tvalid(rep_tvalid),
            // and the SAME output ready, so replicas stall in transmit on the
            // same cycles instead of draining early and racing back to S_RX.
            .m_axis_tready(m_axis_tready),
            .m_axis_tlast(rep_tlast)
        );
    end endgenerate
    assign s_axis_tready = g_rep[0].rep_tready;
    assign m_axis_tdata  = g_rep[0].rep_tdata;
    assign m_axis_tvalid = g_rep[0].rep_tvalid;
    assign m_axis_tlast  = g_rep[0].rep_tlast;

endmodule

`default_nettype wire
