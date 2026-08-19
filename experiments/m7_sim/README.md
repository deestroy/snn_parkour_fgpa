# M7 rehearsal in SIMULATION: latency vs C1 input firing rate (2026-08-19)

`python3 experiments/m7_sim_sweep.py` (about 2 h): synthetic Bernoulli(p)
inputs to C1 at ten densities, golden outputs, both engines through the
AXIS testbench with no gaps, per-sample cycles. `sweep.csv`, plot
`m7_sim_crossover.png`, raw vectors and counts per density.

- All 30 runs bit-identical, including 89 % input activity (the worst-case
  address list of D0016 held: 2,048 spikes/timestep against 4,096 depth).
- dense: 436,247 cycles regardless of input (data-independent).
- ED K=1: 121.9k + 75.8 cycles/spike -> crosses dense at ~45 % input rate.
- ED K=4: 121.8k + 21.9 cycles/spike -> 300.8k at 89 %: never crosses.
- Trained C1 input rate is ~6 %; there the ED engines sit at 1.2-1.5 ms
  against 4.36 ms dense.

This is latency at 100 MHz, in simulation, verified against the board to
3 % at one point (ED K=4, sample 0). It is not energy and it is not the
board. Its purpose: the shape of the M7 experiment is now known before the
meter exists, and the board runs will have a model to be checked against.
The energy curve can differ (static power of the ED design's extra BRAM
and logic vs its lower switching) -- which is the thesis question.
