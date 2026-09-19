# Pre-registration: the M5 metering session (written 2026-09-19, before any instrument is connected)

Written so the energy result cannot be shaped after the fact (CLAUDE.md
M7: "Do not tune the experiment to produce a preferred answer"; C0001-
C0004, C0013, C0018, C0038). Everything below is fixed now; deviations
during the session are recorded as deviations. Procedure details live in
`measure/dmm_protocol.md`; arithmetic and flags in `measure/manual_meter.py`
(`--selftest`), `measure/protocol.py` (`--mock`).

## 1. Instrument and wiring (decided)

- **Primary:** 0.1 ohm shunt in the +12 V lead via a barrel-jack breakout,
  meter in DC-mV mode across the shunt (200 mV range). At ~0.6 A the
  drop is ~60 mV; a 4.5-digit meter resolves 0.01 mV = 0.1 mA. Nothing
  in the supply path depends on the meter's range switch.
- **Fallback:** meter in series on its fused 10 A jack, only if it is a
  bench unit with <= 0.1 mA resolution on that range; handheld 10 mA
  resolution CANNOT resolve a single engine (see 4) and is recorded as
  such, which is the case for the INA226 (C0002).
- Supply voltage read at the barrel with the meter in V mode, once per
  session, before wiring the shunt; P = V_barrel x I; shunt loss
  (I^2 x 0.1 ohm, ~36 mW at 0.6 A) noted, not subtracted from the delta
  (it cancels in idle-minus-run to first order).
- Board thermal settling: 60 s after boot before the first idle reading;
  die temperature from the server's PING/BURST reply logged with every run.

## 2. Bitstreams and samples (the experiment matrix, in this order)

| # | bitstream | archive tag | why |
|---|---|---|---|
| 1 | ED K=4, N_ENGINES=8, N-MNIST | ed_k4_x8_20260917_2251 | the resolvable delta (C0003) |
| 2 | dense P=4, N_ENGINES=8, N-MNIST | dense_p4_x8_20260917_2312 | its dense pair |
| 3 | ED K=4, N=1, N-MNIST (C0044 build) | ed_k4 (2026-09-18) | the per-engine number, if resolvable |
| 4 | dense P=4, N=1, N-MNIST | dense_p4_20260906 | its pair |
| 5 | ED K=4, DATASET=1 (DVS-Gesture) | ed_k4_dvsg_20260919_1324 | the per-clip activity crossover in ENERGY |
| 6 | dense P=4, DATASET=1 | (rebuilding 2026-09-19) | its pair |
| 7-8 | ED K=8 / dense P=8, N-MNIST | ed_k8_20260917_2106 / dense_p8_20260917_2221 | the parallelism crossover in energy, if time |

Samples: the 16 N-MNIST check samples (BURST sweep over all 16 = the
mean over the set) and the 8 DVS-Gesture clips. For #5-6 each clip is
ALSO metered alone (single-sample BURST, C0018), so energy per inference
is a per-clip number and the ~30 % crossover can be tested in energy.
BURST length N sized to 15-30 s per window (N-MNIST ED K=4 ~12,000 x 688.5
us = 8.3 s -> use N = 24,000; dense P=4 N = 16,000; DVS-Gesture ED N =
6,000, dense N = 5,000; x8 builds same per-engine latency, same N).

## 3. Repeats and statistics (C0013)

- Per (bitstream, sample set): **3 runs**, each idle-before (5 readings, 5 s
  apart) -> BURST window (5 readings spread over it) -> idle-after (5).
- Energy per inference = V x (I_run - I_idle) x elapsed / N with the SEM
  from the readings; a run is flagged if |idle_after - idle_before| exceeds
  the delta (drift) or if the delta is < 3 SEM (unresolvable). Flagged runs
  are reported, not dropped.
- Report mean +- SEM over the 3 runs; intervals on every energy figure.
- Order randomised within the session (coin flip per pair which engine
  goes first) so thermal history is not confounded with the engine.

## 4. Predictions (from the cycle model x the tool's power estimate)

Tool estimate for ED K=4 (design_1_wrapper_power_routed.rpt, 2026-09-06):
fabric dynamic ~49 mW (clocks 16 / logic 7 / signals 10 / BRAM 16),
static 144 mW, PS7 1.533 W, total 1.727 W. Dense P=4 has no saved
report yet (requested from the board session 2026-09-19); its fabric
estimate is expected in the same tens-of-mW band.

- **P1 (resolvability).** Single engine: 49 mW fabric = 49 mW x 688.5 us
  = **34 uJ/inference** predicted from the tool; at 12 V and ~85 %
  regulator efficiency that is a **~4.8 mA** input delta -- resolvable
  with the shunt + mV method (0.1 mA), NOT with a handheld ammeter.
  x8 builds: ~390 mW, ~38 mA -- resolvable either way.
- **P2 (the sign of the crossover in energy at K=P=4, N-MNIST).** If
  energy per cycle is the same for both engines, ED wins by the latency
  ratio 1.52x. The event-driven engine has more state switching per
  cycle (K banks, FIFO, word file), so I predict the measured energy
  ratio is BELOW 1.52x: **ED wins, but by 1.1-1.4x**, not 1.52x. A ratio
  above 1.52x or below 1.0x falsifies this.
- **P3 (the estimate-measurement gap).** The tool's fabric number will
  be within a factor of 2 of the measured delta per engine
  (0.5x-2x). Outside that band is itself the C0001 result.
- **P4 (DVS-Gesture per clip).** The energy crossover sits at the same
  clips as the latency one (clips 1 and 5 lose to dense) if P2's
  energy-per-cycle penalty is under ~25 %; if the penalty is larger, one
  more clip (4, at 20.8 % density, 1.25x latency) flips to dense.
- **P5 (x8 vs x1).** Per-engine energy from the x8 build equals the x1
  number within the x1 interval (replication does not change the
  engine's cost; C0003's premise). If x8 per-engine is > 20 % below x1,
  the x1 delta was dominated by something other than the engine.
- **P6 (idle).** Idle board current 0.4-0.6 A at 12 V (PS7 + DDR +
  regulators), the same to within 2 % across bitstreams; if idle differs
  between ED and dense bitstreams by more than the engine delta, static/
  clock-tree differences are real and must be reported separately (C0038
  quantity 2 vs 3).

## 5. What is reported (C0038: never merge the three quantities)

1. System energy per inference (12 V input delta x time / N) -- the
   deployment number.
2. Engine (fabric) delta: the same measurement minus nothing else --
   stated as the delta it is; per-engine = x8 delta / 8.
3. The tool's estimate beside each, and measured/estimate as its own
   column.
Plus, per the brief's metrics rule on every table: latency, mean power,
LUT/FF/BRAM/DSP, firing rate per layer, accuracy, sim-or-board.

## 6. Session log template

Date/time, meter make/model/range, shunt value, V_barrel, room and die
temperature, bitstream tag and PING build/dataset, N, elapsed, the 15
readings per run, flags. One `measure/runs/<timestamp>_<label>.json` per
run from `manual_meter.py`; the session summary table goes in
`experiments/metering_<date>.md` next to this pre-registration.
