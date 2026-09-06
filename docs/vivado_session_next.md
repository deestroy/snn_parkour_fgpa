# Next Vivado/Vitis session — exact step list (revised 2026-09-06)

Status of the 2026-08-20 list: **Build 1 (ED K=4) and Build 2 (dense
P=4) are DONE and on silicon** — ED K=4 688.5 us mean (554.8-815.8),
dense P=4 1048.9 us flat, ED 1.52x at matched parallelism, both
bit-identical (experiments/board_ed_k4_20260905.md,
experiments/board_dense_p4_20260906.md). Server is build 4.

## Files on the VM: current — nothing to copy this session

The three dense files from commit 822990c (single-stage weight init)
are what the P=4 board pass used, so the VM copy is current. Nothing
else has changed in hdl/ since. Before any build, run the copy-check
ritual anyway: line 19 of conv_layer_p_c1.v reads `module
conv_layer_p_c1 #(`, Ctrl+F `wrom_all[wa[g]]` finds one hit, `#0;`
finds nothing.

## Build 3 + 4 — the K = P = 8 pair (brackets the parallelism crossover)

Why: on C1 at this activity the cycle models cross at K = P ~ 6.6
(experiments/latency_sim/ksweep_c0035): ED wins at 4 (measured 1.52x),
dense should win at 8 (sim 0.94x). Two builds put both sides of the
crossover on silicon. No new RTL: K and P are parameters of the same
baked files (ed_scatter_c1 / conv_layer_p_c1 are K- and P-generic).
Both exact synthesis configurations were run through the AXIS harness
in baked form with the hostile handshake on 2026-09-06 (BW=1 ENGINE=1
K=8; BW=1 DP=8): bit-identical, the same evidence the K=4 builds had.

Build 3 — ED K=8:  ENGINE=1, ED_K=8, BAKED_WEIGHTS=1, N_ENGINES=1
Build 4 — dense P=8: ENGINE=0, DENSE_P=8, BAKED_WEIGHTS=1, N_ENGINES=1

For each:
1. Re-customise axis_conv_top_0 (double-click the block), set the
   parameters above, OK. Tcl check:
   get_property CONFIG.ED_K   [get_bd_cells axis_conv_top_0]  -> 8   (Build 3)
   get_property CONFIG.DENSE_P [get_bd_cells axis_conv_top_0] -> 8   (Build 4)
2. Address Editor: three assignments still present (it has dropped before).
3. Validate (F6), Generate Bitstream ONCE. Do not click it again to
   "refresh" — every click re-runs implementation and moves the
   bitstream out from under the timing report.
4. Read WNS from m4_conv.runs\impl_1\design_1_wrapper_timing_summary_routed.rpt
   ("Design Timing Summary" table; check its Date line matches the run).
   What to expect: K=4/P=4 closed at +0.508 / +0.299. Doubling the banks
   halves each bank's obits/vmem depth (write-enable fan-out 578 instead
   of 1,156 per bank) but doubles the number of banks and the read-mux
   width feeding the word port. Plausible either way; WNS < 0 -> paste
   the top path, stop, do not export.
5. WNS >= 0: report_utilization (BRAM tiles: expect ~2x the K=4 count
   for ED — this is the K-vs-BRAM trade the thesis needs measured;
   DSP must still be 0) and report_power (the estimate column). Export
   Hardware WITH bitstream.
6. Vitis: Create Boot Image with the new .bit + existing build-4
   conv_server.elf (no app rebuild). Copy BOOT.bin + .xsa over.
7. Mac: pre-write checks (params, 3 MEMRANGEs, BOOT.bin partition ==
   .xsa bitstream, bitstream != previous build), card, board:
   BOARD PASS (16/16) first, then per-sample bursts + sweep.

Predictions on record (cycle model, 100 MHz, engine-only):
- ED K=8:    56,464 cycles mean -> **~0.565 ms**, range ~0.48-0.64 ms
- dense P=8: 53,195 cycles      -> **~0.532 ms**, zero spread
- dense/ED = 0.94x: dense wins at the mean; ED's best sample (48,317)
  still beats dense. If ED K=8 comes in below dense P=8 on the mean, the
  cycle model's K-independent floor (45.2k) is wrong and the crossover
  analysis is retracted.

## If time remains, in order

8. N_ENGINES=8 for one design (C0003): WNS, utilization, keep the .bit
   for the meter session's replication measurement.
9. Two extra implementation seeds of the K=4 ED build (C0019):
   Implementation Settings -> Strategy variants (Performance_Explore,
   Congestion_SpreadLogic); keep all .bits, all WNS >= 0.
10. SAIF flow prep (C0007): post-implementation functional sim of ~2
    timesteps, write_saif -> report_power; note both numbers.
11. Vitis app at -O2 (cosmetic since build 4 reports engine time
    separately; matters for the metered window's CPU share).
12. ED FC on silicon (C0015) is a separate wrapper change -- NOT this
    session; listed so it is not forgotten.

## Pre-card-write checklist (2026-09-06 revision)

.hwh: ENGINE, ED_K / DENSE_P, N_ENGINES, BAKED_WEIGHTS, DDR part
MT41J128M16, HP0=1, three MEMRANGEs (DMA regs + MM2S->DDR + S2MM->DDR).
WNS >= 0 read from the timing report whose Date matches the run (Vivado
writes bitstreams that fail timing; the bitstream header timestamp is
write_bitstream's, not implementation's). BOOT.bin PL partition
byte-equal to the .xsa bitstream, and that bitstream must DIFFER from
the previous build's. PING build 4.

Added after the dense P=4 zero-output pass: bit-identical simulation
does not cover synthesis-time INITIALIZATION. Every ROM must be
initialized in one step and read directly by the hardware (no second
initial block copying from another array); `sim/lint_synth_safety.sh`
enforces this and lists cross-scope generate references for review.
The first silicon pass of any new engine is a correctness pass first,
timing second: a "BOARD PASS" line, never just a PING.
