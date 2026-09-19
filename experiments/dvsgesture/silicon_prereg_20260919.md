# Pre-registration: DVS-Gesture C1 on silicon, ED K=4 and dense P=4 (written 2026-09-19, 13:32, before either board is powered on)

Builds: ed_k4_dvsg_20260919_1324 (Build A: WNS +0.190 / WHS +0.020 from
its summary) and the dense P=4 DATASET=1 build (Build B, not yet run).
Server build 5 with -DDATASET=1 (conv_server_g1.elf, PING word 2 = 1).
Check set: the 8 test clips of sim/vectors/axis_g1_*.hex
(host/conv_test_data_g1.npz), 1,024 words in and 2,048 out per
inference. The simulation side is
experiments/dvsgesture/latency_prereg_20260918.md (sims 2026-09-18);
this file pre-registers the SILICON numbers against those sims.

## Offset hypothesis, stated before the data

On N-MNIST the board exceeded simulation by a near-constant per pass:
dense +8.3 us (P=4 and P=8), ED +10.7 us (K=4 and K=8). Both stream
292 + 580 = 872 DMA words per inference. If the offset is DMA streaming
time (~10-12 ns per word plus a fixed part), DVS-Gesture's 3,072 words
put it at roughly **ED +38 us, dense +29 us**. If it is a fixed
cost it stays ~10 us. The dense build's flat number decides which.

## Predictions

1. Correctness: 8/8 bit-identical for both engines (bit-identical
   through the baked AXIS harness with the hostile handshake on
   2026-09-18). The client refuses to send anything if PING does not
   report DATASET=1.
2. ED K=4 engine-only per sample (sim cycles at 100 MHz; then with the
   streaming-offset hypothesis):

| sample | gesture | sim cycles | sim us | expected us (+38) | dense expected us | faster |
|---|---|---|---|---|---|---|
| 0 | 0 | 199079 | 1990.8 | 2028.5 | 3633.7 | ED |
| 1 | 6 | 457140 | 4571.4 | 4609.1 | 3633.7 | dense |
| 2 | 1 | 246009 | 2460.1 | 2497.8 | 3633.7 | ED |
| 3 | 7 | 242294 | 2422.9 | 2460.6 | 3633.7 | ED |
| 4 | 10 | 287286 | 2872.9 | 2910.6 | 3633.7 | ED |
| 5 | 9 | 400349 | 4003.5 | 4041.2 | 3633.7 | dense |
| 6 | 8 | 229120 | 2291.2 | 2328.9 | 3633.7 | ED |
| 7 | 2 | 241037 | 2410.4 | 2448.1 | 3633.7 | ED |

   Mean **2878 us** sim, **~2916 us** expected; range 1991-4571 us
   (spread **2.30x**; sample 0 fastest, sample 1 slowest).
3. Dense P=4: **3604 us** sim, **~3634 us** expected, identical on all 8.
4. Verdict at K = P = 4 on DVS-Gesture: **ED 1.25x at the mean; dense
   wins on the densest clips** — the activity crossover inside one
   dataset that the sims showed, now on silicon: ED wins 6 of 8.
5. Resources: ~4x the N-MNIST membrane/output memory (16,384 neurons):
   ED K=4 roughly 40-50 BRAM tiles, dense P=4 roughly 20-25; DSP 0.
6. Server overhead per pass above 117.5 us (the -O0 CRC loop now covers
   2,048 words instead of 580: expect ~400 us); irrelevant to the
   engine numbers (words 8..9).

## What would falsify

- Any CRC mismatch: a DATASET=1-specific silicon bug simulation did
  not see (geometry, threshold 128, the g1 tables).
- Per-sample ED latency more than 3 % off after subtracting whichever
  offset the dense build shows: the cycle model does not transfer to
  the second dataset on hardware.
- Dense spread above the timer's resolution: data dependence leaked.
- ED winning on every sample, or losing at the mean: the sim verdict
  does not transfer.

## Outcome

(to be filled in after the passes)
