# K sweep on the current wrapper (2026-09-06) — supersedes the 2026-08-19 K axis

Harness: `sim/run_axis_tb.sh` with `ENGINE=1 K=<k> NOGAP=1 CYCLES=<file>`
— the same no-gap AXIS harness as `../rebaseline_c0035/`, on the current
engine (C0030 pipelined sweep + C0035 word-parallel wrapper), 16 check
samples, C1, 100 MHz. `ed_k<k>.txt`: `sample total engine_busy`.
Regression: the K=1 and K=4 files reproduce `../rebaseline_c0035/`
exactly, sample for sample. Bit-identical to the golden model at every K.

| K | total cycles (mean) | min | max | ms | vs dense P=4 (104,059) |
|---|---|---|---|---|---|
| 1 | 135,520 | 90,793 | 178,101 | 1.355 | 0.77x (dense wins) |
| 2 | 90,344 | 66,521 | 113,029 | 0.903 | 1.15x |
| **4** | **67,756** | 54,385 | 80,493 | **0.678** | **1.54x** (measured: 1.52x) |
| 8 | 56,464 | 48,317 | 64,225 | 0.565 | 1.84x |
| 16 | 50,822 | 45,301 | 56,091 | 0.508 | 2.05x |

Cycles saved per doubling of K: 45,177 -> 22,588 -> 11,292 -> 5,642 —
halving each step, i.e. the data fit

    cycles(K) = 45.2k + 90.3k / K          (residual < 10 cycles at every K)

exactly. The two terms are the two halves of the engine: the **scatter**
(work per spike, spread over K banks) is the 90.3k/K term; the
**K-independent floor** of ~45k is the neuron sweep (2 cycles x 4,624
neurons x 4 timesteps = 37.0k), the per-timestep epilogues, and ~2k of
wrapper. Scatter cycles per spike fall from ~74 at K=1 to ~4.6 at K=16.

## Reading it honestly

- Against dense **P=4**, larger K keeps winning (2.05x at K=16). But
  that is no longer matched parallelism. The dense engine's cost is
  ~407k/P + 2k, so dense P=16 would sit near 27-28k cycles — BELOW ED
  K=16's 50.8k. ED's floor does not shrink with K; dense's does with P.
  The matched-parallelism comparison therefore has a crossover in the
  PARALLELISM dimension as well as the activity dimension: at C1's
  activity ED wins at K=P<=4-ish and loses at K=P=16. (Dense P=8/P=16
  simulation runs would pin the exact point; not yet run.)
- K=16 also means 16 weight/membrane bank ports switching per spike:
  the energy-optimal K is expected below the latency-optimal K. That is
  C0025 (board K-energy sweep), gated on the meter.
- K=4 stays the silicon operating point: matched to dense P=4, most of
  the scatter gain captured (K 4->8 saves only 17 %), BRAM 12.5 tiles.
