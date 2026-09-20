# Silicon results ledger (2026-09-05 to 2026-09-19)

Every board pass so far, one line each, engine-only latency from the
server's global timer (words 8..9, build 4+), 100 MHz fabric, ZedBoard
XC7Z020. "Prereg" = a pre-registration file written before power-on
and its outcome. Every pass compared every output word against the
golden model; "16/16" and "8/8" mean bit-identical on the whole check
set. Power figures are Vivado estimates (experiments/power_estimates/),
NOT measurements; the meter (M5) has not arrived.

## The passes

| # | date | build (folder) | engine | dataset | N | WNS ns | correctness | engine latency | prereg | record |
|---|---|---|---|---|---|---|---|---|---|---|
| 3 | 09-05 | (GUI, m4_conv) | ED K=4 | N-MNIST | 1 | +0.508 | 16/16 | 688.5 us mean, 554.8-815.8 (1.47x) | none | board_ed_k4_20260905.md |
| 4 | 09-06 | (GUI, m4_conv) | dense P=4 | N-MNIST | 1 | +0.299 | 16/16 | 1,048.9 us flat | held 5/5 | board_dense_p4_20260906.md |
| 5 | 09-17 | ed_k8_20260917_2106 | ED K=8 | N-MNIST | 1 | +0.332 | 16/16 | 575.5 us mean, 494.1-653.1 (1.32x) | held, BRAM pred. failed | board_ed_k8_20260917.md |
| 6 | 09-17 | dense_p8_20260917_2221 | dense P=8 | N-MNIST | 1 | +0.101 | 16/16 | 540.3 us flat | held 6/6 | board_dense_p8_20260917.md |
| 7 | 09-17 | ed_k4_x8_20260917_2251 | ED K=4 | N-MNIST | 8 | +0.430 | 16/16 | = pass 3 to 0.1 us | held | board_ed_k4_x8_20260917.md |
| 8 | 09-17 | dense_p4_x8_20260917_2312 | dense P=4 | N-MNIST | 8 | +0.041 | 16/16 | 1,048.9 us flat | held (resources off) | board_dense_p4_x8_20260917.md |
| 9 | 09-18 | ed_k4_20260918_1300 | ED K=4 (C0044) | N-MNIST | 1 | +0.475 | 16/16 | = pass 3 to 0.1 us | held | board_ed_k4_c0044_20260918.md |
| 10 | 09-19 | ed_k4_dvsg_20260919_1324 | ED K=4 | DVS-Gesture | 1 | +0.190 | 8/8 | 2,970.8 us mean, 2,084.6-4,663.9 (2.24x) | held; offset basis corrected | dvsgesture/board_ed_k4_20260919.md |
| 11 | 09-19 | dense_p4_dvsg_20260919_1447 | dense P=4 (rev 3) | DVS-Gesture | 1 | +1.091 | 8/8 | 3,706.5 us flat | held 5/5 | dvsgesture/board_dense_p4_20260919.md |
| 12 | 09-19 | dense_p4_20260919_2323 | dense P=4 (rev 3) | N-MNIST | 1 | +0.768 | 16/16 | 1,048.9 us flat | (validation) | board_dense_p4_rev3_20260919.md |
| 13 | 09-20 | ed_k4_dvsg_x4_20260920_0010 | ED K=4 | DVS-Gesture | 4 | +0.119 | 8/8 | = pass 10 to 0.1 us | (replication) | dvsgesture/board_ed_k4_x4_20260920.md |
| 14 | 09-20 | dense_p4_dvsg_x2_20260920_1127 | dense P=4 (rev 3) | DVS-Gesture | 2 | +0.842 | 8/8 | 3,706.5 us flat (= pass 11) | (replication; N=4 does not place) | dvsgesture/board_dense_p4_x2_20260920.md |

Passes 1-2 (2026-08) were the loopback and the first functional engine
passes at 1.51 ms / 4.41 ms, superseded by C0030/C0035 (decisions.md).
Zero correctness misses in fourteen passes; every latency prediction
held; two resource predictions and one offset hypothesis failed and
are recorded as such.

## The two crossovers, measured

