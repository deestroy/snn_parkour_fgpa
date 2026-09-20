# N-MNIST timestep sweep (C0023 on the primary benchmark), 2026-09-20, MI210

`train/04_pack_dataset.py --T <T>` (packed_t8 / packed_t16, deleted from the
shared box after the runs; regenerable in ~10 min per T), `03_train.py --T
<T>`, 10 epochs, 3 seeds per T; each run quantised and golden-checked on
the 10,000-sample test set. T = 4 rows from the M1 baseline and its seeds.

| T | float test acc, seeds 0 / 1 / 2 | golden integer | fc |V| range (worst seed) | share of int16 | rates c1 / c2 / c3 / fc (seed 0) |
|---|---|---|---|---|---|---|
| 4 | 96.6 / 97.0 / 97.0 (3-seed spread ~0.4 pp) | 96.75 (seed 0) | 2,850 (M1) | 9 % | .069 / .081 / .103 / .262 |
| 8 | 97.51 / 97.69 / 97.59 | 97.51 / 97.83 / 97.65 | -3,921 .. 2,194 | 12 % | .058 / .066 / .085 / .178 |
| 16 | 98.00 / 97.87 / 98.19 | 98.08 / 97.86 / 98.12 | -8,111 .. 2,622 | 25 % | .040 / .050 / .056 / .090 |

- Accuracy gains ~+0.7 pp per doubling of T (96.9 -> 97.6 -> 98.0 %), with
  the seed spread ~0.2 pp; golden integer tracks float within 0.15 pp on
  every run (15/15 gates pass).
- **The int16 ceiling does not bind N-MNIST**: the fc membrane uses 9-25 %
  of the range even at T = 16. The DVS-Gesture overflow (C0046) is a
  property of that geometry (fc fan-in 1,024 at 2x64x64 vs 256 here) and
  its activity, not of T alone.
- Per-neuron rates fall with T on every layer (fc .26 -> .09), so cycles
  per inference grow slower than T: from the C1 model, ED cost per
  inference at K=4 ~ 2NT + 76.7 s where s grows ~1.4x per doubling of T
  while 2NT doubles.

Files: `train_t<T>_seed<s>.log`, `quantise_t<T>_seed<s>.log`,
`golden_t<T>_seed<s>.log`, `m0_firing_rates_binarised_nmnist_seed<s>_t<T>.csv`,
`nmnist_t<T>_seed<s>_int8.npz`. Checkpoints on the MI210 box.
