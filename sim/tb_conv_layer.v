// Testbench for the dense conv layer: replay golden traces, demand equality.
//
// For every sample: pulse clear. For every timestep: load the input spike
// buffer through the write port, pulse start, wait for done, then read back
// EVERY output spike bit and EVERY membrane word and compare (===) against
// the golden model's trace. 16 samples x 4 timesteps x 4624 neurons x 2
// quantities for C1: 591,872 comparisons.
//
// Plusargs: +in=<file> +s=<file> +v=<file> +nsamples=<n>
// Parameters (set by runner to match the layer): geometry + THRESHOLD.
// The weight file is a parameter of the DUT itself.

`timescale 1ns / 1ps
`default_nettype none

module tb_conv_layer;

    parameter C_IN  = 2,  H_IN  = 34, W_IN  = 34;
    parameter C_OUT = 16, H_OUT = 17, W_OUT = 17;
    parameter signed [15:0] THRESHOLD = 64;
    parameter WEIGHT_FILE = "sim/vectors/conv_c1_w.hex";
    localparam T = 4;
    localparam IN_BITS = C_IN * H_IN * W_IN;
    localparam NEURONS = C_OUT * H_OUT * W_OUT;
    localparam MAX_SAMPLES = 16;

    reg clk = 0, rst = 1, clear = 0, start = 0;
    wire busy, done;
    reg in_we = 0;
    reg [$clog2(IN_BITS)-1:0] in_addr = 0;
    reg in_data = 0;
    reg [$clog2(NEURONS)-1:0] out_addr = 0;
    wire out_data;
    reg [$clog2(NEURONS)-1:0] v_addr = 0;
    wire signed [15:0] v_data;

    conv_layer #(
        .C_IN(C_IN), .H_IN(H_IN), .W_IN(W_IN),
        .C_OUT(C_OUT), .H_OUT(H_OUT), .W_OUT(W_OUT),
        .THRESHOLD(THRESHOLD), .WEIGHT_FILE(WEIGHT_FILE)
    ) dut (
        .clk(clk), .rst(rst), .clear(clear), .start(start),
        .busy(busy), .done(done),
        .in_we(in_we), .in_addr(in_addr), .in_data(in_data),
        .out_addr(out_addr), .out_data(out_data),
        .v_addr(v_addr), .v_data(v_data)
    );

    always #5 clk = ~clk;

    reg        in_bits [0:MAX_SAMPLES*T*IN_BITS-1];
    reg        exp_s   [0:MAX_SAMPLES*T*NEURONS-1];
    reg [15:0] exp_v   [0:MAX_SAMPLES*T*NEURONS-1];
    reg [1023:0] f_in, f_s, f_v;
    integer nsamples, s, t, i, fails, checked, base;

    task wait_done;
        begin
            @(posedge clk); #1;
            while (!done) begin @(posedge clk); #1; end
        end
    endtask

    initial begin
        if (!$value$plusargs("in=%s", f_in) ||
            !$value$plusargs("s=%s", f_s) ||
            !$value$plusargs("v=%s", f_v) ||
            !$value$plusargs("nsamples=%d", nsamples)) begin
            $display("TB_FAIL missing plusargs");
            $finish;
        end
        $readmemb(f_in, in_bits, 0, nsamples*T*IN_BITS-1);
        $readmemb(f_s, exp_s, 0, nsamples*T*NEURONS-1);
        $readmemh(f_v, exp_v, 0, nsamples*T*NEURONS-1);
        fails = 0; checked = 0;

        @(negedge clk) rst = 0;

        for (s = 0; s < nsamples; s = s + 1) begin
            @(negedge clk) clear = 1;
            @(negedge clk) clear = 0;
            wait_done;

            for (t = 0; t < T; t = t + 1) begin
                // fill the input spike buffer for this timestep
                for (i = 0; i < IN_BITS; i = i + 1) begin
                    @(negedge clk);
                    in_we = 1; in_addr = i[$clog2(IN_BITS)-1:0];
                    in_data = in_bits[(s*T + t)*IN_BITS + i];
                end
                @(negedge clk) in_we = 0;

                @(negedge clk) start = 1;
                @(negedge clk) start = 0;
                wait_done;

                // compare every neuron's spike and membrane
                base = (s*T + t)*NEURONS;
                for (i = 0; i < NEURONS; i = i + 1) begin
                    out_addr = i[$clog2(NEURONS)-1:0];
                    v_addr   = i[$clog2(NEURONS)-1:0];
                    #1;
                    checked = checked + 2;
                    if (out_data !== exp_s[base + i] ||
                        v_data !== $signed(exp_v[base + i])) begin
                        fails = fails + 1;
                        if (fails <= 5)
                            $display("MISMATCH sample %0d t %0d neuron %0d: s=%b exp %b  V=%0d exp %0d",
                                     s, t, i, out_data, exp_s[base+i],
                                     v_data, $signed(exp_v[base+i]));
                    end
                end
            end
        end

        if (fails == 0)
            $display("TB_PASS %0d comparisons bit-identical over %0d samples x %0d timesteps",
                     checked, nsamples, T);
        else
            $display("TB_FAIL %0d neuron-checks mismatched", fails);
        $finish;
    end

endmodule

`default_nettype wire
