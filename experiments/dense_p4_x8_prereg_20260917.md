# Pre-registration: dense P=4, N_ENGINES=8 (C0003 replication) first silicon pass (written 2026-09-17, 23:12, before the build finished)

Purpose: the dense half of C0003 (both engines at N=1 and N=8, WNS >= 0),
giving the meter session a replicated dense bitstream to pair with the
replicated ED K=4 one (experiments/board_ed_k4_x8_20260917.md).

Build under test: ENGINE=0, DENSE_P=4, N_ENGINES=8, BAKED_WEIGHTS=1,
built by host/vivado/build_engine.tcl (global synthesis). Server build 4.
Pre-write checks as always, plus N_ENGINES=8 read from the .hwh.

## Predictions

1. Timing: the dense P=4 N=1 build closed with the smallest margin of
   any build so far (+0.299 / +0.012, 2026-09-06, hierarchical
   synthesis; P=8 global closed at +0.101). Eight copies multiply the
   critical-path population, not its length, so WNS should stay near
   the N=1 value unless placement congestion (8 x ~5k flops) stretches
   the routes. Call: **closes, WNS between 0 and +0.3**. If it does not
   close, that is the recorded C0003 outcome for dense at 100 MHz
   (fall-back options: N=4, or a lower fabric clock for BOTH engines'
   replicated builds so the ratio stays fair).
2. Correctness: 16/16 bit-identical (instance 0 alone on the DMA).
3. Latency: **1048.9 us on every sample and on the sweep**, the N=1 P=4
   record exactly (dense is data-independent and the replicas run in
   lockstep). Any difference is a replication-wiring bug.
4. Resources: per engine ~3,000 LUT / ~5,000 FF / 4.5 BRAM tiles
   (N=1 whole design 5,760 / 8,679 / 6.5 less ~2,700 / ~3,600 / 2 for
   DMA + interconnect), so **~24-27k LUTs (45-50 % of 53,200), ~40k
   FFs (~38 %), ~38 BRAM tiles (27 %)**, DSP 0. LUTs, not BRAM, are the
   dense engine's replication budget — the mirror image of ED.
5. Server overhead ~117.5 us, unchanged.

## What would falsify

- CRC mismatch: replication wiring broke instance 0's stream.
- Latency other than 1048.9 us: replicas stalling instance 0.
- LUTs above ~30k: the per-engine LUT estimate from the P=4 N=1 report
  is wrong (the hierarchical-vs-global synthesis difference would then
  be larger than the P=8 comparison suggested).

## Outcome

(2026-09-17, 23:42; experiments/board_dense_p4_x8_20260917.md)

1. Timing: **closed at WNS +0.041 / WHS +0.034** — inside "0 to +0.3", held.
2. Correctness: **16/16 bit-identical**, 4,800 further inferences clean — held.
3. Latency: **1048.9 us on every sample and the sweep** — held exactly.
4. Resources: 27,829 LUT (52 %), 45,023 FF, **46 BRAM tiles**, DSP 0 —
   LUTs 3 % above the predicted range (below the 30k falsification line),
   BRAM 46 vs ~38 predicted: per-engine 5.5 tiles, not 4.5. Held in kind, missed in detail.
5. Server overhead 117.5 us — held.
Nothing falsified; two quantitative misses recorded.
