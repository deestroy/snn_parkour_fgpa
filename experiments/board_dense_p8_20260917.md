# Board pass: dense P=8 on silicon (2026-09-17) — the K = P = 8 verdict

Build: ENGINE=0, DENSE_P=8, BAKED_WEIGHTS=1, N_ENGINES=1, built by
host/vivado/build_engine.tcl with global synthesis
(builds/dense_p8_20260917_2221; bitstream 2026-09-17 22:25:34; WNS
+0.101 / WHS +0.020, timing report dated 22:25:50, same run). Server
build 4. Pre-registered: experiments/dense_p8_prereg_20260917.md
(commit 7e5e4d1, before power-on) — every prediction held.

## Correctness

PING build 4. 16/16 N-MNIST check samples bit-identical to the golden
model (9,280 words). Then 200-iteration bursts on every sample (3,200
inferences) and a 1,600-inference sweep across all 16: zero CRC
mismatches. First silicon pass of the P=8 configuration.

## Latency (engine-only, build-4 words 8..9; 200 iterations/sample)

**540.3 us on every one of the 16 samples**, and 540.3 us on the sweep.
Spread zero at the timer's resolution. Server overhead 117.5-117.6 us.
Die 36.5-38.0 degC.

- vs cycle model 53,195 cycles = 531.95 us: **+1.57 %**, i.e. +8.35 us.
- vs the pre-registered ~543 us (model + ~11 us offset): -0.5 %.
- The per-pass offset is engine-specific, not universal: dense P=4 was
  +8.3 us (1048.9 - 1040.6), dense P=8 +8.35 us; ED K=4 +10.9, ED K=8
  +10.9. Two constants, each stable across its own parallelism sweep;
  the ~2.5 us difference sits in the ED wrapper's start/finish path.
  Use +8.3 (dense) and +10.9 (ED) from here on. (Corrected 2026-09-20: the
+10.5 came from the rounded 678 us rather than the cycle file's 677.56; both
ED offsets are 10.89 us.)

## The K = P = 8 comparison, both engines on silicon

Same board, same server, same 16 samples, same timer:

| engine | mean | min | max | spread |
|---|---|---|---|---|
| dense P=8 | **540.3 us** | 540.3 | 540.3 | 1.00x |
| ED K=8 | 575.5 us | 494.1 | 653.1 | 1.32x |

dense / ED = **0.939x — dense wins at the mean by 6.1 %** (simulation
said 0.94x). Per sample:

| sample | digit | dense P=8 us | ED K=8 us | faster |
|---|---|---|---|---|
| 0 | 0 | 540.3 | 589.4 | dense |
| 1 | 0 | 540.3 | 620.5 | dense |
| 2 | 0 | 540.3 | 610.7 | dense |
| 3 | 0 | 540.3 | 586.9 | dense |
| 4 | 0 | 540.3 | 554.2 | dense |
| 5 | 1 | 540.3 | 494.1 | ED |
| 6 | 2 | 540.3 | 597.6 | dense |
| 7 | 3 | 540.3 | 553.5 | dense |
| 8 | 3 | 540.3 | 576.4 | dense |
| 9 | 3 | 540.3 | 567.4 | dense |
| 10 | 6 | 540.3 | 560.0 | dense |
| 11 | 7 | 540.3 | 524.5 | ED |
| 12 | 7 | 540.3 | 548.7 | dense |
| 13 | 7 | 540.3 | 553.1 | dense |
| 14 | 8 | 540.3 | 653.1 | dense |
| 15 | 8 | 540.3 | 618.4 | dense |

ED wins 2 of 16 (the thin digit 1 and one digit 7), dense the other
14. Exactly the pre-registered split.

## What this settles

