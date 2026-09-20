# DVS-Gesture C1 latency, both engines, K = P sweep (2026-09-18)

Harness: the engine testbenches (`sim/run_ed_tb.sh g1 ed_conv_layer`
with `CYCLES=`, `sim/run_conv_p_tb.sh g1`), 8 test samples, T = 4,
THRESH = 128, 100 MHz. Engine-only cycles: the same quantity the
board's build-4 server reports in reply words 8..9. Every run
bit-identical to the golden model. Pre-registered predictions:
`../latency_prereg_20260918.md` (outcomes appended there).

## Matched parallelism, K = P

| K = P | ED mean | ED min | ED max | spread | dense (every sample) | dense / ED | ED wins on |
|---|---|---|---|---|---|---|---|
| 1 | 655,379 | 358,727 | 1,221,516 | 3.41x | 1,441,788 | 2.20x | 8/8 |
| 2 | 410,319 | 252,295 | 711,932 | 2.82x | 720,892 | 1.76x | 8/8 |
| **4** | **287,789** | 199,079 | 457,140 | 2.30x | **360,444** | **1.25x** | **6/8** |
| 8 | 226,524 | 172,471 | 329,744 | 1.91x | 180,220 | 0.80x | 1/8 |
| 16 | 195,892 | 159,167 | 266,046 | 1.67x | 90,108 | 0.46x | 0/8 |

Cycles to ms: divide by 100,000. ED K=4 = 2.88 ms mean; dense P=4 =
3.60 ms flat.

## The cycle model transfers exactly

Fit on the K means: `cycles = 165,259 + 490,120 / K`, residual 0.00 %
at every K. Decomposed:

    cycles = 2 x N x T  +  5.0 x spikes  +  71.7 x spikes / K
             (sweep)      (FIFO pump,      (scatter, spread
              131,072      K-independent)   over K banks)

Per sample at K=4 the decomposition is within 0.3 % (table below). The
same three constants reproduce the N-MNIST C1 fit (37.0k + 6.3k +
90.3k/K on 1,256 spikes/sample): the per-spike costs depend on C_OUT
(16 in both), not on the image size or the dataset. Dense is
1,441,788 / P to within 2 cycles at every P: 88.0 cycles per neuron
per inference, exactly the N-MNIST figure per neuron.

**Crossover in the parallelism dimension: K = P = 5.8** (solve
165,259 + 490,120/K = 1,441,788/K; recomputed from the files 5.76),
against 7.4 on N-MNIST (corrected 2026-09-20, C0049: that comparison said
6.6 until then). The
board pair at K = P = 8 (Builds 3-4) still brackets it.

## The activity crossover, on real data, per sample

| sample | input spikes | input density | ED K=4 cycles | dense P=4 / ED |
|---|---|---|---|---|
| 0 | 2,955 | 9.0 % | 199,079 | 1.81x |
| 6 | 4,280 | 13.1 % | 229,120 | 1.57x |
| 3 | 4,830 | 14.7 % | 242,294 | 1.49x |
| 7 | 4,801 | 14.7 % | 241,037 | 1.50x |
| 2 | 4,981 | 15.2 % | 246,009 | 1.47x |
| 4 | 6,822 | 20.8 % | 287,286 | 1.25x |
| 5 | 11,753 | 35.9 % | 400,349 | **0.90x** |
| 1 | 14,252 | 43.5 % | 457,140 | **0.79x** |

At K = P = 4 the event-driven engine beats the dense one on a sample
if and only if its input has fewer than ~10,000 spikes over T = 4,
i.e. **input density below ~30.5 %** (131,072 + 22.9 x s < 360,444).
Two of the eight gestures are denser than that and lose. This is the
thesis's crossover statement, on a real dataset, in cycles: the
model-derived ~31 % from the N-MNIST era (C0037) is confirmed on data
that actually straddles it. Energy has to come from the meter (M5),
but on latency the sign of the result now flips within one benchmark.

## Honest reading

- The 2.30x per-sample spread at K=4 (predicted 1.3-1.5x from N-MNIST's
  1.47x) is the dataset, not the engine: gesture clips differ 4.8x in
  spike count (2,955 to 14,252), digits differ far less. Under a
  deadline this is the number that matters: the worst DVS-Gesture
  sample takes 4.57 ms at K=4 against dense's constant 3.60 ms.
- The prereg's ED point predictions were 5-17 % low because the
  K-independent per-spike term (5.0 cycles: the one-spike-per-two-
  cycles FIFO handoff in S_IDLE/S_FEED) was written as a vague
  "fixed ~6-8k" instead of being scaled with spikes. The fit above
  makes it explicit; the next prediction uses it.
- 8 samples, one seed of the network. The per-sample crossover is a
  statement about C1's input density, which does not depend on the
  network's weights, only on the data and the encoding (T = 4,
  binarised). More samples would sharpen the 30.5 % figure only via
  the exact cycle counts, which the fit already reproduces to 0.3 %.

Files: `ed_k{1,2,4,8,16}.txt` (`sample cycles`), `dense_p{1,2,4,8,16}.txt`
(the bench's summary line).
