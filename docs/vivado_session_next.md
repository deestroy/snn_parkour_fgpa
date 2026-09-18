# Next Vivado/Vitis session — exact step list (revised 2026-09-06)

Status of the 2026-08-20 list: **Build 1 (ED K=4) and Build 2 (dense
P=4) are DONE and on silicon** — ED K=4 688.5 us mean (554.8-815.8),
dense P=4 1048.9 us flat, ED 1.52x at matched parallelism, both
bit-identical (experiments/board_ed_k4_20260905.md,
experiments/board_dense_p4_20260906.md). Server is build 4.

## Files on the VM: ONE file to re-copy before Build 3 (revised 2026-09-17)

`hdl/eventdriven/ed_conv_layer.v` changed on 2026-09-17 (C0044: the
sweep never zeroed neuron 0's input current; invisible on N-MNIST,
caught by DVS-Gesture). Copy it over the VM's copy before Build 3 and
check: Ctrl+F `(C0044)` finds one hit in ed_conv_layer.v. The K=4
bitstream on the board predates the fix — its N-MNIST results stand
(the check set never puts a spike in neuron 0's receptive field), but
do not reuse that bitstream for DVS-Gesture or robot data.

The three dense files from commit 822990c (single-stage weight init)
are what the P=4 board pass used, so that part of the VM copy is
current. Before any build, run the copy-check ritual anyway: line 19 of
conv_layer_p_c1.v reads `module conv_layer_p_c1 #(`, Ctrl+F
`wrom_all[wa[g]]` finds one hit, `#0;` finds nothing.

## Builds 3 + 4 DONE 2026-09-17 — the K = P = 8 pair is on silicon
ED K=8: 575.5 us mean (494-653), 13.5 BRAM tiles, WNS +0.332 — but this
bitstream PREDATES the C0044 fix (N-MNIST numbers stand; not for other
data). Dense P=8: 540.3 us flat, 8.5 tiles, WNS +0.101, built with the
fix in the project. dense/ED = 0.939x: crossover between 4 and 8 on
silicon. Records: experiments/board_ed_k8_20260917.md,
experiments/board_dense_p8_20260917.md.

Scripted flow now standard: `git pull` in C:/Users/dhritiaravind/snn_parkour_fpga,
then in the Tcl console
  set ENGINE <0|1>; set ED_K <K>; set DENSE_P <P>; source C:/Users/dhritiaravind/snn_parkour_fpga/host/vivado/build_engine.tcl
Outputs land in m4_conv/builds/<tag>/; Create Boot Image in Vitis with
that folder's .bit; copy BOOT.bin + .xsa to the Mac through
\\tsclient\Users\dhritiaravind\git_projects\snn_parkour_fpga\host\mac\build.
Project HDL still lives in m4_loopback/: after any hdl/ change, copy the
file from the clone over the m4_loopback copy (Copy-Item ... -Force) and
confirm the marker with Ctrl+F before building.

Next ED build should be a clean K=8 (C0044 in) if the K=8 bitstream is
ever needed for DVS-Gesture; otherwise proceed to the "if time remains"
list below.

## Build 3 + 4 — the K = P = 8 pair (brackets the parallelism crossover)

Why: on C1 at this activity the cycle models cross at K = P ~ 6.6
(experiments/latency_sim/ksweep_c0035): ED wins at 4 (measured 1.52x),
dense should win at 8 (sim 0.94x). Two builds put both sides of the
crossover on silicon. No new RTL beyond the C0044 line: K and P are parameters of the same
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

## DVS-Gesture pair — the second benchmark on silicon (ready 2026-09-18, DATASET=1)

Why: on DVS-Gesture C1 the simulated matched-parallelism verdict at
K = P = 4 is ED 1.25x on the mean but a LOSS on the two densest clips
(experiments/dvsgesture/latency_sim/README.md): the activity crossover
(~30 % input density) falls inside one dataset. Two builds put that on
silicon, one per engine.

What changed for it: `axis_conv_top` has a new parameter **DATASET**
(0 = N-MNIST C1, default; 1 = DVS-Gesture C1). One knob selects the
baked weight table (`conv_layer_p_g1` / `ed_scatter_g1`, generated by
sim/gen_weight_vh.py from golden/dvsgesture_weights_int8.npz) AND the
geometry (2x64x64 -> 16x32x32) AND the threshold (128), so they cannot
be mismatched in the dialog. Both exact configurations went through the
baked AXIS harness with the hostile handshake on 2026-09-18 (BW=1
ENGINE=1 K=4 g1; BW=1 DP=4 g1): 16,384 words bit-identical each, and
the N-MNIST DATASET=0 runs are unchanged. Both DATASET=1 tops lint
clean.

Build A — ED K=4, DVS-Gesture:   ENGINE=1, ED_K=4,     BAKED_WEIGHTS=1, N_ENGINES=1, DATASET=1
Build B — dense P=4, DVS-Gesture: ENGINE=0, DENSE_P=4, BAKED_WEIGHTS=1, N_ENGINES=1, DATASET=1

Steps beyond the scripted flow:
1. Four new/changed HDL files must be in the project: hdl/dense/
   conv_layer_p_g1.v and hdl/eventdriven/ed_scatter_g1.v (new; add as
   sources), plus the changed hdl/dense/axis_conv.v, axis_conv_top.v
   and hdl/eventdriven/ed_conv_layer.v (C0044 AND the DATASET select).
   Markers: Ctrl+F `DATASET` finds hits in all three changed files;
   `module conv_layer_p_g1` and `module ed_scatter_g1` one hit each.
2. The top gained a parameter, so the RTL module reference in the block
   design must be refreshed before DATASET appears in the customise
   dialog: right-click axis_conv_top_0 -> Refresh Module (or
   `update_module_reference design_1_axis_conv_top_0_0`), then check
   `get_property CONFIG.DATASET [get_bd_cells axis_conv_top_0]` -> 1.
   build_engine.tcl does this check when you `set DATASET 1` before
   sourcing (tag gets `_dvsg`).
3. Vitis: the server must be rebuilt with `-DDATASET=1` (the request is
   1,024 words and the reply 2,048 words per inference instead of
   292 / 580). Server build 5's PING reply carries the dataset in word 2
   and host/uart_client.py prints it: check it says "DVS-Gesture C1"
   before loading samples. A DATASET=0 server on a DATASET=1 bitstream
   fails with ERR_NWORDS, which is the intended failure.
4. .hwh check adds DATASET=1 to the ENGINE/ED_K/DENSE_P grep.
5. Expected engine-only latency (100 MHz, from the sims): ED K=4 mean
   2.88 ms, min 1.99, max 4.57 (sample 1); dense P=4 3.60 ms flat.
   Timing: same engines at the same K/P, four times the membrane and
   output-word memory (16,384 neurons); expect BRAM ~4x the N-MNIST
   builds (ED K=4 ~50 tiles?) and WNS to tighten; WNS < 0 -> paste the
   report, do not write the card.
6. Host vectors: the 8 test samples of sim/vectors/axis_g1_*.hex are
   the check set (export with sim/export_dvsgesture_vectors.py then
   sim/export_axis_vectors.py --layer g1). The card writer needs
   packed frames from data/packed_dvsgesture/test_frames.npy (on the
   Mac and the box).

## If time remains, in order

8. DONE 2026-09-17, both engines (C0003 build half complete): ED K=4 x8
   (WNS +0.430, 86 tiles) and dense P=4 x8 (WNS +0.041, 46 tiles, 52 %
   LUT); per-engine latency unchanged by replication. Records:
   experiments/board_ed_k4_x8_20260917.md, board_dense_p4_x8_20260917.md.
   Meter session uses these two bitstreams + the N=1 K=4/P=4 ones.
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
