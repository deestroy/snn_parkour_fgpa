# Pre-registration: dense P=8 first silicon pass (written 2026-09-17, 22:41, before power-on)

Written BEFORE the board is powered on the P=8 image (CLAUDE.md M7).
Same discipline as dense_p4_prereg_20260906.md and
ed_k8_prereg_20260917.md.

Build under test: ENGINE=0, DENSE_P=8, BAKED_WEIGHTS=1, N_ENGINES=1,
built by host/vivado/build_engine.tcl with global synthesis
(synth_checkpoint_mode None) and the C0044 ed_conv_layer.v in the
project (the dense engine does not use that file's sweep, but the
project now carries it). Bitstream header 2026-09-17 22:25:34. Server
build 4. Pre-write checks: .hwh ENGINE=0 DENSE_P=8 ED_K=4 BAKED=1
N_ENGINES=1, MT41J128M16, HP0=1, three MEMRANGEs, BOOT.bin PL partition
byte-equal to the .xsa bitstream, bitstream differs from the K=8 build.
WNS +0.101 / WHS +0.020 (summary.txt of the run, transcribed 22:42 before the card write).

Source of the predictions: experiments/latency_sim/ksweep_c0035/dense_p8.txt
(53,195 cycles, identical on all 16 samples) plus the ~11 us per-pass
offset both ED builds showed on silicon (K=4: +10.5 us, K=8: +10.9 us).

## Predictions

1. Correctness: 16/16 bit-identical (P=8 was bit-identical in the baked
   AXIS harness with the hostile handshake on 2026-09-06; P is a
   parameter of the silicon-proven P=4 RTL).
2. Engine-only latency: **~543 us** (531.95 + ~11) on every sample.
3. Spread: **zero** at the timer's resolution, as at P=4 (data-independent
   by construction). Any spread is DMA/host jitter, not the engine.
4. The K = P = 8 verdict on C1 (the point of Builds 3+4): dense P=8
   ~543 us vs ED K=8 575.5 us mean -> **dense wins at the mean by ~6 %**
   (dense/ED ~0.94x, the number on record since 2026-09-06). ED K=8
   still wins on its two fastest samples (5: 494.1 us, 11: 524.5 us) and
   loses on the other 14. Together with K = P = 4 (ED 1.52x) this puts
   the parallelism crossover between 4 and 8 on silicon, consistent
   with the cycle-model estimate of K = P ~ 6.6.
5. Server overhead ~117.5 us per pass, unchanged.
6. Resources: after the K=8 lesson (banking partitions the same bits),
   BRAM tiles near P=4's 6.5, not 2x; LUTs above P=4's 5,760 (eight MAC
   lanes and eight bank write paths); DSP 0.

## What would falsify

- Any CRC mismatch: a P=8-specific bug simulation did not see.
- Latency more than ~3 % off 543 us: the dense cycle model (407.2k/P +
  2.0k) is wrong at P=8, or the per-pass offset is not constant.
- Dense P=8 slower than ED K=8's 575.5 us mean: the crossover is above
  8, and the "dense wins at 8" prediction is retracted.
- Any spread comparable to ED's: something data-dependent in the dense
  path.

## Outcome

(2026-09-17, 22:44, same evening; experiments/board_dense_p8_20260917.md)

1. Correctness: **16/16 bit-identical**, 4,800 further inferences with zero CRC mismatches — held.
2. Engine latency: **540.3 us** vs ~543 predicted (-0.5 %; +1.6 % over raw sim) — held.
3. Spread: **zero** (540.3 on all 16 and on the sweep) — held.
4. Verdict: dense/ED = **0.939x**, dense wins at the mean by 6.1 %; ED wins samples 5 and 11 only — held, exactly as written.
5. Server overhead: **117.5 us** — held.
6. Resources: 8.5 BRAM tiles (P=4: 6.5), 5,362 LUTs, DSP 0 — held in kind (no doubling); LUT comparison clouded by the synthesis-mode change.
Nothing falsified. Crossover between K = P = 4 and 8 on silicon.

> **Footnote added 2026-09-20 (C0049).** The "K = P ~ 6.6" cycle-model
> estimate quoted in this pre-registration was an arithmetic slip; the
> correct value from the same two fits is K = P = 7.4. The prediction made
> here and its outcome are left exactly as written — the dense P=8 result
> (dense wins at K = P = 8) is unaffected, and 7.4 is still inside the
> 4-to-8 bracket this pair was built to test.
