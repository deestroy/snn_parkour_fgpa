// Testbench for the AXIS wrapper: golden word streams through a hostile
// handshake.
//
// Drives the input stream with RANDOM GAPS (tvalid drops between words) and
// stalls the output stream with RANDOM BACKPRESSURE (tready drops), because
// handshake bugs hide under polite timing and the real DMA is not polite.
// Every received word must equal the golden packed spike map, and tlast must
// land exactly on the final word of each sample.
//
// Plusargs: +in=<file> +out=<file> +nsamples=<n> +wi=<words-in-per-ts>
//           +wo=<words-out-per-ts> +seed=<n>

`timescale 1ns / 1ps
`default_nettype none

module tb_axis_conv;

    parameter C_IN  = 2,  H_IN  = 34, W_IN  = 34;
    parameter C_OUT = 16, H_OUT = 17, W_OUT = 17;
    parameter signed [15:0] THRESHOLD = 64;
    parameter WEIGHT_FILE = "sim/vectors/conv_c1_w.hex";
    localparam T = 4;
    localparam MAXW = 65536;

    reg clk = 0, rst = 1;
    reg  [31:0] s_tdata = 0;
    reg         s_tvalid = 0, s_tlast = 0;
    wire        s_tready;
    wire [31:0] m_tdata;
    wire        m_tvalid, m_tlast;
    reg         m_tready = 0;

    // Instantiate the SYNTHESIS top (active-low reset and all), not the
    // inner module -- what gets synthesised is what got tested.
    // BAKED_WEIGHTS=1: exercise the exact path synthesis uses (compiled-in
    // table), so a hex-vs-baked mismatch would show up here, not on silicon.
    axis_conv_top #(
        .WEIGHT_FILE(WEIGHT_FILE), .BAKED_WEIGHTS(1)
    ) dut (
        .aclk(clk), .aresetn(~rst),
        .s_axis_tdata(s_tdata), .s_axis_tvalid(s_tvalid),
        .s_axis_tready(s_tready), .s_axis_tlast(s_tlast),
        .m_axis_tdata(m_tdata), .m_axis_tvalid(m_tvalid),
        .m_axis_tready(m_tready), .m_axis_tlast(m_tlast)
    );

    always #5 clk = ~clk;

    reg [31:0] in_words  [0:MAXW-1];
    reg [31:0] exp_words [0:MAXW-1];
    integer nsamples, wi, wo, seed;
    integer n_in, n_out, tx_i, rx_i, fails, lasts;

    reg [1023:0] f_in, f_out;

    // watchdog: a stalled stream must fail loudly, not hang the sim
    initial begin
        #200_000_000;
        $display("TB_FAIL watchdog: stream stalled (received %0d words)", rx_i);
        $finish;
    end

    // --- driver: feed words with random gaps -----------------------------

    initial begin
        if (!$value$plusargs("in=%s", f_in) ||
            !$value$plusargs("out=%s", f_out) ||
            !$value$plusargs("nsamples=%d", nsamples) ||
            !$value$plusargs("wi=%d", wi) ||
            !$value$plusargs("wo=%d", wo)) begin
            $display("TB_FAIL missing plusargs"); $finish;
        end
        if (!$value$plusargs("seed=%d", seed)) seed = 1;
        n_in  = nsamples * T * wi;
        n_out = nsamples * T * wo;
        $readmemh(f_in, in_words, 0, n_in-1);
        $readmemh(f_out, exp_words, 0, n_out-1);
        fails = 0; lasts = 0;

        @(negedge clk) rst = 0;

        // driver loop. All handshake sampling happens at the NEGEDGE, when
        // signals are stable: tvalid && tready seen at a negedge means the
        // transfer completes at the following posedge. Sampling after the
        // posedge reads post-transfer state and silently drops words -- the
        // first version of this bench did exactly that.
        for (tx_i = 0; tx_i < n_in; tx_i = tx_i + 1) begin
            while ($dist_uniform(seed, 0, 99) < 30) @(negedge clk);  // gap
            @(negedge clk);
            s_tdata  = in_words[tx_i];
            s_tvalid = 1;
            s_tlast  = (tx_i == n_in-1);
            while (!s_tready) @(negedge clk);
            @(posedge clk);            // transfer completes here
            @(negedge clk);
            s_tvalid = 0; s_tlast = 0;
        end
    end

    // --- receiver: random backpressure, compare every word ---------------
    initial begin
        rx_i = 0;
        forever begin
            @(negedge clk);
            m_tready = ($dist_uniform(seed, 0, 99) < 70);
            #1;  // same negedge-sampling rule as the driver: stable mid-cycle
            if (m_tvalid && m_tready) begin
                if (m_tdata !== exp_words[rx_i]) begin
                    fails = fails + 1;
                    if (fails <= 5)
                        $display("MISMATCH word %0d: got %08x exp %08x",
                                 rx_i, m_tdata, exp_words[rx_i]);
                end
                // tlast must land on the final word of each SAMPLE
                if (m_tlast) begin
                    lasts = lasts + 1;
                    if (((rx_i + 1) % (T * wo)) != 0) begin
                        fails = fails + 1;
                        $display("MISMATCH tlast at word %0d", rx_i);
                    end
                end
                rx_i = rx_i + 1;
                if (rx_i == n_out) begin
                    if (fails == 0 && lasts == nsamples)
                        $display("TB_PASS %0d words bit-identical, tlast x%0d correct, hostile handshake",
                                 n_out, lasts);
                    else
                        $display("TB_FAIL %0d mismatches, %0d tlasts (expect %0d)",
                                 fails, lasts, nsamples);
                    $finish;
                end
            end
        end
    end

endmodule

`default_nettype wire
