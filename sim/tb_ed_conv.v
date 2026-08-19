// Testbench for the M6 event-driven conv engine interface. Drives spike
// ADDRESS LISTS (D0016) from sim/vectors/ed_<L>_spk.txt, one timestep at a
// time, and demands every output spike and membrane equal the golden model.
//
// The DUT is whatever module implements the ed interface. Today that is
// ed_iface_shim (dense engine underneath) so the harness itself is proven;
// tomorrow it is ed_conv_layer, and this file does not change.
//
// Plusargs: +spk=<file> +s=<file> +v=<file> +nsamples=<n>

`timescale 1ns / 1ps
`default_nettype none

module tb_ed_conv;

    parameter C_IN  = 2,  H_IN  = 34, W_IN  = 34;
    parameter C_OUT = 16, H_OUT = 17, W_OUT = 17;
    parameter signed [15:0] THRESHOLD = 64;
    parameter WEIGHT_FILE = "sim/vectors/conv_c1_w.hex";
    parameter WT_FILE = "sim/vectors/ed_c1_wt.hex";
    parameter K_BANKS = 1;
    localparam T = 4;
    localparam IN_BITS = C_IN * H_IN * W_IN;
    localparam NEURONS = C_OUT * H_OUT * W_OUT;
    localparam MAX_SAMPLES = 16;
    localparam MAX_SPK = MAX_SAMPLES * T * IN_BITS;   // upper bound on list

    reg clk = 0, rst = 1, clear = 0, start = 0, spk_we = 0;
    // D0020 rev 2: spike addresses are FIELDS {ic, iy, ix}. The vector files
    // hold golden flat indices; pack them here (the DUT never sees a divide).
    localparam IC_W = (C_IN > 1) ? $clog2(C_IN) : 1;
    localparam IY_W = $clog2(H_IN), IX_W = $clog2(W_IN);
    localparam SPK_W = IC_W + IY_W + IX_W;
    reg [SPK_W-1:0] spk_addr = 0;
    function [SPK_W-1:0] spk_pack(input integer flat);
        integer ic, iy, ix;
        begin ic = flat / (H_IN*W_IN); iy = (flat % (H_IN*W_IN)) / W_IN; ix = flat % W_IN;
              spk_pack = {ic[IC_W-1:0], iy[IY_W-1:0], ix[IX_W-1:0]}; end
    endfunction
    wire busy, done;
    reg [$clog2(NEURONS)-1:0] out_addr = 0, v_addr = 0;
    wire out_data;
    wire signed [15:0] v_data;

    `ifndef ED_DUT
    `define ED_DUT ed_iface_shim
    `endif
    `ED_DUT #(
        .C_IN(C_IN), .H_IN(H_IN), .W_IN(W_IN),
        .C_OUT(C_OUT), .H_OUT(H_OUT), .W_OUT(W_OUT),
        .THRESHOLD(THRESHOLD), .WEIGHT_FILE(WEIGHT_FILE)
    `ifdef ED_HAS_WT
        , .WT_FILE(WT_FILE), .K(K_BANKS)
    `endif
    ) dut (
        .clk(clk), .rst(rst), .clear(clear),
        .spk_we(spk_we), .spk_addr(spk_addr), .start(start),
        .busy(busy), .done(done),
        .out_addr(out_addr), .out_data(out_data),
        .v_addr(v_addr), .v_data(v_data)
    );

    always #5 clk = ~clk;

    // spike list file: per (sample, ts): count, then addresses
    integer spk_words [0:MAX_SPK + MAX_SAMPLES*T - 1];
    reg        exp_s [0:MAX_SAMPLES*T*NEURONS-1];
    reg [15:0] exp_v [0:MAX_SAMPLES*T*NEURONS-1];
    reg [1023:0] f_spk, f_s, f_v;
    integer nsamples, s, t, i, k, cnt, pos, fails, checked, base, total_spk;
    integer fd, r;

    task wait_done;
        begin
            @(posedge clk); #1;
            while (!done) begin @(posedge clk); #1; end
        end
    endtask

    initial begin
        if (!$value$plusargs("spk=%s", f_spk) || !$value$plusargs("s=%s", f_s) ||
            !$value$plusargs("v=%s", f_v) || !$value$plusargs("nsamples=%d", nsamples)) begin
            $display("TB_FAIL missing plusargs"); $finish;
        end
        // read the decimal address list
        fd = $fopen(f_spk, "r"); pos = 0;
        while (!$feof(fd)) begin
            r = $fscanf(fd, "%d\n", spk_words[pos]);
            if (r == 1) pos = pos + 1;
        end
        $fclose(fd);
        $readmemb(f_s, exp_s, 0, nsamples*T*NEURONS-1);
        $readmemh(f_v, exp_v, 0, nsamples*T*NEURONS-1);
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

                base = (s*T + t)*NEURONS;
                for (i = 0; i < NEURONS; i = i + 1) begin
                    @(negedge clk);
                    out_addr = i[$clog2(NEURONS)-1:0];
                    v_addr   = i[$clog2(NEURONS)-1:0];
                    @(posedge clk); #1;
                    checked = checked + 2;
                    if (out_data !== exp_s[base + i] ||
                        v_data !== $signed(exp_v[base + i])) begin
                        fails = fails + 1;
                        if (fails <= 5)
                            $display("MISMATCH sample %0d t %0d neuron %0d: s=%b exp %b  V=%0d exp %0d",
                                     s, t, i, out_data, exp_s[base+i], v_data, $signed(exp_v[base+i]));
                    end
                end
                // let the DUT finish any post-timestep housekeeping
                while (busy) begin @(posedge clk); #1; end
            end
        end

        if (fails == 0)
            $display("TB_PASS K=%0d %0d comparisons bit-identical over %0d samples x %0d timesteps, %0d input spikes",
                     K_BANKS, checked, nsamples, T, total_spk);
        else
            $display("TB_FAIL %0d mismatched", fails);
        $finish;
    end

endmodule

`default_nettype wire
