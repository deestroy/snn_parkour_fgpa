// Testbench for ed_scatter: replay each timestep's spike address list, then
// compare EVERY accumulator word I[n] against the Python engine's post-scatter
// dump (sim/vectors/ed_<L>_i.hex), then zero I as the sweep would, and go on.
// This checks the scatter unit in isolation, before any sweep exists.
//
// Plusargs: +spk=<file> +i=<file> +nsamples=<n>

`timescale 1ns / 1ps
`default_nettype none

module tb_ed_scatter;

    parameter C_IN  = 2,  H_IN  = 34, W_IN  = 34;
    parameter C_OUT = 16, H_OUT = 17, W_OUT = 17;
    parameter WT_FILE = "sim/vectors/ed_c1_wt.hex";
    parameter K_BANKS = 1;
    localparam T = 4;
    localparam IN_BITS = C_IN * H_IN * W_IN;
    localparam NEURONS = C_OUT * H_OUT * W_OUT;
    localparam MAX_SAMPLES = 16;
    localparam MAX_SPK = MAX_SAMPLES * T * IN_BITS + MAX_SAMPLES * T;

    reg clk = 0, rst = 1, clear = 0, spk_we = 0;
    reg [$clog2(IN_BITS)-1:0] spk_addr = 0;
    wire busy;
    reg  [$clog2(NEURONS)-1:0] i_addr = 0;
    wire signed [15:0] i_rdata;
    reg  i_we = 0;
    reg  signed [15:0] i_wdata = 0;

    ed_scatter #(
        .C_IN(C_IN), .H_IN(H_IN), .W_IN(W_IN),
        .C_OUT(C_OUT), .H_OUT(H_OUT), .W_OUT(W_OUT),
        .K(K_BANKS), .WT_FILE(WT_FILE)
    ) dut (
        .clk(clk), .rst(rst), .clear(clear),
        .spk_we(spk_we), .spk_addr(spk_addr), .busy(busy),
        .i_addr(i_addr), .i_rdata(i_rdata), .i_we(i_we), .i_wdata(i_wdata)
    );

    always #5 clk = ~clk;

    integer spk_words [0:MAX_SPK-1];
    reg [15:0] exp_i [0:MAX_SAMPLES*T*NEURONS-1];
    reg [1023:0] f_spk, f_i;
    integer nsamples, s, t, k, cnt, pos, i, fails, checked, base, total_spk, fd, r;
    integer cyc_scatter, cyc0;

    task wait_idle; begin @(posedge clk); #1; while (busy) begin @(posedge clk); #1; end end endtask

    initial begin
        if (!$value$plusargs("spk=%s", f_spk) || !$value$plusargs("i=%s", f_i) ||
            !$value$plusargs("nsamples=%d", nsamples)) begin
            $display("TB_FAIL missing plusargs"); $finish;
        end
        fd = $fopen(f_spk, "r"); pos = 0;
        while (!$feof(fd)) begin r = $fscanf(fd, "%d\n", spk_words[pos]); if (r == 1) pos = pos + 1; end
        $fclose(fd);
        $readmemh(f_i, exp_i, 0, nsamples*T*NEURONS-1);
        fails = 0; checked = 0; total_spk = 0; pos = 0; cyc_scatter = 0;

        @(negedge clk) rst = 0;

        for (s = 0; s < nsamples; s = s + 1) begin
            @(negedge clk) clear = 1;
            @(negedge clk) clear = 0;
            wait_idle;

            for (t = 0; t < T; t = t + 1) begin
                cnt = spk_words[pos]; pos = pos + 1;
                cyc0 = $time;
                for (k = 0; k < cnt; k = k + 1) begin
                    // push one spike, wait until the unit has consumed it
                    @(negedge clk);
                    spk_we = 1; spk_addr = spk_words[pos]; pos = pos + 1;
                    @(negedge clk) spk_we = 0;
                    wait_idle;
                end
                cyc_scatter = cyc_scatter + ($time - cyc0) / 10;
                total_spk = total_spk + cnt;

                // compare every I word against the Python post-scatter dump
                base = (s*T + t)*NEURONS;
                for (i = 0; i < NEURONS; i = i + 1) begin
                    @(negedge clk); i_addr = i[$clog2(NEURONS)-1:0];
                    @(posedge clk); #1;
                    checked = checked + 1;
                    if (i_rdata !== $signed(exp_i[base + i])) begin
                        fails = fails + 1;
                        if (fails <= 5)
                            $display("MISMATCH sample %0d t %0d neuron %0d: I=%0d exp %0d",
                                     s, t, i, i_rdata, $signed(exp_i[base+i]));
                    end
                end
                // stand in for the sweep: zero I
                for (i = 0; i < NEURONS; i = i + 1) begin
                    @(negedge clk); i_we = 1; i_addr = i[$clog2(NEURONS)-1:0]; i_wdata = 0;
                end
                @(negedge clk) i_we = 0;
            end
        end

        if (fails == 0)
            $display("TB_PASS K=%0d %0d accumulator words bit-identical over %0d samples x %0d timesteps, %0d spikes, %0d scatter cycles (%0d/spike)",
                     K_BANKS, checked, nsamples, T, total_spk, cyc_scatter, cyc_scatter / (total_spk > 0 ? total_spk : 1));
        else
            $display("TB_FAIL %0d mismatched", fails);
        $finish;
    end

endmodule

`default_nettype wire