**Parallelism (N-MNIST C1, 13.6 % measured input density), matched K = P:**
(the ~31 % figure that stood here was the model-derived break-even density,
not the operating point -- corrected 2026-09-20)

| K = P | ED mean | dense | dense / ED | ED wins on |
|---|---|---|---|---|
| 4 | 688.5 us | 1,048.9 us | **1.52x** (ED) | 16 of 16 |
| 8 | 575.5 us | 540.3 us | **0.94x** (dense) | 2 of 16 |

Crossover between 4 and 8 on silicon; the cycle models put it at 7.4
(N-MNIST) and 5.8 (DVS-Gesture). The N-MNIST figure read ~6.6 until
2026-09-20; see C0049.

**Activity (DVS-Gesture C1, 8 clips, 20.9 % mean density), K = P = 4:**

| | mean | ED wins on |
|---|---|---|
| ED K=4 | 2,970.8 us (2,085-4,664) | 6 of 8 |
| dense P=4 | 3,706.5 us flat | the two densest clips |

Same parallelism, same board: the sign of the event-driven advantage
flips with input density inside one dataset.

## Cycle models vs silicon

ED = 45.2k + 90.3k/K cycles; dense = 406.9k/P + 2.3k (N-MNIST C1, wrapper-inclusive; 406.9k/P + 4 engine-only);
both transfer to DVS-Gesture with slope 0.9998. Board exceeds the
wrapper-inclusive simulation by a per-pass constant: N-MNIST ED 10.7 us
/ dense 8.3 us (872 DMA words), DVS-Gesture ED 29.4 / dense 20.0 us
(3,072 words) -- roughly 3.5 us + 5-9 ns per word (DMA + cache
maintenance). Compare board numbers only to the harness's
wrapper-inclusive total.

## Resources and estimates (single engine, N-MNIST unless noted)

| build | LUT (engine) | FF (engine) | BRAM tiles (engine) | fabric est. mW | total est. W |
|---|---|---|---|---|---|
| ED K=4 (pass 9) | ~1,150 | ~510 | 10.5 | 48 | 1.724 |
| ED K=8 | 1,161 | 377 | 11.5 | 54 | 1.731 |
| dense P=4 (pass 12) | ~3,170 | ~5,200 | 5.5 | 73 | 1.750 |
| dense P=8 | 2,799 | 5,211 | 6.5 | 83 | 1.761 |
| ED K=4 x8 | 11,733 whole | 7,539 whole | 86 whole | 241 | 1.933 |
| dense P=4 x8 | 27,829 whole | 45,023 whole | 46 whole | 501 | 2.196 |
| ED K=4 DVS-Gesture | 1,883 | 526 | 21 | 72 | 1.750 |
| dense P=4 DVS-Gesture | 7,282 | 17,081 | 9.5 | 135 | 1.814 |

PS7 (ARM) = 1.533 W in every estimate; DSP = 0 everywhere. The dense
engine's replication budget is logic; the ED engine's is block RAM.

## Engine revisions on silicon

- C0035 rev 2 (per-lane output bit files): passes 4-8, 10.
- C0044 (sweep zeroes neuron 0's input current): passes 9-12; passes
  3-8 predate it (N-MNIST results unaffected by construction; those
  bitstreams are not for other datasets).
- C0035 rev 3 (registered bit-file write): passes 11-12; required for
  dense at 16,384 neurons (rev 2: WNS -0.696), cycle counts unchanged.

## Rejected before the card (the checks that caught them)

| date | delivery | caught by |
|---|---|---|
| 09-06 | dense P=4 two-stage weight init (all zeros on silicon) | board pass, then lint added |
| 09-17 | BOOT.bin built from the previous build's bitstream | PL-partition == .xsa check |
| 09-18 | m4_conv2 bare RTL block, no clock (WNS inf) | script's unconstrained-run gate |
| 09-18 | m4_conv2 without the ZedBoard preset (DDR part wrong) | 901-parameter .hwh diff |
| 09-19 | DVS-Gesture image carrying the N-MNIST server | client's PING dataset check |
| 09-19 | dense P=4 DVS-Gesture at WNS -0.696 | script's timing gate |
