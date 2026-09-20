# C0046 option costing: FC shift k = 7 / 6 on the DVS-Gesture networks that overflow int16 (2026-09-20, MI210)

**Question.** C0046 offers three ways out of the fc int16 ceiling: (a) 18-bit
membranes (RTL change), (b) fc quantised one shift coarser (k = 7, a
quantiser option), (c) stay at T = 4 and low activity. What does (b) cost in
accuracy, and how much range does it buy? (a)'s accuracy is already known:
the golden model keeps int32 membranes and only *reports* the int16 fit, so
the golden accuracy at the chosen shift IS the accuracy a wider membrane
would give.

**Method.** Every DVS-Gesture checkpoint that overflowed or came within 5 %
of int16 (T = 16 seeds 1-2, T = 8 seeds 1-2, the 34 %-activity T = 4 network
seeds 0-2; the T = 8/16 seed-0 checkpoints were not retained) was
requantised with `train/05_quantise.py --fixed_k c1,c2,c3,FC` holding the
conv shifts at their chosen values and setting FC to 7 and to 6, then
golden-checked over the full 264-sample test set. `run.sh` is the exact
chain; `quantise_*.log` / `golden_*.log` are its outputs; the `*_int8.npz`
weight files are the requantised networks.

| network | fc max\|w\| | k = 8 (chosen): acc / fc range | k = 7: acc / fc range | k = 6: acc / fc range |
|---|---|---|---|---|
| T=16 seed 1 | 0.336 | 70.45 % / 98 % of int16 | 70.45 % / 49 % | 69.70 % / 25 % |
| T=16 seed 2 | 0.347 | 69.32 % / **121 %** (overflow) | 67.80 % / 60 % | 68.56 % / 30 % |
| T=8 seed 1 | 0.339 | 64.39 % / **101 %** (overflow) | 65.15 % / 50 % | 64.02 % / 25 % |
| T=8 seed 2 | 0.346 | 64.77 % / 95 % | 64.77 % / 47 % | 63.64 % / 23 % |
| T=4, 34 % activity, seed 0 | 0.362 | 66.67 % / **150 %** (overflow) | 66.29 % / 75 % | 66.67 % / 38 % |
| T=4, 34 % activity, seed 1 | 0.363 | 64.39 % / **138 %** (overflow) | 64.39 % / 69 % | 65.15 % / 35 % |
| T=4, 34 % activity, seed 2 | 0.370 | 65.15 % / **186 %** (overflow) | 67.05 % / 93 % | 65.53 % / 47 % |

Weight clipping at k = 7 and k = 6: **0.000 %** on every network (fc
max|w| <= 0.37 < 127 x 2^-7 = 0.99). `choose_k` picks k = 8 because it is
the *largest* shift with no clipping; k = 7 only loses one bit of weight
resolution (rms rounding error 2.25e-3 vs 1.13e-3).

**Reading.**

- **(b) costs nothing measurable.** Over the seven networks the k = 7
  accuracy moves by -1.5 to +1.9 pp against k = 8, mean +0.1 pp; one test
  sample is 0.38 pp, and the seed spread at fixed T is 1-5 pp. k = 6 is
  the same story (mean -0.3 pp).
- **(b) halves the range per step, exactly as expected:** fc use falls
  from 95-186 % to 47-93 % at k = 7 and to 23-47 % at k = 6. Every
  network that overflowed fits at k = 7; the worst (T = 4 at 34 %
  activity, seed 2) sits at 93 %, so k = 7 alone does not cover T = 8 at
  34 % activity -- k = 6 does (47 %).
- **(a) vs (b):** the k = 8 column *is* option (a)'s accuracy. It is not
  better than (b): 18-bit membranes buy no accuracy here, only the
  freedom to keep the finer weight grid, which the accuracy does not
  reward at this network size.
- **Recommendation for the decision (still the user's call):** option
  (b) with the FC shift chosen as `min(choose_k, 7)` for DVS-Gesture
  (k = 6 if T x activity is to exceed ~2.4), recorded as a quantiser
  default per dataset; no RTL change, no re-verification of the engines
  (the fc layer's threshold is a parameter of the golden check and of the
  FC RTL, nothing in the conv engines moves). The T x activity usable
  band becomes ~2.4 at k = 7 and ~4.8 at k = 6 instead of ~1.2.

**Caveats.** Accuracy on 264 test samples; two seeds at T = 8/16 (seed 0's
checkpoints were not retained -- a rerun would take ~20 min per seed on
the MI210); the conv layers are untouched, and their ranges (9-28 % of
int16) did not change. The recommendation is a tool result, not a board
result: the FC layer has not been on silicon (C0015).
