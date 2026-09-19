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

Engine benches: C1's input is the data (unchanged across the sweep); the
C2/C3 benches at the DVS-Gesture geometry are not yet wired into the
runners (item 3 of the 2026-09-19 list). Weights `dvsg_rate<r>_int8.npz`
committed; traces local + on the AMD box (checkpoints there too).
