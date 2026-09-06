# Board pass: dense P=4 on silicon (2026-09-06) — the matched-parallelism result

Build: ENGINE=0, DENSE_P=4, BAKED_WEIGHTS=1, conv_layer_p_c1 with single-
stage weight init (commit 822990c). WNS +0.299 / WHS +0.012, all
constraints met (report 17:38; bitstream re-written 18:12 from the same
routed design). Server build 4. Pre-registered predictions:
experiments/dense_p4_prereg_20260906.md — every one held.

## Correctness

16/16 N-MNIST check samples bit-identical to the golden model (9,280
words), then 3,200 single-sample burst inferences + a 1,600-inference
sweep across all 16, zero CRC mismatches. This is also the diagnosis
of the morning's all-zero pass, confirmed by elimination: the only
change between the zero-output build and this one is the weight-ROM
initialization (two-stage -> single-stage).

## Latency (engine-only, build-4 words 8..9; 200 iterations/sample)

| sample | digit | engine us | | sample | digit | engine us |
|---|---|---|---|---|---|---|
| 0-15 | all | **1048.9** | | (identical on every sample) | | |

Mean 1048.9 us, min 1048.9, max 1048.9: **zero spread** at the global
timer's resolution. Sweep across all 16: 1048.9 us. Server overhead
117.5 us/pass (same -O0 CRC loop as the ED runs). Die 32.4-34.3 degC.

- vs cycle model 104,059 cycles = 1040.6 us: **+0.8 %**.
- Data-independence, measured: the dense walk costs the same on a
  thin digit 1 and a fat digit 8, as the design guarantees.

## The matched-parallelism comparison, both engines on silicon

Same board, same server, same 16 samples, same timer, K = P = 4:

| engine | mean | min | max | spread |
|---|---|---|---|---|
| dense P=4 | 1048.9 us | 1048.9 | 1048.9 | 1.00x |
| ED K=4 | 688.5 us | 554.8 | 815.8 | 1.47x |

**ED K=4 beats dense P=4 on C1 by 1.52x at the mean** (sim: 1.54x), and
wins on every individual sample — its worst case (815.8 us, digit 8) is
still 1.29x faster than dense; its best (554.8 us, digit 1) is 1.89x.
The crossover (~31 % input activity from the cycle model) lies above
every sample in this set; the board has not yet been driven there —
that is the M7 density sweep, which now has both endpoints measured.

Both engines' Vivado power estimates and the measured energy are still
to come (DMM requested 2026-09-06).
