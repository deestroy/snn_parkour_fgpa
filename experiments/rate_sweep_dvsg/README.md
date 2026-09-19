# DVS-Gesture activity axis: networks trained to target firing rates (2026-09-19, MI210)

Same method as `../rate_sweep/` (N-MNIST): `03_train.py --dataset dvsgesture
--rate_target r --rate_lambda 100`, seed 0, T = 4, 30 epochs, each point
quantised and golden-checked on the 264-sample test set. Calibration (3
epochs at target 0.04, lambda 100): c1 0.053 / c2 0.054 / c3 0.079 --
the penalty lands 0.01-0.04 ABOVE target on this dataset at lambda 100
(N-MNIST landed within 0.003); the achieved rates are what is recorded.

| target | achieved c1 / c2 / c3 / fc | float | int8 | golden integer | golden - float | shifts (c1/c2/c3/fc) | max membrane | gate |
|---|---|---|---|---|---|---|---|---|
| none (seed 0, `../dvsgesture`) | .073 / .143 / .186 / .359 | 63.26 % | 65.15 % | 63.26 % | 0.00 | 7/7/8/8 | fc 16 bits (60 %) | pass |
| 0.02 | .032 / .032 / .034 / .300 | 63.26 % | 64.39 % | 62.12 % | -1.14 pp | 6/7/7/8 | fc 14 bits | pass |
| 0.04 | .050 / .051 / .050 / .344 | 64.39 % | 65.53 % | 64.77 % | +0.38 pp | 6/7/7/8 | fc 14 bits | pass |
| 0.08 | .101 / .098 / .095 / .359 | 65.53 % | 64.02 % | 62.12 % | -3.41 pp | 7/8/8/8 | fc 15 bits | FAIL (accuracy) |
| 0.16 | .206 / .194 / .190 / .366 | 65.53 % | 65.53 % | 65.15 % | -0.38 pp | 6/7/8/8 | fc 16 bits (62 %) | pass |
| 0.30 | .342 / .376 / .354 / .369 | 66.29 % | 65.91 % | 66.67 % | +0.38 pp | 6/8/8/8 | **fc 17 bits: -49,002, DOES NOT FIT** | FAIL (membrane) |

## Seeds (2026-09-19, seeds 1-2 added; `*_seed1*`, `*_seed2*`)

| target | float test acc, seeds 0 / 1 / 2 | mean +- sd | golden integer mean | fc |V|max as % of int16, per seed |
|---|---|---|---|---|
| 0.02 | 63.3 / 63.6 / 60.6 | **62.5** +- 1.7 | 60.4 | 22% / 19% / 28% |
| 0.04 | 64.4 / 63.3 / 58.7 | **62.1** +- 3.0 | 62.8 | 24% / 23% / 30% |
| 0.08 | 65.5 / 66.7 / 63.3 | **65.2** +- 1.7 | 63.1 | 38% / 39% / 50% |
| 0.16 | 65.5 / 64.0 / 67.0 | **65.5** +- 1.5 | 64.9 | 62% / 85% / 73% |
| 0.30 | 66.3 / 63.6 / 65.9 | **65.3** +- 1.5 | 65.4 | 150% / 138% / 186% |

Three seeds sharpen the one-seed reading into a step, not a slope: **the
2-5 % networks average 62.3 %, the 10-35 % networks 65.3 %** (sd 1.4-3.0 pp
per point, 264 test samples), i.e. the low-activity regime costs ~3 pp
on DVS-Gesture, and above ~10 % activity buys nothing more. The int16
verdict is now unambiguous at the top: **the 34 % network overflows the fc
membrane on all three seeds** (138-186 % of int16), while the 21 %
networks use 62-85 % -- the usable band as built is roughly 5-20 %
activity at T = 4. Golden gate failures by accuracy on 264 samples
remain frequent (6 of 15 runs) and are noise, not a bias.

## Reading it

- **Unlike N-MNIST, DVS-Gesture uses its activity a little.** Float
  accuracy rises monotonically with the achieved rate: 63.3 -> 64.4 ->
  65.5 -> 65.5 -> 66.3 % from 3 % to 34 %. The whole span (3 pp) is
  inside the T = 4 seed spread (5.3 pp), so it is a trend from one seed,
  not a measurement; but the direction is the opposite of N-MNIST's
  flat-then-falling curve, and it says the event-driven engine's easy
  regime (2-4 %) costs something here.
- **Quantisation noise is larger on this dataset**: golden - float runs
  from -3.4 to +0.4 pp (5 samples = 1.9 pp on 264). The 0.08 point fails
  the ~1 pp gate by accuracy, the 0.02 point sits at the gate's edge; on
  N-MNIST's 10,000 samples the same networks' drops were 0.0-0.1 pp.
