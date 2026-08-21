# Next Vivado/Vitis session — exact step list (written 2026-08-20)

Everything below is verified in simulation (check ladder green, incl. the
BAKED synthesis paths). One session, priority-ordered: stop anywhere after
step 5 and the session was still worth it.

## Files to copy to Windows (overwrite; add new ones as design sources)

    hdl/dense/axis_conv.v            (rewritten: word-parallel, C0035)
    hdl/dense/axis_conv_top.v        (N_ENGINES, DENSE_P params)
    hdl/dense/conv_layer_p.v         (NEW: P-wide dense engine)
    hdl/dense/conv_layer_p_c1.v      (NEW: baked synthesis variant)
    hdl/eventdriven/ed_conv_layer.v  (pipelined sweep + word port)
    hdl/eventdriven/ed_scatter.v     (unchanged today; copy for safety)
    hdl/eventdriven/ed_scatter_c1.v  (regenerated)
    host/board/conv_server.c         (BUILD_ID 3: BURST sweep + XADC)

The old conv_layer.v / conv_layer_c1.v are no longer used by the wrapper;
they can stay in the project harmlessly.

## Build 1 — event-driven, the priority (ENGINE=1, ED_K=4, BAKED=1, N_ENGINES=1)

1. Refresh Module Reference on axis_conv_top_0; Tcl:
   get_property CONFIG.ENGINE [get_bd_cells axis_conv_top_0]  -> 1
2. F6; Generate Bitstream. TODAY'S RTL IS NEW LOGIC: check WNS first
   (pipelined sweep + word wrapper + flop word-file are plausible new
   critical paths). WNS < 0 -> report_timing file to Mac, stop here.
3. WNS >= 0: utilization (expect DSP 0 -- confirms the C0017 property
   measured) + the Power summary screenshot (ED per-category breakdown,
   still missing). Export .xsa.
4. Vitis: rebuild conv_server (PING must say build 3), Create Boot Image
   with the fresh .bit. Copy BOOT.BIN + .xsa.
5. Mac verifies (six-point check incl. N_ENGINES in the .hwh grep), card,
   boot: BOARD PASS on the UNBIASED set (C0039 board half) +
   `--burst 2000` (new latency ~0.68 ms predicted) +
   `--burst-sweep --burst 3200` (C0018 on silicon, temps in reply).

## Build 2 — dense fair baseline (ENGINE=0, DENSE_P=4, BAKED=1)

Same steps; predicted ~1.04 ms/inference. Utilization: the P=4 dense row
(weight/membrane banks x4) completes the matched-area comparison data.

## If time remains, in order

6. N_ENGINES=8 for one design (C0003): WNS, utilization, keep the .bit
   for the meter session's replication measurement.
7. Two extra seeds of Build 1 (C0019): Implementation Settings ->
   Strategy variants (e.g. Performance_Explore, Congestion_SpreadLogic);
   keep all .bits, all WNS >= 0.
8. SAIF flow prep (C0007): post-implementation functional sim of ~2
   timesteps, write_saif -> report_power; note both numbers.
9. ED FC on silicon (C0015) is a separate wrapper change -- NOT this
   session; listed so it is not forgotten.

## Pre-card-write checklist (unchanged, plus one)

.hwh: ENGINE, ED_K / DENSE_P, N_ENGINES, BAKED_WEIGHTS, DDR part
MT41J128M16, HP0=1, two DMA MEMRANGEs. BOOT.bin PL partition byte-equal
to the .xsa bitstream. WNS >= 0. PING build 3.
