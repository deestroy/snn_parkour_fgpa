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

## Matched parallelism, K = P, dense P=2/8/16 added (same evening)

Dense P=2, 8, 16 run through the same harness (bit-identical at each P;
`dense_p<P>.txt`). Dense is exactly data-independent at every P.

| K = P | ED mean | ED min-max | dense | dense / ED |
|---|---|---|---|---|
| 1 | 135,520 | 90,793-178,101 | 409,243 | 3.02x |
| 2 | 90,344 | 66,521-113,029 | 205,787 | 2.28x |
| **4** | **67,756** | 54,385-80,493 | **104,059** | **1.54x** (silicon: 1.52x) |
| 8 | 56,464 | 48,317-64,225 | 53,195 | 0.94x — dense wins |
| 16 | 50,822 | 45,301-56,091 | 27,763 | 0.55x — dense wins |

Dense fits 407.2k/P + 2.0k; ED fits 45.2k + 90.3k/K. Equating them puts
the **parallelism crossover at K = P ~ 6.6** for C1 at this activity —
between the 4 (ED wins on every sample) and 8 (dense wins at the mean;
ED's best sample, 48,317, still beats dense's 53,195) that we can build.
The mechanism: dense parallelism divides ALL its work; ED parallelism
divides only the scatter, never the neuron sweep. At high parallelism the
dense engine's "wasted" work is cheap enough that ED's fixed sweep cost
dominates — on a layer with 18 taps per neuron. C2/C3 (147/291 taps) push
this crossover far to the right; the fan-in dependence is the layer-level
story already in D0026/C0037. Silicon has K = P = 4 only; a K = P = 8
board pair would bracket the crossover and is a candidate for the
C0003/C0025 build slot.
