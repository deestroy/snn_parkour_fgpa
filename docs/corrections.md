# Corrections and gaps — methodology review, 2026-08-20
Reviewed against `docs/decisions.md` (D0001–D0024) and the project brief.
Written to be worked through by Claude Code. Each item states the problem,
why it matters to the thesis, the action, and a done-when.
Numbering is `C00NN` so it does not collide with the `D00NN` decision log.
When an item is resolved, record it as a normal dated entry in
`docs/decisions.md` — this file is a worklist, not a second source of truth.
**Priority key.** P0 = do before the meter session, or the measurement is
not defensible. P1 = do before any M7 number is written up. P2 = do before
the thesis is written. P3 = housekeeping.
---
## C0001 — Measure absolute idle power per bitstream, not only the delta (P0)
**Problem.** The protocol in D0022 and `measure/dmm_protocol.md` is
"power while running minus power while idle." Static power — leakage and
the clock tree — is present in both states and therefore **cancels out of
the delta entirely.**
**Why it matters.** The thesis argument (project brief; Minitaur's 73.8 %
clocks/IO/leakage) is that static power is exactly what operation-counting
misses. The 22:56 resource table shows the event-driven build carrying
5.5 more BRAM tiles than dense — the address list and the I banks, i.e.
the event-driven machinery itself. That cost is paid on every clock cycle
whether or not a spike arrives, and the current protocol cannot see it.
Half the thesis argument is being subtracted away.
**Action.** Measure and report two quantities per bitstream:
1. `P_idle(design)` — PL configured and clocked, DMA idle, CPU in the
   conv_server receive loop, no BURST running. Define this state once in
   `measure/dmm_protocol.md` and use it identically for both engines.
2. `ΔP(design) = P_burst − P_idle` — dynamic power attributable to running.
Both go in the results table. If `P_idle(ED) > P_idle(dense)`, that is a
result the tool cannot predict and it belongs in the abstract.
**Done when:** `measure/dmm_protocol.md` defines the idle state precisely;
both engines have `P_idle` and `ΔP` recorded with the same instrument in
the same session; the results table has separate columns for each.
---
## C0002 — Establish the noise floor before any comparison (P0)
**Problem.** No repeatability figure exists. Without one, any reported
delta is unfalsifiable.
**Why it matters.** The quantity being measured is ~25 mW on a ~5 W board.
If the baseline drifts by more than that over a measurement window, the
comparison is noise. This must be known *before* the numbers are taken,
not argued about afterwards.
**Action.**
- Measure the same bitstream twice, cold, separated by a power cycle.
- Measure the same bitstream twice within one session, separated by 10 min.
- Record the spread. That spread is the noise floor and every reported
  delta must exceed it.
- If the floor exceeds the dense-vs-ED delta, C0003 is mandatory rather
  than optional.
**Done when:** a noise-floor figure with its method is recorded in
`docs/decisions.md`, and `measure/dmm_protocol.md` requires it to be
re-measured at the start of every metering session.
---
## C0003 — Replicate the engine N times to lift the signal above drift (P0 enabler)
**Problem.** The fabric is ~31 mW on a ~1.7 W chip estimate; the
idle→burst delta is ~2.7 mA at 12 V against a ~0.5 A board baseline. The
limiting factor is not meter resolution — a 4.5-digit DMM resolves that —
it is **baseline stability** over the measurement window.
**Why it matters.** This is the difference between needing an expensive
instrument and not. Utilisation is 3.4 k of 53,200 LUTs and 13 of 140
BRAM tiles, so there is room for roughly 8 copies of either engine.
**Action.**
- Add a `N_ENGINES` parameter to `axis_conv_top.v` wrapping the engine
  instantiation in a generate loop.
- Broadcast the same input stream to all instances. Compare only
  instance 0's output against golden; the others are representative load
  and must be fed real data, not zeros or a held constant.
- Report per-engine energy as `ΔP / N`, and state N with every number.
- Check BRAM before building: ED is 13 tiles per instance against 140
  available; dense is 7.5.
**Caveat to record:** replication changes routing and clock-tree loading,
so per-engine energy at N>1 is not identical to N=1. Measure at N=1 and
at N=8 for at least one design and report the ratio, so the scaling
assumption is evidence rather than assertion.
**Done when:** both engines build at N=1 and N=8 with WNS ≥ 0; the
N=1-vs-N=8 scaling ratio is measured and recorded; the pre-write check
in `docs/decisions.md` includes N_ENGINES in the `.hwh` grep.
---
## C0004 — State the measurement boundary with every number (P0, cheap)
**Problem.** The project brief requires it and it is not yet stated.
**Action.** One sentence in `measure/dmm_protocol.md`, repeated in every
results table caption: what is inside the measured boundary (with the
meter on the 12 V input: the whole board — FPGA, DDR3, PHYs, oscillators,
regulator losses) and what that means for comparability with published
figures, which are almost always die-only tool estimates.
**Worked example to cite, and a fair one.** Harmeling et al. (*Neuromorph.
Comput. Eng.* 6, 024022, 2026) report energy per digit for an Artix-7 SNN
accelerator, derived as follows: *"the energy per digit can be estimated
from Vivado power estimation (post-implementation)... The total reported
consumption is 1.13 W (including the HUB75 display)."* Every energy figure
in their Table 3 therefore has a 32x64 LED matrix inside the measurement
boundary. This is not sloppiness — it is what happens when the boundary is
not decomposed, which is the norm. Use it as the concrete illustration of
why the boundary sentence exists, without editorialising.
Also: check the ZedBoard Rev C.1 schematic for whether VCCINT (PL core,
1.0 V) and VCCPINT (PS core) are separate nets. If separate, a shunt on
VCCINT isolates the fabric and removes the ARM from the baseline entirely
— a far better measurement than the barrel jack. If tied, the 1.0 V rail
still excludes DDR3, PHY, USB, OLED, LEDs and regulator losses. Record
the finding either way; it is a methodology decision with evidence.
**Done when:** the boundary sentence exists and is cited by every table;
the VCCINT/VCCPINT question is answered from the schematic and recorded.
---
## C0005 — Add the duty-cycle model: energy per control period, not only per inference (P1)
**Problem.** BURST runs the engine at ~100 % duty. A deployed perception
loop does not.
**Why it matters.** At 10 Hz with 1.51 ms of work the ED engine is idle
98.5 % of the time, and
```
E_period = P_idle × T_period  +  ΔP × t_active
```
At a 100 ms period and ~1.5 ms of work the static term is roughly 60× the
dynamic one. A design that wins decisively on energy-per-inference at
100 % duty can still lose over a control period if its idle draw is
higher. **That is the Loihi 2 failure mode one level down, and it is
probably where the crossover actually lives.**
**Action.**
- Add `E_period` as a reported quantity, computed from the C0001
  measurements, swept over perception rate (10 / 25 / 50 / 100 Hz).