- **The 30 % network overflows int16 in the FC layer at T = 4** (-49,002):
  the FC's input activity (c3 at 35 %) drives currents the int16 membrane
  cannot hold with k = 8. This is the same limit the T sweep found at
  T = 16 and (seed-dependently) at T = 8: the fc membrane budget is the
  binding hardware constraint on this dataset, reached by EITHER more
  timesteps or more activity. Options as before (18-bit membrane, fc
  k = 7, or stay below); none taken.
- Firing rates are per timestep over the 64x64 maps; the fc rate barely
  moves (0.30-0.37) because it is not penalised.

## Engine cycles vs activity on C2 and C3 (K = P = 4, 16 check samples, 2026-09-19)

C1's input is the data (unchanged across the sweep). C2/C3 at the
DVS-Gesture geometry (`g2`, `g3` in both runners; trace-driven like the
N-MNIST c2/c3). All 12 sweep runs + 4 baseline runs bit-identical to the
golden model. Per-sample ED cycle files `bench/ed_k4_<net>_<layer>.txt`.

### G2 (DVS-Gesture C2: 16384 input bits, 8,192 neurons; dense P=4 constant 1,212,412 cycles/sample)

| network | input rate (bench) | input spikes / sample | ED K=4 mean | min | max | spread | dense / ED |
|---|---|---|---|---|---|---|---|
| seed-0 baseline | 0.068 | 4,480 | 245,522 | 167,724 | 351,361 | 2.09x | 4.94x |
| target 0.02 | 0.031 | 1,999 | 145,136 | 120,597 | 165,740 | 1.37x | 8.35x |
| target 0.04 | 0.046 | 3,033 | 186,961 | 141,670 | 236,791 | 1.67x | 6.48x |
| target 0.08 | 0.095 | 6,252 | 317,397 | 186,454 | 504,829 | 2.71x | 3.82x |
| target 0.16 | 0.193 | 12,649 | 576,345 | 265,327 | 1,018,067 | 3.84x | 2.10x |
| target 0.30 | 0.320 | 20,980 | 912,405 | 400,269 | 1,611,806 | 4.03x | 1.33x |

Fit `ED = 64,464 + 40.4 x spikes` (max residual 0.1 %; sweep floor 2 x 8,192 x 4 = 65,536); **crossover at 28,393 input spikes per sample = 43 % input rate** (beyond the swept range; extrapolated)

### G3 (DVS-Gesture C3: 8192 input bits, 4,096 neurons; dense P=4 constant 1,196,028 cycles/sample)

| network | input rate (bench) | input spikes / sample | ED K=4 mean | min | max | spread | dense / ED |
|---|---|---|---|---|---|---|---|
| seed-0 baseline | 0.134 | 4,407 | 358,813 | 205,188 | 574,974 | 2.80x | 3.33x |
| target 0.02 | 0.032 | 1,040 | 109,021 | 79,219 | 144,188 | 1.82x | 10.97x |
| target 0.04 | 0.048 | 1,564 | 147,954 | 105,213 | 204,457 | 1.94x | 8.08x |
| target 0.08 | 0.092 | 3,018 | 255,481 | 154,885 | 390,649 | 2.52x | 4.68x |
| target 0.16 | 0.181 | 5,937 | 471,421 | 267,530 | 746,590 | 2.79x | 2.54x |
| target 0.30 | 0.349 | 11,426 | 877,602 | 483,723 | 1,414,455 | 2.92x | 1.36x |

Fit `ED = 32,222 + 74.0 x spikes` (max residual 0.2 %; sweep floor 2 x 4,096 x 4 = 32,768); **crossover at 15,727 input spikes per sample = 48 % input rate** (beyond the swept range; extrapolated)

Reading: the same shape as N-MNIST, one geometry up. Dense P=4 pays
1,212,412 / 1,196,028 cycles per sample on C2 / C3 (144 / 288 taps per
neuron), the ED engine pays per spike, so the advantage runs from 8.4x /
11.0x at ~3 % activity to 1.33x / 1.36x at 32-35 %, with fitted
crossovers at ~43 % (C2) and ~48 % (C3) input activity -- beyond every
network in the sweep, though closer than N-MNIST's 48 % / 57 % because
DVS-Gesture's per-clip spread is wider. The per-spike constants transfer
across datasets: 40.4 vs 41.0 cycles per spike on C2 and 74.0 vs 76.4 on
C3 (N-MNIST fits), intercepts on the sweep floor within 2 %. The
per-sample spread grows with activity (up to 4.0x at 32 %): the deadline
reading is worse here than the mean reading, as on C1. The int16 fc
overflow at 34 % (above) bites before the ED engine loses a conv layer. Weights `dvsg_rate<r>_int8.npz`
committed; traces local + on the AMD box (checkpoints there too).