With K = P = 4 (ED 1.52x, 2026-09-06) and K = P = 8 (dense 1.065x,
tonight), the **parallelism crossover on C1 at this activity lies
between 4 and 8 on silicon**, consistent with the cycle-model estimate
of K = P ~ 6.6 (experiments/latency_sim/ksweep_c0035). Both fitted
models (ED 45.2k + 90.3k/K, dense 407.2k/P + 2.0k) now have two silicon
points each, all within 2 % after their per-engine offsets. This is the
latency half of the M7 result: the event-driven design's advantage is
a function of how much parallelism the dense design is given, not a
constant, and at C1's 13.6 % activity it is gone by P = 8. (Corrected
2026-09-20: ~31 % is the model-derived break-even density, not C1's activity.) The energy
half waits on the meter.

## Resources (utilization_hier.rpt, Date Thu Sep 17 22:25:50 2026, routed)

| | dense P=8 | dense P=4 (2026-09-06) |
|---|---|---|
| LUTs, whole design | 5,362 (5,148 logic, 16 LUTRAM, 198 SRL) | 5,760 |
| Registers | 8,809 | 8,679 |
| Block RAM tiles (RAMB36 + RAMB18/2) | 2 + 13/2 = **8.5** | 6.5 |
| DSP | 0 | 0 |

Caveat: this build synthesised globally (synth_checkpoint_mode None),
the P=4 build hierarchically; global synthesis optimises across the
block boundary, so the LUT columns are not strictly like for like. BRAM
is mode-independent: +2 tiles for doubling P (rounding, as at K=8).
Engine-level rows, same report — the like-for-like comparison of the two
engines at matched parallelism (the DMA and interconnect are common):

| | dense P=8 engine (conv_layer_p_c1) | ED K=8 engine (ed_conv_layer + scatter + lif) |
|---|---|---|
| LUTs | 2,799 (all logic, 0 LUTRAM) | 1,161 (765 logic + 396 LUTRAM) |
| Registers | 5,211 | 377 |
| Block RAM | 13 RAMB18 = 6.5 tiles | 5 RAMB36 + 13 RAMB18 = 11.5 tiles |
| DSP | 0 | 0 |
| wrapper (axis_conv, g_rep[0].core) | 36 LUT, 127 FF | 105 LUT, 123 FF |

The dense engine spends its area in flops (its eight MAC lanes, their
accumulators and the per-lane output bit files) and 2.4x the LUTs; the
ED engine spends its area in block RAM (per-bank membrane and input-
current memories plus the baked weight ROMs). Neither uses a DSP. The
remaining ~2,500 LUTs of the design are the DMA and AXI interconnect in
both builds. These are static-power-relevant differences the meter will
see (M5), not just latency ones.

## Raw client lines