- Plot energy per control period against perception rate for both engines,
  alongside the existing energy-per-inference plot.
- State explicitly which figure of merit the robot claim rests on.
**Done when:** the analysis script emits both figures of merit; the
duty-cycle sweep is in `experiments/`; the thesis outline names
`E_period` as the robot-facing metric.
---
## C0006 — Decide the LIF sweep skip, and pre-empt the "is this really event-driven?" attack (P1)
**Problem.** The sweep visits every neuron every timestep, 4 cycles × N,
unconditionally. At K=4 on C1 that is 18.5 k of 27.1 k cycles — **68 % of
the engine's time is dense-style work inside the event-driven design.**
**Why it matters.** This is the sharpest technical criticism available
against the architecture and it will be the first question at the defence.
It is currently filed as a "post-M7 optimisation," which understates it.
**Action.** Choose one and record the reasoning:
- **(a) Implement the skip.** A neuron can be skipped when `I == 0` and
  `V` has already decayed to 0 (integer truncation reaches 0 in finite
  steps, so this is reachable). The D0016 address-list architecture makes
  the bookkeeping feasible. Measure what fraction of the sweep survives at
  trained rates.
- **(b) Argue the floor is inherent** and quantify it: state that this is
  event-driven *synaptic* processing with a dense *neuron* update, which
  is what most accelerators in this family do, and report how much of the
  advantage survives the floor.
Either is defensible. Silence is not.
**Done when:** a `D00NN` entry states the choice with numbers, and the
thesis methodology contains the sentence that pre-empts the question.
---
## C0007 — Estimate-vs-measured is three numbers, not two (P1)
**Problem.** The Vivado figures recorded so far are marked "confidence:
medium" — the vectorless estimator, with a default toggle-rate assumption.
Comparing a vectorless estimate against a measurement partly measures the
assumption rather than the tool.
**Why it matters.** This is contribution C1 of the thesis. Doing it
properly turns one weak comparison into two strong ones.
**Action.** Produce three numbers per design:
- **(a) vectorless default** — what the literature actually reports.
- **(b) SAIF-driven** — post-implementation simulation over a
  representative window (a few timesteps of a real sample), `read_saif`,
  `report_power`.
- **(c) measured** — from C0001.
Report all three. The gap (a)→(c) is *the field's practice being wrong*.
The gap (b)→(c) is *the tool's genuine accuracy when used carefully*.
These are different findings and both are worth having.
**Done when:** all three exist for both engines; the two gaps are named
and quantified separately in the results chapter.
---
## C0008 — Report accuracy at every point of the M7 sweep (P1)
**Problem.** M7 varies firing rate, which changes accuracy. An
energy-versus-activity curve without accuracy at each point is not
interpretable — energy can always be reduced by firing less and being
wrong.
**Why it matters.** D0005 already establishes that threshold and weight
scale are a single knob, so the sweep is a controlled scale parameter —
but the accuracy consequence must travel with it.
**Action.**
- Record full-split test accuracy at every sweep point (D0009: full split,
  never `--limit`).
- Where possible, add an iso-accuracy comparison: energy for each engine
  at matched accuracy, not merely at matched activity.
**Done when:** every row of the M7 results table carries an accuracy
column, and the plot annotates it.
---
## C0009 — Log die temperature during metering (P2)
**Problem.** Leakage is exponential in temperature and nothing records it.
**Action.** Read the XADC die-temperature sensor from `conv_server.c` and
include it in the BURST reply; log it at the start and end of every
metering window.
**Why it is worth the hour.** It demonstrates the window was thermally
stable (supporting C0002), and it gives a second lever for separating
static from dynamic power if the idle-vs-delta split needs corroboration.
**Done when:** temperature appears in the BURST reply and in every logged
measurement.
---
## C0010 — State the scope of the measured claim (P2)
**Problem.** Everything on silicon is C1. The per-layer simulation shows
dense/ED ratios differing sharply by layer (2.0× / 0.8× / 0.4× at K=1),
so a whole-network figure cannot be extrapolated from C1 silently.
**Action.** Either put C2/C3/FC on the board, or state plainly in the
methodology that the measurement is C1 and that the whole-network figure
is **modelled** from measured C1 plus simulated cycle counts, with the
model's assumptions listed.
The second is legitimate. Undeclared, it is not.
**Done when:** the scope sentence exists, or the additional layers are
measured.
---
## C0011 — Build the external baseline table (P2)
**Problem.** No comparison against published accelerators exists, so the
work cannot be placed in the literature.
**Action.** Build the table from published figures — no reproduction
needed. Columns the field expects: platform, network, benchmark,
accuracy, LUT / FF / BRAM / DSP, clock, latency, throughput (FPS and
GSOP/s), power and how it was obtained, energy per inference, GSOP/W.
Rows: Cheng et al. TCAS-I 2025, Cerebron TVLSI 2022, FireFly-S,
Spiker+, **Harmeling et al. NCE 2026**, and both of ours.
Note in every row **how the power figure was obtained** — that column is
the thesis's argument in visual form, and ours will be the only measured
entry.
**Harmeling et al. is the most directly comparable row and should be
prominent.** Same FPGA family (Artix-7 XC7A200T), same clock (100 MHz),
same benchmark (MNIST), hand-written VHDL chosen over HLS for the same
reason as D0011, 4-bit weights, 96.31 % accuracy, 1.7424 ms/digit,
1.972 mJ/digit. Note their scale for context: 93,347 logic cells and 341
BRAM for 784-100-10, because each layer is fully parallelised.
**Comparability trap.** Their energy is *per digit*, where one digit is a
220-image spike train. It is not comparable to a per-inference figure at
T = 4 without normalising. If both appear in one table, normalise
explicitly and say so in the caption, or the comparison is meaningless in
your favour — which is worse than meaningless against you.
**Done when:** the table exists in `docs/` with citations, and any
cross-normalisation is stated.
---
## C0012 — Add one benchmark harder than N-MNIST (P2)
**Problem.** N-MNIST alone is the weakest evidence in this field and
reviewers discount MNIST-class results almost automatically. DVS-Gesture
is deferred on disk grounds (D0024).
**Action.** Solve the disk constraint — streamed pipeline, external
storage, or a cleared quota — and train/quantise/verify DVS-Gesture
through the existing golden-model path. The engines are geometry-clean
(D0024 addendum), so the retarget cost is parameters and vectors only.
**Done when:** DVS-Gesture accuracy and firing rates are recorded and at
least one engine is verified against golden on it.
---
## C0013 — Statistical treatment of the energy measurements (P2)
**Problem.** Latency is deterministic and single runs are fine. Energy
will not be.
**Action.** Define, before measuring: repeats per condition, what is
randomised between them, and how confidence intervals are computed.
Report intervals, not single values. Cross-reference the C0002 noise
floor.
**Done when:** the protocol is written in `measure/dmm_protocol.md` and
every energy figure carries an interval.
---
## C0014 — Characterise or remove the wrapper asymmetry (P2)
**Problem.** The AXIS wrapper's bit-serial pack/unpack is ~11 % of dense
cycles and ~26 % of ED cycles. It is shared, so it is fair — but it is
*unequally weighted*, which compresses the engine-to-engine ratio.
**Action.** Either land the word-parallel pack/unpack before M7, or
measure the wrapper's contribution separately and report engine-only
figures alongside system figures. Removing it also increases the delta
C0003 is trying to lift.
**Done when:** the wrapper contribution is either eliminated or quantified
and reported separately.
---
## C0015 — Get the event-driven FC layer onto silicon (P2)
**Problem.** FC holds 81 % of the weights (D0004) and is dense-only on the
board. D0023 verified the ED variant in simulation at K = 2…16.
**Action.** Generate the baked-weight variant, wire the selection in
`axis_conv.v`, build, verify WNS ≥ 0 and BOARD PASS, and take BURST
latency plus C0001 power for it.
**Done when:** ED FC has a sign-off-clean board pass and its own row in
the results table.
---
## C0016 — Use an unbiased sample distribution for M7 (P2)
**Problem.** The per-timestep tables use the golden traces, which D0009
established are class-ordered and on the busy side of true mean activity.
**Action.** Draw M7's samples from a seeded random subset of the full
split, as D0009 already requires for reported numbers. State the sampling
method in the results chapter.
**Done when:** M7's inputs are drawn from the unbiased distribution and
the method is documented.
---
## C0017 — Housekeeping (P3)
- The index table in `docs/decisions.md` stops at D0020; the log runs to
  D0024. Bring it current and add C-item resolutions as they land.
