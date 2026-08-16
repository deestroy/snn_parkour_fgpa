// Testbench for lif_neuron: replay golden-model traces, demand bit equality.
//
// A testbench is simulation-only code -- it is allowed to look like software
// (file reads, loops, prints) because it never becomes silicon. Only the DUT
// ("device under test", the lif_neuron instance) is real hardware.
//
// Reads sim/vectors/lif_<layer>.hex (format documented in
// export_lif_vectors.py): groups of 4 words, one group per neuron-sample,
// reset between groups. After every en'd clock edge, v_out and spike must
// equal the golden values EXACTLY (===). One bit off anywhere is a FAIL.
//
// Plusargs:  +vec=<file>  +nvecs=<count>
// Parameter: THRESHOLD (64 conv layers, 256 FC) -- set by the runner.

`timescale 1ns / 1ps
`default_nettype none

module tb_lif_neuron;

    parameter signed [15:0] THRESHOLD = 64;
    localparam T = 4;
    localparam MAX_WORDS = 8192;

    reg clk = 0;
    reg rst = 1;
    reg en = 0;
    reg signed [15:0] current_in = 0;
    wire signed [15:0] v_out;
    wire spike;

    lif_neuron #(.THRESHOLD(THRESHOLD)) dut (
        .clk(clk), .rst(rst), .en(en),
        .current_in(current_in), .v_out(v_out), .spike(spike)
    );

    always #5 clk = ~clk;  // 100 MHz equivalent; period is arbitrary in sim

    reg [47:0] words [0:MAX_WORDS-1];
    integer nvecs, nwords, i, t, fails, checked;
    reg [1023:0] vecfile;
    reg signed [15:0] exp_v;
    reg exp_s;

    initial begin
        if (!$value$plusargs("vec=%s", vecfile) ||
            !$value$plusargs("nvecs=%d", nvecs)) begin
            $display("TB_FAIL missing +vec= or +nvecs= plusarg");
            $finish;
        end
        nwords = nvecs * T;
        $readmemh(vecfile, words, 0, nwords - 1);
        fails = 0;
        checked = 0;

        for (i = 0; i < nvecs; i = i + 1) begin
            // reset: one clocked cycle back to V=0, like a new sample
            @(negedge clk) rst = 1; en = 0;
            @(negedge clk) rst = 0;

            for (t = 0; t < T; t = t + 1) begin
                // drive I[t] away from the clock edge, let the edge commit it
                current_in = words[i*T + t][47:32];
                en = 1;
                @(posedge clk);
                #1;  // settle non-blocking updates before sampling
                exp_v = words[i*T + t][31:16];
                exp_s = words[i*T + t][0];
                checked = checked + 1;
                if (v_out !== exp_v || spike !== exp_s) begin
                    fails = fails + 1;
                    if (fails <= 5)
                        $display("MISMATCH vec %0d t %0d: I=%0d  V=%0d expect %0d  s=%b expect %b",
                                 i, t, current_in, v_out, exp_v, spike, exp_s);
                end
                @(negedge clk) en = 0;
            end
        end

        if (fails == 0)
            $display("TB_PASS %0d/%0d timestep checks bit-identical (threshold %0d)",
                     checked, nwords, THRESHOLD);
        else
            $display("TB_FAIL %0d of %0d checks mismatched", fails, checked);
        $finish;
    end

endmodule

`default_nettype wire
