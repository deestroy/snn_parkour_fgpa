# Pre-registration: the energy-versus-K sweep (C0025), written 2026-09-20

Written before any of the new bitstreams exist and before the meter is in
hand, so the answer cannot be shaped after the fact (CLAUDE.md M7: "Do not
tune the experiment to produce a preferred answer"). Instrument, wiring,
repeats, statistics, drift and resolvability flags are **inherited unchanged**
from `measure/metering_prereg_2026-09-19.md` sections 1 and 3; only what is
specific to this experiment is fixed here. Deviations during the session are
recorded as deviations.

---

## 1. The question

The event-driven engine's bank count K is a free parameter. Latency falls with
K, with diminishing returns, because only the scatter term divides by K while
the sweep floor does not. Every doubling of K adds bank ports, adders and
block RAM, all of which cost power whether or not they are busy.

**Does the energy-optimal K differ from the latency-optimal K?**

D0017 and C0025 say it should, and say so for a mechanical reason rather than
a hopeful one: latency improves sub-linearly in K while the static cost grows
roughly linearly in K. If that is right, energy per inference has an interior
minimum and the fastest configuration is not the most efficient one. That is a
clean design result and it is quotable either way.

It also tests something sharper. The three energy quantities of C0038 need not
have the same optimum, because the always-on processor subsystem is roughly
thirty times the fabric's power. If the fabric-level optimum is interior and
the board-level optimum is at the largest K, then **the answer to "what is the
most efficient K" depends entirely on where you put the probe** — which is the
thesis's own argument, turned on its own design.

## 2. What is already known (no new measurement)

Latency per K, 16 N-MNIST check samples, C1, 100 MHz. Simulated totals from
`experiments/latency_sim/ksweep_c0035/`; the two board figures are
engine-only, from passes 3 and 5.

| K | sim total (us) | sim engine-busy (us) | board engine-only (us) | BRAM tiles, whole design | fabric estimate (mW) |
|---|---|---|---|---|---|
| 1 | 1,355.2 | 1,336.4 | -- | -- | -- |
| 2 | 903.4 | 884.6 | -- | -- | -- |
| 4 | 677.6 | 658.7 | **688.5** | **12.5** | **48** |
| 8 | 564.6 | 545.7 | **575.5** | **13.5** | **54** |
| 16 | 508.2 | 489.3 | -- | -- | -- |

Fitted: `ED cycles = 45,172 + 90,347 / K`. Board minus simulated total is
+10.9 us at K = 4 and +10.8 at K = 8, so board latency at an unbuilt K is
predicted as **sim total + 10.9 us**. Only two fabric estimates exist, and
both are vectorless Vivado numbers whose spread across implementation
strategies is about 9 mW on this engine (C0019), which is larger than the
gap between K = 4 and K = 8. That is precisely why this question needs a
meter and not another estimate.

## 3. Bitstreams to build (priority order)

All ED, N-MNIST, BAKED_WEIGHTS=1, DATASET=0, 100 MHz, WNS >= 0 or the card is
not written. `N_ENGINES` is the replication count (written R in the thesis).

| # | build | R | why | status |
|---|---|---|---|---|
| 1 | ED K=16, R=1 | 1 | the far end of the axis; without it there is no sweep | to build |
| 2 | ED K=1, R=1 | 1 | the near end; the pure sweep-floor case | to build |
| 3 | ED K=16, R=max that fits | 8, else 4 | per-engine subtraction at the far end | to build |
| 4 | ED K=8, R=max that fits | 8, else 4 | per-engine subtraction at K=8 | to build |
| 5 | ED K=2, R=1 | 1 | fills the curve between 1 and 4 | to build |
| 6 | ED K=4, R=1 | 1 | **exists**: `ed_k4_20260918_1300` | archived |
| 7 | ED K=8, R=1 | 1 | **exists**: `ed_k8_20260917_2106` | archived |
| 8 | ED K=4, R=8 | 8 | **exists**: `ed_k4_x8_20260917_2251` | archived |

C0025 asks for at least K in {1, 4, 16}; builds 1, 2 and the archived K=4
satisfy that minimum, and 3-5 complete the curve. **If build time is short,
stop after 1-3**: K in {1, 4, 8, 16} with one replicated pair at each end is
enough to locate an interior minimum or rule one out.

Every build is a fresh scripted run with parameter read-back, and every card
goes through the pre-write checklist and the PING build check, exactly as the
fourteen existing passes did. A correctness pass (16/16 bit-identical) is
required before any bitstream is metered; an engine that is wrong is not
interesting for its power.

## 4. Predictions, fixed now

Written as falsifiable statements with the number that would refute each.

**K1. Latency.** Board engine-only latency at K = 16 is **519 +- 8 us** and
at K = 1 is **1,366 +- 15 us** (sim total + 10.9). *Refuted if* either lands
outside its interval, which would mean the fitted cycle model does not
extrapolate past the built range.

**K2. Fabric power grows with K, and roughly with bank count.** Two
candidate laws fit the only two points available: +6 mW per doubling (power
in log K) predicts 36 / 42 / 48 / 54 / 60 mW at K = 1 / 2 / 4 / 8 / 16;
+1.5 mW per bank (power in K) predicts 43.5 / 45 / 48 / 54 / 66 mW. I
pre-register the **per-bank law** as the more physical one and therefore
**66 mW at K = 16 and 43.5 mW at K = 1**, measured as fabric delta.
*Refuted if* the measured K = 16 fabric delta is below 60 mW, which would put
the per-doubling law ahead and mean the bank hardware is largely idle.

**K3 (the headline). The energy-optimal K is smaller than the
latency-optimal K.** With K2's per-bank law and K1's latencies, fabric energy
per inference is predicted as:

| K | predicted latency (us) | predicted fabric (mW) | predicted fabric energy (uJ) |
|---|---|---|---|
| 1 | 1,366 | 43.5 | 59.4 |
| 2 | 914 | 45 | 41.1 |
| 4 | 688.5 | 48 | 33.0 |
| 8 | 575.5 | 54 | 31.1 |
| 16 | 519 | 66 | 34.3 |

So the predicted fabric-energy optimum is **K = 8**, the predicted
latency optimum is **K = 16**, and the curve between 4 and 16 is shallow —
a 10 % band. *Refuted if* the measured fabric energy is monotonically
decreasing through K = 16 (no interior optimum), which is the outcome C0025
expects not to see. **I am pre-registering that this prediction is at real
risk:** the K = 4 to K = 8 gap in the table is 6 %, comparable to the
measurement's own expected spread, so "flat between 4 and 16, optimum not
resolvable" is a likely and publishable third outcome. It will be reported as
such rather than forced into a minimum.

**K4. The board-level optimum is at the largest K, and differs from the
fabric-level one.** With the processor subsystem at about 1.533 W, whole-board
energy per inference is predicted to fall monotonically: 2,143 / 1,440 /
1,089 / 913 / 830 uJ at K = 1 / 2 / 4 / 8 / 16. *Refuted if* the board-level
curve has an interior minimum too. If K3 and K4 both hold, the sentence the
thesis gets is: **on this board the most efficient event-driven configuration
is K = 8 if you measure the datapath and K = 16 if you measure the board,
and neither is wrong — they answer different questions** (C0038).

**K5. Resources.** BRAM for the whole design is predicted at 11.5 / 12 /
12.5 / 13.5 / 15.5 tiles at K = 1 / 2 / 4 / 8 / 16 (the engine alone is 10.5
tiles at K = 4, from the x8 subtraction). LUTs at K = 16 are predicted between
4.5k and 5.5k against 3.4k at K = 4. *Refuted if* K = 16 exceeds 17 tiles or
6k LUTs, which would say the bank hardware scales worse than the two built
points suggest.

**K6. Replication fit.** K = 8 fits at R = 8 (predicted 94 tiles); K = 16
fits at R = 8 only marginally (predicted 110 tiles) and is expected to be
**built at R = 4** if the placer refuses, exactly as the dense DVS-Gesture
build did. *Refuted if* K = 16 places at R = 8 with WNS >= 0.

**K7. Single-engine resolvability.** A single engine's input delta is
predicted at 4.3 to 6.5 mA across the K range (fabric mW / 0.85 / 12 V),
against the shunt method's 0.1 mA resolution. *Refuted if* any single-engine
delta fails the resolvability flag (delta < 3 SEM), in which case only the
replicated per-engine numbers are reported and that failure is itself the
C0003 result.

## 5. Decision rules, fixed now

- **"Energy-optimal K"** means the K minimising measured fabric energy per
  inference, with its interval. If two K values' intervals overlap, the
  optimum is reported as a range, not a point, and K3 is scored as "not
  resolved" rather than confirmed or refuted.
- **Measured beats predicted, always.** Where a measured latency exists it is
  used in the energy arithmetic; predicted latencies are used only for K
  values whose board pass has not happened.
- **Per-engine power** comes from the replicated-minus-single subtraction at
  that same K, never from a different K's subtraction.
- **No bitstream is dropped for being inconvenient.** A build that fails
  timing, fails to place, or fails its correctness pass is reported with the
  reason, and the curve is drawn with the gap visible.
- The three energy quantities are reported in three separate rows and never
  merged (C0038).

## 6. Threats specific to this experiment

- **The fabric deltas are small and close together.** The whole K = 4 to
  K = 16 range spans about 18 mW, while placement alone moves the tool's
  estimate by about 9 mW at fixed RTL (C0019). The meter does not share that
  particular weakness, but it has drift; hence idle-before and idle-after per
  run, three runs, and randomised order.
- **Different K values are different bitstreams**, so bitstream-to-bitstream
  variation is confounded with K. The C0019 strategy variants at K = 4 bound
  that confound, and prediction P9 of the metering pre-registration measures
  it directly. If the measured strategy spread at fixed K turns out to be
  comparable to the K-to-K differences, K3 cannot be answered with single
  builds per K and the honest report says so.
- **One layer, one dataset, one clock.** This is C1 on N-MNIST at 100 MHz.
  The sweep floor fraction differs by layer (C2 and C3 have far more taps per
  neuron), so the optimum K is expected to move right on those layers; that
  is stated as an expectation, not measured here.
- **Temperature.** Higher K runs finish sooner and dissipate differently;
  die temperature is logged with every reading and reported beside the deltas.

## 7. Deliverable

A table of K against measured fabric energy, board energy, latency, BRAM and
LUTs, with intervals; the optimum identified per energy quantity or declared
unresolved; K1 to K7 scored as held, refuted or not resolved; and a figure of
energy against K with the latency curve behind it. The figure generator gains
a function reading `measure/` logs, so the plot is drawn from data rather than
transcribed. Outcomes are appended to this file and never edited into it.