- D0021 lists the constant `/` and `%` in `ed_scatter` as accepted; D0020
  rev 2 removed them. Mark the D0021 note as superseded so a reader does
  not act on a stale caveat.
- The 22:56 table has a footnote saying DSP = 1 for ED with
  `use_dsp="no"` expected to make it 0. Confirm on the next build and
  update, so the "DSP = 0 for both engines" property is stated as measured
  rather than expected.
---
---
# Design review — architecture and a numerical error
Added 2026-08-20. D0028 is a correction to a published finding in the log.
D0029 is the fairness issue most likely to be attacked at a defence.
Numbered `D00NN` in the C-series style but prefixed here as design items;
renumber into your own scheme as you prefer.
---
## C0028 — The dense cost model in the M6 K=4 table is wrong for C2 and C3; a headline finding does not survive it (P0)
**Problem.** The M6 K=4 entry states *"sweep = 4 cyc/neuron, dense = 21
cyc/neuron"* and applies 21 cycles/neuron to **all three layers**:
```
C1  4,624 neurons x 21 =  97,104   <- correct
C2  2,592 neurons x 21 =  54,432   <- wrong
C3  1,600 neurons x 21 =  33,600   <- wrong
```
21 cycles/neuron is a **C1-specific** figure. C1 has `C_IN x 3 x 3 = 2 x 9
= 18` taps per neuron, so 21 cycles is 18 taps plus ~3 of overhead — one
tap per cycle, consistent with a data-independent walk of the full kernel.
But C2 has `16 x 9 = 144` taps per neuron and C3 has `32 x 9 = 288`. At one
tap per cycle those are ~147 and ~291 cycles/neuron, not 21.
**Your own later simulation confirms this and contradicts the table.**
`experiments/latency_sim/layers.md` gives dense C1/C2/C3 = 3.90 / 15.26 /
18.63 ms per sample. At 100 MHz over 4 timesteps:
```
C2: 15.26 ms -> 381k cycles/timestep    vs 2,592 x 147 = 381k   MATCH
C3: 18.63 ms -> 466k cycles/timestep    vs 1,600 x 291 = 466k   MATCH
```
So the log holds two mutually inconsistent dense figures for C2 and C3, and
the incorrect one is attached to a highlighted result.
**What does not survive.** The finding *"at K=1 the event-driven engine
LOSES to dense on C2 and C3"* — described in the log as *"the crossover the
thesis is about, already visible in RTL cycle counts"* — is an artefact of
the wrong dense column. Corrected:
| per timestep | dense (corrected) | ED K=1 | ED K=4 | dense/K1 | dense/K4 |
|---|---|---|---|---|---|
| C1 | 97,104 | 48,276 | 27,116 | 2.0x | 3.6x |
| C2 | 381,000 | 70,532 | 26,628 | **5.4x** | **14.3x** |
| C3 | 466,000 | 83,993 | 26,584 | **5.5x** | **17.5x** |
Event-driven wins on every layer at every K. There is no cycle-level
crossover in the layer dimension.
**Action.**
- Verify the tap arithmetic independently (count taps in `conv_layer.v`'s
  inner loop for each geometry, or instrument the simulation per layer).
- Correct the M6 K=4 table and **retract the finding explicitly**, in the
  style of the DDR retractions — that discipline is the most credible thing
  in the log and this is exactly the case it exists for.
- Check whether any downstream reasoning depended on it, in particular the
  D0017 note's framing of what banking buys.
