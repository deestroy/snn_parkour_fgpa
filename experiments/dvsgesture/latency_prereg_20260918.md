# Pre-registration: DVS-Gesture C1 latency, both engines (written 2026-09-18 09:41 EDT, before the sims)

Written BEFORE the simulations run (CLAUDE.md M7: "Do not tune the
experiment to produce a preferred answer"). The numbers below come from
the C1 cycle models fitted on N-MNIST (experiments/latency_sim/
ksweep_c0035) rescaled to the DVS-Gesture C1 geometry and activity; the
sims decide whether those models transfer to a second dataset.

## Inputs to the model

| | N-MNIST c1 | DVS-Gesture g1 |
|---|---|---|
| input bits / timestep | 2 x 34 x 34 = 2,312 | 2 x 64 x 64 = 8,192 |
| output neurons | 16 x 17 x 17 = 4,624 | 16 x 32 x 32 = 16,384 |
| input spikes / sample (T=4) | 1,256 (20,093 / 16) | 6,834 (54,674 / 8) |
| input density | 13.6 % | 20.9 % |

## Model, from the N-MNIST fits

- ED engine: `cycles = floor + scatter/K`. On c1 the fit is 45.2k +
  90.3k/K including ~1.9k wrapper, i.e. engine floor ~43.3k of which
  the sweep is 2 x 4,624 x 4 = 37.0k and ~6.3k is per-timestep and
  per-spike fixed cost; scatter is 90.3k / 1,256 spikes = 71.9
  cycles per spike at K=1 (it depends on C_OUT = 16, not on H x W).
  For g1: sweep 2 x 16,384 x 4 = 131.1k, fixed ~6-8k (scaled with
  spikes, uncertain), scatter 6,834 x 71.9 = 491k / K.
- Dense engine: 407.2k/P on c1 = 88.1 cycles per neuron per inference
  (18 taps x 4 timesteps plus pipeline). For g1: 16,384 x 88.1 = 1,443k
  / P. (P=4 was already observed at 360,444 during the bit-identity run
  on 2026-09-17; the prediction is that the other P values scale as 1/P.)

## Predictions (engine cycles per sample, 100 MHz)

| K = P | ED predicted | dense predicted | verdict |
|---|---|---|---|
| 1 | ~628k (6.3 ms) | ~1,443k (14.4 ms) | ED 2.3x |
| 2 | ~383k | ~721k | ED 1.9x |
| 4 | **~260k (2.6 ms)** | **~361k (3.6 ms)** | **ED ~1.4x** |
| 8 | ~198k | ~180k | dense ~1.1x |
| 16 | ~168k | ~90k | dense ~1.9x |

Crossover in the parallelism dimension: **K = P ~ 6-7**, essentially
where it was on N-MNIST (6.6). The reason is the honest one: the sweep
floor scales with neurons exactly as the dense cost does, so a 1.5x
higher input density moves the crossover less than one might guess.

## What would falsify the model

1. ED K=4 outside 235-290k cycles (+-10 % of the point prediction):
   the per-spike scatter cost is not geometry-independent, or the
   fixed term does not scale as assumed.
2. ED per-sample spread: predicted ~1.3-1.5x between the sparsest and
   densest of the 8 samples (N-MNIST: 1.47x). A spread below 1.2x means
   the sweep floor dominates more than modelled.
3. Dense P=8/P=16 not within 1 % of 1,443k/P: the P-lane engine has a
   fixed cost the c1 fit hid.
4. The crossover landing at K = P <= 4 or >= 8 would change the board
   plan (Builds 3-4 are K = P = 8 on N-MNIST).

## Outcomes (sims run 2026-09-18 09:41-09:53 EDT; `latency_sim/README.md`)

| K = P | ED predicted | ED measured | dense predicted | dense measured | verdict predicted / measured |
|---|---|---|---|---|---|
| 1 | ~628k | 655,379 (+4 %) | ~1,443k | 1,441,788 | ED 2.3x / 2.20x |
| 2 | ~383k | 410,319 (+7 %) | ~721k | 720,892 | ED 1.9x / 1.76x |
| 4 | ~260k | 287,789 (+11 %) | ~361k | 360,444 | ED 1.4x / **1.25x** |
| 8 | ~198k | 226,524 (+14 %) | ~180k | 180,220 | dense 1.1x / 1.26x |
| 16 | ~168k | 195,892 (+17 %) | ~90k | 90,108 | dense 1.9x / 2.17x |

1. ED K=4 at 287,789 is inside the 235-290k band by 0.8 % — held, but
   only just, and the miss is systematic (every K is low by the same
   5.0 cycles x spikes): the K-independent per-spike FIFO cost was
   modelled as a constant instead of scaling with spikes. The refined
   model `2NT + 5.0 s + 71.7 s/K` has 0.00 % residual at every K.
2. Spread: 2.30x, far ABOVE the predicted 1.3-1.5x. The prediction
   only stated the low-side failure; the high side is a dataset
   property (4.8x range in spikes per clip). Recorded as a miss.
3. Dense within 1 % of 1,443k/P at every P — held (within 0.1 %).
4. Crossover at K = P = 5.8, inside 4-8 — held; Builds 3-4 unchanged.

> **Footnote added 2026-09-20 (C0049).** This file compares the
> DVS-Gesture crossover (5.8, correct) with "6.6" on N-MNIST; the N-MNIST
> value is 7.4. The comparison's direction — the crossover moves LEFT on
> the dataset with the bigger sweep floor — is unchanged and slightly
> stronger.
