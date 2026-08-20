// Testbench for ed_fc_layer: replay golden c3 spike lists, compare EVERY
// fc spike and membrane against the golden traces, per timestep.
// Plusargs: +spk=<file> +s=<file> +v=<file> +nsamples=<n>
`timescale 1ns / 1ps
`default_nettype none

module tb_ed_fc;
    parameter C_IN = 64, H_IN = 5, W_IN = 5, N_OUT = 128;
    parameter K_BANKS = 4;
    parameter WT_FILE = "sim/vectors/ed_fc_wt.hex";
    localparam T = 4;
    localparam IN_BITS = C_IN * H_IN * W_IN;
    localparam MAX_SAMPLES = 16;
    localparam MAX_SPK = MAX_SAMPLES * T * IN_BITS + MAX_SAMPLES * T;
    localparam C_W = $clog2(C_IN), Y_W = $clog2(H_IN), X_W = $clog2(W_IN);
    localparam SPK_W = C_W + Y_W + X_W;

    reg clk = 0, rst = 1, clear = 0, start = 0, spk_we = 0;
    reg [SPK_W-1:0] spk_addr = 0;
    wire busy, done_w;
    reg  [$clog2(N_OUT)-1:0] out_addr = 0, v_addr = 0;
    wire out_data; wire signed [15:0] v_data;

    function [SPK_W-1:0] spk_pack(input integer flat);
        integer c, y, x;
        begin c = flat / (H_IN*W_IN); y = (flat % (H_IN*W_IN)) / W_IN; x = flat % W_IN;
              spk_pack = {c[C_W-1:0], y[Y_W-1:0], x[X_W-1:0]}; end
    endfunction

    ed_fc_layer #(.C_IN(C_IN), .H_IN(H_IN), .W_IN(W_IN), .N_OUT(N_OUT),
                  .K(K_BANKS), .WT_FILE(WT_FILE)) dut (
        .clk(clk), .rst(rst), .clear(clear),
        .spk_we(spk_we), .spk_addr(spk_addr), .start(start),
        .busy(busy), .done(done_w),
        .out_addr(out_addr), .out_data(out_data),
        .v_addr(v_addr), .v_data(v_data));

    always #5 clk = ~clk;

    integer spk_words [0:MAX_SPK-1];
    reg        exp_s [0:MAX_SAMPLES*T*N_OUT-1];
    reg [15:0] exp_v [0:MAX_SAMPLES*T*N_OUT-1];
    reg [1023:0] f_spk, f_s, f_v;
    integer nsamples, s, t, k, cnt, pos, i, fails, checked, base, total_spk, fd, r;

    task wait_done; begin @(posedge clk); #1; while (!done_w) begin @(posedge clk); #1; end end endtask

    initial begin
        if (!$value$plusargs("spk=%s", f_spk) || !$value$plusargs("s=%s", f_s) ||
            !$value$plusargs("v=%s", f_v) || !$value$plusargs("nsamples=%d", nsamples)) begin
            $display("TB_FAIL missing plusargs"); $finish;
        end
        fd = $fopen(f_spk, "r"); pos = 0;
        while (!$feof(fd)) begin r = $fscanf(fd, "%d\n", spk_words[pos]); if (r == 1) pos = pos + 1; end
        $fclose(fd);
        $readmemb(f_s, exp_s, 0, nsamples*T*N_OUT-1);
        $readmemh(f_v, exp_v, 0, nsamples*T*N_OUT-1);
        fails = 0; checked = 0; total_spk = 0; pos = 0;

        @(negedge clk) rst = 0;

        for (s = 0; s < nsamples; s = s + 1) begin
            @(negedge clk) clear = 1;
            @(negedge clk) clear = 0;
            wait_done;

            for (t = 0; t < T; t = t + 1) begin
                cnt = spk_words[pos]; pos = pos + 1;
                for (k = 0; k < cnt; k = k + 1) begin
                    @(negedge clk);
                    spk_we = 1; spk_addr = spk_pack(spk_words[pos]); pos = pos + 1;
                end
                @(negedge clk) spk_we = 0;
                total_spk = total_spk + cnt;

                @(negedge clk) start = 1;
                @(negedge clk) start = 0;
                wait_done;

                base = (s*T + t)*N_OUT;
                for (i = 0; i < N_OUT; i = i + 1) begin
                    @(negedge clk);
                    out_addr = i[$clog2(N_OUT)-1:0];
                    v_addr   = i[$clog2(N_OUT)-1:0];
                    @(posedge clk); #1;
                    checked = checked + 2;
                    if (out_data !== exp_s[base + i] || v_data !== $signed(exp_v[base + i])) begin
                        fails = fails + 1;
                        if (fails <= 5)
                            $display("MISMATCH sample %0d t %0d neuron %0d: s=%b exp %b  V=%0d exp %0d",
                                     s, t, i, out_data, exp_s[base+i], v_data, $signed(exp_v[base+i]));
                    end
                end
                while (busy) begin @(posedge clk); #1; end
            end
        end

        if (fails == 0)
            $display("TB_PASS K=%0d %0d comparisons bit-identical over %0d samples x %0d timesteps, %0d c3 spikes",
                     K_BANKS, checked, nsamples, T, total_spk);
        else $display("TB_FAIL %0d mismatched", fails);
        $finish;
    end
endmodule
`default_nettype wire