**Done when:** the table is corrected, the finding is retracted with the
arithmetic shown, and the layer-level and simulation figures agree.
---
## C0029 — The dense baseline has no parallelism knob; the comparison is unfair on the axis that matters most (P0)
**Problem.** The event-driven engine has `K`, giving it K-way RMW
throughput via channel-interleaved banks. **The dense engine has no
equivalent.** It processes one tap per cycle, single-issue, always.
So the headline comparison is a **4-wide event-driven engine against a
1-wide dense engine.** D0011 rightly insists on comparison hygiene for
authorship and toolchain; D0021 rightly insists on it for the wrapper.
Parallelism is the one axis where hygiene is missing, and it is the axis a
reviewer will find first.
**Why it matters, in numbers.** A P-wide dense engine — 4 output channels
in parallel, weights and membranes banked by `oc mod P`, i.e. structurally
the same trick `ed_scatter` already uses — would give:
```
              dense P=1    dense P=4    ED K=4
C1              97,104       24,276     27,116    <- dense P=4 WINS
C2             381,000       95,250     26,628    <- ED wins 3.6x
C3             466,000      116,500     26,584    <- ED wins 4.4x
```
On C1 a fairly-parallelised dense baseline is **faster** than ED K=4. The
2.9x board result rests partly on a baseline that was never given the same
knob.
**This is good news, not bad.** It does not weaken the thesis — it produces
the crossover the thesis was looking for, and locates it somewhere more
interesting than activity alone: **in the fan-out of the layer.** C1 has 18
taps per neuron and 64 targets per spike; C3 has 288 taps and 144 targets.
Event-driven wins where fan-in is large and dense must walk it all; dense
wins where fan-in is small enough that walking it is cheap. That is a
genuine architectural result with a mechanism behind it.
**Action.**
- Add a `P` parameter to `conv_layer.v` mirroring `ED_K`: bank weights and
  membranes by `oc mod P`, issue P taps per cycle. The infrastructure is
  the same partition `ed_scatter` already implements.
- Verify bit-identical against golden at P ∈ {1, 2, 4} (the existing
  harness should catch any error).
- Report the comparison at **matched parallelism** (P = K) as the primary
  result, with P=1 retained as the naive baseline.
- Consider also reporting **matched area** — dense at whatever P consumes
  the same LUT+BRAM as ED at K — which is arguably the fairest framing of
  all for an energy thesis.