```
[board] PING ok: build 4, cap 65535 words
  sample  0 (digit 0): ok
  sample  1 (digit 0): ok
  sample  2 (digit 0): ok
  sample  3 (digit 0): ok
  sample  4 (digit 0): ok
  sample  5 (digit 1): ok
  sample  6 (digit 2): ok
  sample  7 (digit 3): ok
  sample  8 (digit 3): ok
  sample  9 (digit 3): ok
  sample 10 (digit 6): ok
  sample 11 (digit 7): ok
  sample 12 (digit 7): ok
  sample 13 (digit 7): ok
  sample 14 (digit 8): ok
  sample 15 (digit 8): ok

BOARD PASS: 16 samples, 9280 words, bit-identical to the golden model (4.90 s, 306 ms/sample incl. UART)
M4's done-when is met: correct results back from real hardware.
[board] BURST sample 0: 200 iterations in 0.132 s -> 657.9 us/inference (1520 inf/s), 0 mismatches, crc 8c0547d6  [engine 540.3 us + server 117.6 us]  die 36.5->36.6 degC
[board]   wall-clock 0.138 s vs board 0.132 s (tick-rate cross-check; wall includes UART overhead)
[board] BURST sample 1: 200 iterations in 0.132 s -> 657.9 us/inference (1520 inf/s), 0 mismatches, crc 64496222  [engine 540.3 us + server 117.5 us]  die 37.1->37.3 degC
[board] BURST sample 2: 200 iterations in 0.132 s -> 657.9 us/inference (1520 inf/s), 0 mismatches, crc eb268d5e  [engine 540.3 us + server 117.6 us]  die 37.1->37.4 degC
[board] BURST sample 3: 200 iterations in 0.132 s -> 657.9 us/inference (1520 inf/s), 0 mismatches, crc 59cf14da  [engine 540.3 us + server 117.6 us]  die 37.1->37.4 degC
[board] BURST sample 4: 200 iterations in 0.132 s -> 657.9 us/inference (1520 inf/s), 0 mismatches, crc fed59c62  [engine 540.3 us + server 117.6 us]  die 37.1->37.3 degC
[board] BURST sample 5: 200 iterations in 0.132 s -> 657.9 us/inference (1520 inf/s), 0 mismatches, crc 27180e7b  [engine 540.3 us + server 117.6 us]  die 37.3->37.4 degC
[board] BURST sample 6: 200 iterations in 0.132 s -> 657.9 us/inference (1520 inf/s), 0 mismatches, crc 7d47a3f4  [engine 540.3 us + server 117.6 us]  die 37.3->37.5 degC
[board] BURST sample 7: 200 iterations in 0.132 s -> 657.9 us/inference (1520 inf/s), 0 mismatches, crc 9e652337  [engine 540.3 us + server 117.6 us]  die 37.5->37.4 degC
[board] BURST sample 8: 200 iterations in 0.132 s -> 657.9 us/inference (1520 inf/s), 0 mismatches, crc a7fa0875  [engine 540.3 us + server 117.6 us]  die 37.4->37.5 degC
[board] BURST sample 9: 200 iterations in 0.132 s -> 657.9 us/inference (1520 inf/s), 0 mismatches, crc dd2a4b20  [engine 540.3 us + server 117.6 us]  die 37.5->37.6 degC
[board] BURST sample 10: 200 iterations in 0.132 s -> 657.9 us/inference (1520 inf/s), 0 mismatches, crc 583bccab  [engine 540.3 us + server 117.6 us]  die 37.6->37.7 degC
[board] BURST sample 11: 200 iterations in 0.132 s -> 657.9 us/inference (1520 inf/s), 0 mismatches, crc a59c6c4c  [engine 540.3 us + server 117.6 us]  die 37.6->37.6 degC
[board] BURST sample 12: 200 iterations in 0.132 s -> 657.9 us/inference (1520 inf/s), 0 mismatches, crc 89f456f7  [engine 540.3 us + server 117.6 us]  die 37.5->37.7 degC
[board] BURST sample 13: 200 iterations in 0.132 s -> 657.9 us/inference (1520 inf/s), 0 mismatches, crc 04e329e3  [engine 540.3 us + server 117.6 us]  die 37.6->37.6 degC
[board] BURST sample 14: 200 iterations in 0.132 s -> 657.9 us/inference (1520 inf/s), 0 mismatches, crc 4aa3061e  [engine 540.3 us + server 117.6 us]  die 37.6->37.7 degC
[board] BURST sample 15: 200 iterations in 0.132 s -> 657.9 us/inference (1520 inf/s), 0 mismatches, crc 89e867eb  [engine 540.3 us + server 117.6 us]  die 37.7->37.8 degC
[board] BURST sample 0: 1600 iterations in 1.053 s -> 657.9 us/inference (1520 inf/s), 0 mismatches, crc 89e867eb  [engine 540.3 us + server 117.6 us]  die 38.0->38.0 degC
```

> **Footnote added 2026-09-20 (C0049).** The "K = P ~ 6.6" cycle-model
> figure quoted in this record is corrected to 7.4. The measured result on
> this page (dense P=8 at 540.3 us flat, beating ED K=8's 575.5 us mean by
> 1.065x) is a measurement and does not change.