**Done when:** a P-wide dense engine exists and is verified; the primary
comparison is at matched parallelism; the P=1 figures are relabelled as the
naive baseline rather than the baseline.
---
## C0030 — Pipeline the sweep: it is not an optimisation, it is what makes the architecture worth having (P1)
**Problem.** The sweep is 4 cycles/neuron. At K=4 on C1 that is 18.5k of
27.1k cycles — and it is a **floor**: the ED engine cannot go below it at
any activity level.
Against a fairly-parallelised dense baseline (C0029), C1 dense P=4 is 24.3k
cycles. So ED K=4's absolute best case, at zero activity, is 18.5k — only
1.3x better than a dense engine that does not care about activity at all.
**That margin is too thin to build an energy argument on.**
The log already identifies the fix — read n+1 while updating n, taking the
sweep to ~2 cycles/neuron — but files it as a timing patch and then as a
"later" item. At 2 cycles/neuron the ED floor becomes 9.25k, i.e. 2.6x
better than dense P=4, which is a margin worth measuring.
**Action.** Implement the pipelined sweep in `ed_conv_layer.v` and
re-verify against the full harness. Then re-run the cycle model and the
crossover prediction.
**Done when:** the sweep is ~2 cycles/neuron, bit-identical, and the
crossover prediction is updated.
---
## C0031 — Measure the touched-neuron fraction before deciding the sweep skip (P1, cheap — do before C0006)
**Problem.** C0006 asks whether to implement a sweep skip (skip neurons
with `I == 0` and `V` decayed to 0). Whether that pays depends entirely on
what fraction of neurons receive *any* input in a timestep, and that number
is not measured anywhere.
**Why it is not obvious.** One C1 input spike touches up to `2 x 2 x C_OUT
= 64` of 4,624 neurons — 1.4%. At ~392 input spikes per timestep, if
targets were disjoint, coverage would be total several times over. But
N-MNIST digits are **spatially clustered**, so the touched set is clustered
too and much of the frame may never be touched. Coverage could be anywhere
from ~20% to ~100%, and the skip is worth building only at the low end.
**Action.** Add ~10 lines to `golden/eventdriven.py` to record, per layer
per timestep, the fraction of neurons with `I != 0` and the fraction with
`V != 0` after the sweep. Run over the full split (D0009 — not `--limit`).
That measurement settles C0006 with data instead of judgement, costs an
hour, and the answer is a thesis result either way: *"at realistic
convolutional fan-out, N% of neurons receive input each timestep, so
event-driven neuron updates save little"* is exactly the kind of
quantified, mechanism-level finding the field lacks.
**Done when:** touched-fraction figures exist per layer at trained rates,
and C0006's decision cites them.
---
## C0032 — State the worst-case address-list sizing as a deliberate trade (P2)
**Problem.** D0016 sizes the address list for every neuron firing —
4096 x 13 bits for C1, roughly 1.5 BRAM tiles — for a case that never
occurs. At trained 6.8% firing, ~315 entries are used.
**Why it should be said out loud.** That is **area bought with determinism**,
and area costs static power, which is the thesis's own argument. The choice
is right — a data-dependent overflow policy would break bit-exactness or
make timing data-dependent, which D0016 correctly rejected — but the cost
should be quantified rather than left implicit, because it is part of why
the ED design carries 5.5 extra BRAM tiles.
**Action.** Quantify the address list's share of the ED area premium and
state the trade explicitly in the methodology.
---
## C0033 — Ask whether the two-word neuron state is structural or an ordering artefact (P2)
**Problem.** D0019's `V` plus `I` doubles neuron state and is the dominant
part of the ED area premium. The reasoning given is that leak and pending
reset need `V[n-1]`, which scatter would destroy.
**Worth one page of analysis.** Is that inherent, or an artefact of doing
scatter-then-sweep? An alternative ordering — apply leak and reset at the
*start* of the timestep, then scatter directly into `V`, with firing
evaluated at the next timestep's leading edge — might need only one word.
The delayed-reset semantics (D0002) already push the reset decision a
timestep late, which is suggestive.
I am not asserting this works; the bit-exactness risk is real and the
current design is verified. But since neuron state is the headline area
difference and area is the thesis's static-power argument, **the question
deserves an explicit answer even if the answer is "necessary, because X."**
Also check, separately and safely: `|I|` and `|V|` ranges are known per
layer from M1 (11/12/13/13 bits). Narrowing the memories only saves BRAM if
it crosses a Xilinx width boundary (36/18/9/4/2/1), so for C1 at 11 bits
there is probably no saving — but confirm per layer rather than assuming
16 bits everywhere.
---
## C0034 — Inter-layer chaining is designed but never exercised (P2)
**Problem.** D0016's double-buffered address lists exist so one layer's
sweep output feeds the next layer's scatter. On silicon only C1 has ever
run. The hand-off is designed, argued and unexercised.
**Action.** Chain at least C1 → C2 in simulation through the real address
lists (not the testbench's direct push) before any whole-network claim, and
on hardware before any whole-network measurement (see C0010, C0015).
---
# Second pass — measurement accuracy and missing experiments
Added 2026-08-20 after a closer read. C0018 and C0022 are more serious than
anything in the first list.
---
## C0018 — BURST replays one sample, so the energy figure is that sample's, not the design's (P0)
**Problem.** D0022 replays *the last-loaded sample* N times. Switching
activity is data-dependent, so the measured power is the power of sample 0
repeated 12,000 times — not the power of the design over its input
distribution. The ED engine's own latency already varies 1.49–1.56 ms
across samples (±2 %); energy will vary at least as much and probably more.
There is a second, subtler effect: replaying identical data means the DMA
and input buffer see the *same* words every iteration, so their switching
activity is unrepresentatively low and correlated. Real inference streams
present different data each frame.
**Also check:** whether BURST clears membrane and accumulator state between
iterations. If it does not, iteration k starts from iteration k−1's state,
which is neither the golden semantics nor a realistic stream. If it does,
that clear is itself work being measured. Either is fine — it must be
documented and identical for both engines.
**Action.**
- Extend BURST to cycle through the loaded sample set (16 samples already
  live in memory) rather than repeating one, or add a `--burst-sweep` mode
  that runs N/16 iterations of each and reports the mean and spread.
- Report energy per inference as mean ± spread across samples, not a single
  number from one sample.
- Document the state-reset behaviour between iterations in
  `host/protocol.md` and confirm it is identical for both engines.
**Done when:** the reported energy figure is a distribution over samples;
inter-sample spread is quoted; reset behaviour is documented.
---
## C0019 — Implementation-seed variance is an uncontrolled confound (P0)
**Problem.** Dense and ED are separate builds. They differ in the engine —
but they also differ in placement, routing, clock-tree loading and net
capacitance, all of which affect power independently of the design.
**Some fraction of any measured dense-vs-ED delta is build variance, not
architecture.**
**Why it matters.** This is the synthesis-side analogue of C0002's noise
floor, and almost nobody in the FPGA power literature controls for it —
which makes controlling for it a methodological contribution in its own
right.
**Action.**
- Build each design 3–5 times with different implementation seeds
  (`-directive` variants or an explicit placer seed), all WNS ≥ 0.
- Measure `P_idle` and `ΔP` for each build.
- Report the build-to-build spread alongside the design delta.
- **If build variance is comparable to the dense-vs-ED delta, the
  comparison cannot attribute and must be reported as such.**
**Done when:** seed spread is measured for both designs and quoted next to
every design-level delta.
---
## C0020 — Idle and burst readings are taken at different die temperatures (P1)
**Problem.** Leakage is exponential in temperature. The idle reading is
taken on a cooler die than the burst reading, so `ΔP = P_burst − P_idle`
contains a thermal leakage term that is not switching power. An 18-second
burst is also almost certainly *not* long enough to reach thermal steady
state — so the measurement is taken on a rising temperature ramp.
**Action.**
- Add a warm-up: run BURST continuously for several minutes until the XADC
  die temperature (C0009) is stable to within a stated tolerance, and only
  then start the measurement window.
- Record die temperature at both the idle and burst readings.
- Either correct for the leakage difference, or state it explicitly as a
  bound on the delta's accuracy.
**Done when:** the protocol has a defined warm-up and stability criterion;
temperatures at both readings are logged with every measurement.
---
## C0021 — Compare at iso-latency, not only at iso-frequency (P1)
**Problem.** Both engines run at 100 MHz, so ED finishes 2.9× sooner. But
the thesis's figure of merit is *energy at a fixed deadline*, and a design
that finishes early has bought nothing it needed.
**Why this is the sharper experiment.** Dynamic power scales roughly with
frequency. If ED were clocked down to whatever frequency just meets the
same deadline dense meets at 100 MHz — around 35 MHz — its dynamic power
would drop accordingly while its static power would not. That is the
correct comparison for a deadline-driven system, and it puts static power
front and centre, which is exactly the thesis's argument.
**Action.**
- Build ED at the lowest frequency that still meets the target deadline
  (and dense at 100 MHz, its minimum for the same deadline).
- Measure energy per inference for both at iso-latency.
- Report both framings: iso-frequency (which is what the accelerator
  literature reports) and iso-latency (which is what a control loop cares
  about). The difference between them is worth a paragraph.
**Done when:** an iso-latency energy comparison exists alongside the
iso-frequency one.
---
## C0022 — There is no ANN baseline, so the ES-Parkour claim cannot actually be audited (P1)
**Problem.** The thesis motivation is that ES-Parkour reports 11.7 % of ANN
energy (88.3 % saving) computed analytically, and that nobody has measured
it. But every measurement planned here is **spiking-dense versus
spiking-event-driven.** Without an ANN reference, the headline audit cannot
be performed.
**Action — two options, and the cheap one is arguably better.**
**(a) Cheap, and directly on point.** Compute the analytical energy for
*your own network*, using ES-Parkour's own method — operation counts times
45 nm per-operation constants (MAC 4.6 pJ, AC 0.9 pJ) — and compare it
against your measured figure. You already have exact operation counts from
the golden model and the cycle model. This audits the *published
methodology* on a network where you also have ground truth, which is
precisely the thesis's claim, without building anything new.
**(b) Expensive, and stronger.** Build an INT8 ANN conv engine for the same
C1 geometry on the same fabric, verified against a golden model the same
way, and measure it. This gives a real measured SNN-versus-ANN number on
identical silicon — the thing nobody has.
Do (a) regardless; it is a day's work and it is the sentence the abstract
wants. Do (b) if time allows, and note that it needs DSPs, which changes
the "DSP = 0" property (C0017) and needs its own timing closure.
**Done when:** the analytical-versus-measured comparison exists for this
network with both numbers and the ratio; a decision on (b) is recorded.
### C0022 addendum — a 2026 paper states this thesis's question as an open one
Harmeling et al. (NCE 6, 024022, June 2026) treat the dense-versus-event
tradeoff as established folklore, choose synchronous processing on that
basis **without measuring it**, and then close by suggesting the question is
open:
> *"The event-driven approach proposed by Roy et al is highly efficient when
> spikes are sparse, but becomes less effective under dense or bursty
> activity. In such cases, synchronous layer-by-layer processing is commonly
> adopted. Here, we employ a synchronous per-layer processing scheme."*
> *"...higher values (e.g. 980) significantly reduce spiking activity (by
> approximately a factor of ~3)... This suggests that an event-based
> implementation could become advantageous when activity is sufficiently
> sparse."*
**Use this in the introduction and in related work.** It is a peer-reviewed,
open-access, three-month-old statement that (i) the tradeoff is assumed
rather than measured, and (ii) whether event-driven wins at low activity is
a suggestion awaiting evidence. That is a stronger framing of the gap than
anything you can assert on your own authority, and it dates the gap to
after the literature review rather than before it.
---
## C0023 — Two planned sweep axes are missing entirely: T and weight bit-width (P1)
**Problem.** The project brief names both timestep count and quantisation
bit-width as experiment axes. Neither appears anywhere in the log.
**Why they matter.** T multiplies both latency and energy directly and is
the SNN-specific knob no ANN has — a T sweep is one of the few results
that is *about spiking* rather than about dataflow. Bit-width trades weight
BRAM (and therefore static power) against accuracy, which is the other half
of the area-versus-activity argument.
**Action.**
- Confirm T is parameterised end-to-end (RTL, wrapper, protocol, host) and
  sweep T ∈ {1, 2, 4, 8}: accuracy, latency, energy for both engines.
- Sweep weight width ∈ {4, 8} at minimum: accuracy, BRAM, `P_idle`, energy.
  4-bit halves weight storage, which should move `P_idle` measurably — a
  direct test of the static-power argument.
**Both sweeps have a direct published comparison point.** Harmeling et al.
(NCE 2026) sweep weight bit-width from 9 down to 2 bits with accuracy at
every point (their table 5), and sweep spike-train length — the analogue of
your T — with accuracy, latency and energy per point (their table 3). Their
finding that 4 bits is a practical floor for MNIST but not for
Fashion-MNIST is worth testing against your own network, and their tables
give your sweeps somewhere to land rather than standing alone.
**Done when:** both sweeps have results tables with accuracy reported at
every point (C0008), and are positioned against Harmeling's equivalents.
---
## C0043 — Justify the LIF choice with a citation rather than an assertion (P3)
Harmeling et al.'s table 4 gives per-neuron FPGA cost by neuron model on an
Artix-7 (after Koravuna et al.): LIF 13 LUT / 17 FF / 0 DSP; SRC 75 / 21 /
0; QIF 82 / 21 / 0; Izhikevich 42 / 25 / 1; Hodgkin-Huxley 73 / 25 / 3.
Background chapter currently justifies LIF on general "hardware cost"
grounds. This table makes the argument quantitative in one line, and it
also gives you a place to acknowledge what LIF gives up — the same paper
argues SRC preserves dynamics LIF discards, which is a fair limitation to
name rather than to omit.
---
## C0024 — Report ΔP against activity, not only endpoint energy (P1)
**Problem.** The M7 plan produces energy per inference at each activity
level. That is an endpoint number. It does not demonstrate the
*mechanism*.
**Why it matters.** If ΔP is linear in spike count for ED and flat for
dense, that is direct evidence the event-driven datapath behaves as
designed — and it turns the crossover from a measured coincidence into a
model with a fitted slope and intercept. You already have exactly this
structure in cycles (`ED K=4 = 121.8k + 21.9/spike`). Doing it in power
lets you state the energy model in the same form.
**Action.** For each engine, plot measured ΔP against measured spike count
across the activity sweep; fit and report slope (energy per synaptic
event) and intercept (fixed per-timestep cost). Compare the fitted
intercept against the sweep-floor cost predicted from cycles.
**Done when:** the fitted energy model exists for both engines, with its
coefficients compared against the cycle-level prediction.
---
## C0025 — Measure energy against K on the board (P2)
**Problem.** The K axis is filled in simulation for latency
(K = 1…16). D0017's note correctly says energy per K is the meter's
question — but it is not yet in any plan as a deliverable.
**Why it matters.** K is the knob that flips the C2/C3 cycle-level
crossover, and each doubling of K doubles the accumulator bank BRAMs.
Latency improves with diminishing returns while static cost grows
linearly, so there should be an energy-optimal K that is **not** the
latency-optimal K. That is a clean, quotable design result.
**Action.** Build and meter at least K ∈ {1, 4, 16}: `P_idle`, ΔP, energy
per inference, BRAM. Identify the energy-optimal K and state whether it
differs from the latency-optimal one.
**Done when:** an energy-versus-K table exists with the optimum identified.
---
## C0026 — The 12 V measurement point sits behind non-linear regulators (P2)
**Problem.** Measuring at the barrel jack means measuring through the
board's switching regulators, whose efficiency varies with load. A 2.7 mA
delta at the input does not correspond linearly to the load-side delta,
and the transfer function is not known.
**Action.** Either move to a load-side rail (C0004's VCCINT question), or
characterise the input-to-load relationship by applying a known variable
load and measuring both sides. If neither is practical, state the
non-linearity as a limitation with an estimated bound.
**Done when:** the measurement point is either load-side, characterised,
or its non-linearity is bounded and declared.
---
## C0027 — State the tool-ranking result formally (P2)
**Problem.** The 23:00 entry observes that Vivado's estimates for the two
designs differ by ~25 mW on ~30 mW of fabric power, and concludes the tool
"genuinely cannot rank the two designs." That is a strong, quotable claim
currently living in a log entry.
**Action.** Turn it into a stated result: does the tool's *ordering* of the
two designs match the meter's ordering, and by how much does the magnitude
differ? With C0019's seed spread, you can also say whether the tool's delta
is even larger than its own build-to-build variance.
"The synthesis tool cannot rank two architectures whose measured energies
differ by X%" is a headline sentence if the measurement supports it — and a
useful negative result if it turns out the tool ranks them correctly.
**Done when:** the ranking claim is stated as a result with numbers behind
it, in both directions (ordering and magnitude).
---
---
# Third pass — internal consistency and thesis alignment
Added 2026-08-20. Most of these came from cross-checking figures in the log
against each other rather than against outside knowledge.
---
## C0035 — The AXIS wrapper is now the binding constraint, not a nicety (P0, promote from C0014)
**Problem.** The wrapper is bit-serial: 73 words in + 145 words out per
timestep, unpacked and packed one bit per cycle. That is ~28k bits of
traffic per sample, matching the 39–48k cycles attributed to it.
**Why it has become blocking.** Once the dense engine gets a `P` knob
(C0029), the wrapper caps what parallelism can buy:
```
dense engine  wrapper   total    wrapper share
P=1   388k     48k      436k      11 %
P=4    97k     48k      145k      33 %
P=8    48k     48k       96k      50 %
```
The same saturation hits ED at higher K. **You cannot run the P or K sweeps
(C0025, C0029) or the iso-latency comparison (C0021) meaningfully while a
fixed 48k-cycle serial cost dominates both arms.** A word-parallel wrapper
takes 28k bits down to ~872 word transfers — roughly 32x — and removes the
ceiling.
**Action.** Implement word-parallel pack/unpack in `axis_conv.v`, re-verify
through the hostile-handshake bench for dense, ED K=1 and ED K=4, and
re-baseline every cycle figure.
**Done when:** the wrapper is a small fraction of both engines' totals and
the parallelism sweeps are no longer saturating on it.
---
## C0036 — Three different network geometries are conflated in the log (P1)
**Problem.** There are three networks in play and the log moves between
them without always saying which:
| | input | c3 | FC | params |
|---|---|---|---|---|
| project brief's target | 48x64 | 64x6x8 | 768→128 | 121,632 |
| **N-MNIST, as implemented** | 2x34x34 | 64x5x5 | **256→128** | **~56,096** |
| robot / distilled (D0024) | 2x64x64 | 64x8x8 | 1024→34 | 58,178 |
The implemented N-MNIST FC is 256→128 = 32,768 weights (confirmed by
D0023's "W_T[j][n] (32,768 bytes)" and "128 neurons x 256 windows x 4
positions"), **not** the brief's 768→128 = 98,304.
**Consequences that matter.**
- D0004's "the FC layer holds 98,304 of 121,632 parameters — **81 %** of the
  network's weights" describes the *brief's* network. For the implemented
  N-MNIST network it is 32,768 / 56,096 = **58 %**. D0006 then cites the
  81 % figure as if it describes the built network, and uses it to reason
  about where the event-driven design's fate is decided.
- The headline constraint "161 KB, ~26 % of BRAM, everything on-chip" is
  also the brief's network. The implemented N-MNIST network is ~73 KB dense
  / ~91 KB event-driven. The robot network is ~114 KB / ~172 KB.
- All three still fit comfortably, so nothing is broken — but a reader
  cannot currently tell which number describes the artifact that was
  measured.
**Action.** Add a table to `docs/decisions.md` naming the three geometries
and their resource figures, and annotate every resource claim with which
one it describes. Correct the 81 % figure where it is used to describe the
implemented network.
**Done when:** every parameter, neuron and BRAM figure in the log states
its geometry.
---
## C0037 — With a fair dense baseline, the C1 crossover lands almost exactly at the operating point (P1)
**This is a result, not a defect — but it changes what the thesis reports.**
Using the M7 sim's own fitted models and a P=4 dense engine (C0029), and
holding the wrapper constant at ~48k cycles:
```
dense P=4 : 97k + 48k              = 145,000 cycles/sample  (flat)
ED K=4    : 121,800 + 21.9 x spikes
equal at   spikes = (145,000 - 121,800) / 21.9 = 1,059 spikes/sample
total possible = 2,312 inputs x 4 timesteps    = 9,248
crossover                                       = 11.5 % input activity
```
**The trained N-MNIST input activity is 13.8 % (D0009).** So at C1's actual
operating point, a fairly-parallelised dense engine and the event-driven
engine are within a few percent of each other — with dense marginally
ahead.
**Why this is good.** A crossover that sits far from the operating point is
a curiosity. One that sits *at* it is the thesis: it means the architecture
choice genuinely depends on the workload, and small design changes (the
sweep pipeline, C0030; the wrapper, C0035) move the answer. It also means
the deeper layers — where ED wins 3.6x and 4.4x even at P=4 — carry the
whole-network case, which is a mechanism worth stating.
**Action.** Recompute this properly once C0029, C0030 and C0035 land, and
report the crossover with its sensitivity to each. State plainly that at
C1's geometry and operating activity the two designs are close, and that
the event-driven advantage comes from fan-in-heavy layers.
**Done when:** the crossover is reported per layer, with the operating
point marked on the plot.
---
## C0038 — Board-level "energy per inference" is an ARM number, not an engine number (P0)
**Problem.** Fabric power is ~31 mW of a ~1.7 W chip estimate; the PS is
96 % of dynamic power. A measured "energy per inference" at the 12 V input
is therefore **overwhelmingly the ARM and the board**, not the accelerator.
Reporting "energy per inference = X mJ" without qualification would be a
statement about a Cortex-A9 running a polling loop.
**Action.** Report three distinct quantities and never let them merge:
1. **System energy per inference** — the board-level figure, honest and
   dominated by the host. Useful for the deployment argument.
2. **ΔE between the two engines** — the fabric-attributable difference.
   This is the architecture result.
3. **Engine energy** — (2) plus the static component from C0001, with the
   attribution method stated.
The dense-vs-ED comparison lives in (2). The ES-Parkour audit (C0022) must
also use (2) or (3), never (1), because ES-Parkour's analytical figure is a
network-compute number with no host in it.
**Done when:** the results chapter defines all three and every number is
labelled with which it is.
---
## C0039 — The verification sample set is class-biased (P1)
**Problem.** Every BOARD PASS uses "16 golden samples," and the cycle
tables refer to "busy digit-0 samples." D0009 established that N-MNIST is
class-ordered, so the first 16 samples are all digit 0.
**Why it matters.** Bit-exactness proven over one digit class is proven
over a narrow input distribution — narrower spatial extent, narrower
activity range, and possibly narrower membrane range than the full split.
The M1 membrane-range measurements (which justify the 16-bit datapath, and
therefore the absence of saturation logic in D0010) may also have been
taken on that distribution.
**Action.**
- Rebuild the 16-sample verification set as a seeded random draw across all
  ten classes, and re-run BOARD PASS for both engines.
- Re-check the membrane and current ranges on the full split, and confirm
  the 16-bit no-saturation decision (D0010) still holds with headroom.
**Done when:** verification spans all classes and the datapath-width
justification cites full-split ranges.
---
## C0040 — The M7 rehearsal used synthetic Bernoulli inputs; real activity is spatially clustered (P1)
**Problem.** `experiments/m7_sim/` sweeps activity with "synthetic
Bernoulli inputs at ten densities." Real event data is **spatially
clustered** — digits occupy a small region — so at the same mean rate the
address distribution is entirely different.
**Why it matters more for energy than for cycles.** By design there are no
data-dependent stalls (D0017's banking is conflict-free by construction),
so cycle counts should be insensitive to clustering. **Switching activity
is not.** Address locality changes BRAM row activation patterns and net
toggling, and energy per RMW is not a constant.
**Action.** Run the energy sweep on *real* samples with activity varied
through the threshold / weight-scale knob (D0005), not on synthetic
Bernoulli fields. Keep the Bernoulli sweep as the cycle-model validation it
already is, and label it as such.
**Done when:** the energy-versus-activity curve is measured on real data,
and any divergence from the Bernoulli cycle prediction is reported.
---
## C0041 — The wrapper's cycle attribution is internally inconsistent (P2)
**Problem.** The wrapper is reported as 48k cycles for dense (11 % of 436k)
and 39k for ED K=4 (26 % of 149k). But D0021 states the two paths do
**identical work** — same words in, same words out, differing only in one
line of the unpack state. Identical work should cost identical cycles.
The 9k discrepancy suggests the attribution is measuring *exposed*
wrapper time (cycles where the engine is idle) rather than wrapper work,
which would differ with overlap. That is a legitimate thing to measure, but
it is a different quantity and it should not be described as "the wrapper's
cost."
**Action.** State the attribution method precisely. If it is exposed time,
report the wrapper's absolute work separately, since only the absolute
figure is comparable between engines.
**Done when:** the method is documented and the two engines' wrapper
figures are reconciled or explained.
---
## C0042 — Nothing in the current plan produces the thesis's stated metric (P1)
**Problem.** The thesis's figure of merit is **energy per inference at a
fixed control deadline.** The experiments planned produce energy per
inference at ~100 % duty (BURST), latency, and — with C0005 — energy per
control period at various rates. None of these is yet measured *with a
deadline in force and consequences for missing it.*
**Why it matters.** This is the sentence that distinguishes the thesis from
an accelerator benchmarking paper. Without it, the work is "we measured two
SNN datapaths carefully," which is good but is not what the introduction
promises.
**Action.** Make the connection explicit and scheduled:
- Year one delivers the components: measured energy (C0001), latency, and
  the duty-cycle model (C0005).
- Year two's HIL loop delivers the deadline: `robot/host/perception_loop.py`
  already charges the perception path against an explicit budget and logs
  overruns. Wire the FPGA link in as the `perceive` callable, and report
  energy per control period alongside deadline-miss rate at each perception
  rate.
- State in the methodology which chapter delivers which half, so an
  examiner can see the promise is kept rather than quietly narrowed.
**Done when:** the thesis outline maps the stated metric to specific
experiments, and the HIL loop has the FPGA behind its `perceive` hook.
---
## Closing note on this review
Three passes have been made: methodology (C0001–C0017), measurement
accuracy and missing experiments (C0018–C0027), design and internal
consistency (C0028–C0042).
The rate of significant findings has dropped sharply — pass one found
structural gaps, pass two found protocol errors, pass three found mostly
bookkeeping inconsistencies plus two real ones (C0035, C0037). **That decay
is the signal to stop reviewing on paper and start acting**, because the
next class of problem is the kind only measurement finds: the noise floor
(C0002), the seed spread (C0019), and whether the fabric delta is resolvable
at all (C0003).
Two things that would benefit from a fresh pair of eyes rather than another
pass from me:
- **An independent re-derivation of the cycle model from the RTL**, by
  someone who has not seen the tables. C0028 was an arithmetic slip that
  survived because every later figure was checked against the same model.
- **A read of the M1 quantisation chain by someone fluent in fixed-point.**
  It is the one part of the stack I have only been able to check for
  internal consistency, not correctness — the shift-based leak's truncation
  behaviour for negative V (D0007) in particular deserves a second reader.
---
## Suggested order
**Immediately — these change what the results mean:**
0a. **C0028** (dense cost model wrong for C2/C3) — a highlighted finding
    does not survive; retract it before it propagates further.
0b. **C0029** (P-wide dense baseline) — the comparison is currently
    4-wide against 1-wide. Fixing it likely creates a real crossover.
0c. **C0031** (touched-neuron fraction) — one hour, and it settles C0006.
0d. **C0035** (word-parallel wrapper) — blocking the P and K sweeps and the
    iso-latency comparison; every cycle figure re-baselines after it.
0e. **C0038** (three energy quantities) — a labelling decision, but making
    it late means relabelling every table.
**Before the meter session:**
1. **C0002** (noise floor) — decides whether C0003 is optional.
2. **C0003** (replication) — likely removes the instrument problem.
3. **C0018** (multi-sample BURST) — cheap, and without it every energy
   number is one sample's.
4. **C0019** (seed variance) — a few extra builds; without it the delta
   cannot be attributed.
5. **C0001** + **C0004** + **C0020** (idle power, boundary, thermal) —
   recovers the static-power argument and removes a systematic error.
**Before any M7 number is written up:**
6. **C0006** (sweep skip) — a design decision; make it before more builds.
7. **C0022(a)** (analytical-vs-measured) — a day's work; it is the audit
   the thesis promised.
8. **C0005**, **C0007**, **C0008**, **C0021**, **C0024** — the M7 protocol
   proper.
9. **C0023**, **C0025** — the remaining sweep axes.
**Before write-up:** everything else.
The four cheapest items with the largest effect on whether the results are
believable are **C0002**, **C0018**, **C0019** and **C0001**. None takes
more than a day. Together they turn "we measured 25 mW of difference" into
a claim with a noise floor, a build-variance bound, a sample distribution,
and a static-power component — which is the difference between a result and
an anecdote.
