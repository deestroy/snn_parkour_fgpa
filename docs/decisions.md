# Design decisions

Every judgement call, with the reasoning and the evidence. This file becomes
the thesis methodology chapter, so write entries as if a examiner will read
them. Newest at the bottom. Status is one of: OPEN, DECIDED, REVISITED.

---

## D0001 — Start the golden model at one neuron, not at the network

**Date:** 2026-08-15 · **Status:** DECIDED

The golden-model rule requires bit-identical agreement between Python and
hardware. Rather than write the reference model once the network exists, we
started it at the smallest unit: `golden/lif.py` implements a single LIF
neuron as a plain loop, and `train/00_lif_demo.py` asserts it matches
snnTorch's `snn.Leaky` exactly.

**Evidence:** demo reports `spikes bit-identical: True`,
`membrane bit-identical: True`, `max |V| difference: 0.0` — over 40 timesteps,
float32.

**Why it matters:** it forced the two questions in D0002 into the open on day
one, at a scale where they cost minutes to resolve rather than days of
waveform-staring in M2.

**Cost:** `golden/lif.py` does arithmetic in the dtype of its input array so
that float32 rounding matches PyTorch's. This is deliberate; it is why the
check can assert equality rather than a tolerance.

---

## D0002 — Which LIF neuron are we actually building?

**Date:** 2026-08-15 · **Status:** DECIDED — see verdict at the bottom

the project brief specifies `V[n] = beta*V[n-1] + sum(w*s[n])`, fire and reset when
`V >= V_threshold`. snnTorch's `snn.Leaky` defaults do **not** implement that.
Two differences, both confirmed by experiment:

**(a) When the reset is applied.** snnTorch's `reset_delay=True` computes the
reset from the *previous* membrane, so the threshold subtraction lands one
timestep after the crossing. the project brief describes an immediate reset. Same
input, same beta, same threshold:

```
reset_delay=True  (snnTorch default) : .........|.....|....|...................
reset_delay=False (the project brief's model): .........|....|....|....|...............
```

3 spikes vs 4 over 40 timesteps — a 33% difference in firing rate, which is the
independent variable of the entire thesis.

**(b) Strict vs non-strict threshold.** snnTorch fires on `V > threshold`
(it evaluates a Heaviside of `V - threshold`). the project brief says `V >=`. Driving
a neuron to land exactly on the threshold:

```
V exactly == threshold -> fire on '>' : ......   (no spike)
                       -> fire on '>=': |.....   (spike)
```

With floats, exact equality is rare enough to hide for months. In M1 everything
becomes **integers**, where landing exactly on the threshold is common — so this
will start mattering precisely when it is hardest to debug.

**Options:**

1. **Match snnTorch (`reset_delay=True`, strict `>`)** and update the project brief
   to describe what we actually build. Zero friction in training; the delayed
   reset needs one extra register in hardware to hold the pending reset flag.
2. **Match the project brief (immediate reset, `>=`)** and pass
   `reset_delay=False` to every snnTorch neuron. Costs nothing at training
   time, and the immediate reset is the more natural thing to build in a single
   clock cycle.

**Recommendation at the time: option 2.** Reasoning was that the hardware is
the constrained side of the project and should not inherit a quirk from a
training library's default.

### Verdict: option 1 — match snnTorch (`reset_delay=True`, strict `>`)

Chosen 2026-08-15. the project brief has been amended to describe the neuron we
actually build. `golden/lif.py` keeps both behaviours behind flags, but
`reset_delay=True, fire_on_equal=False` is now the project default and every
comparison against hardware uses it.

**The recommendation was priced wrong and the correction favours this choice.**
I claimed the delayed reset costs an extra register per neuron to carry the
pending-reset flag between timesteps. It does not. The flag is

```
pending_reset[n] = (V[n-1] > threshold)
```

which is a pure function of the membrane potential we already store. Hardware
recomputes it with a comparator against the stored `V` at the start of the
step — no extra state, no extra memory traffic. Since membrane state is 42.2 KB
of a 161 KB on-chip budget, "no extra state per neuron" is the cost that
actually mattered here, and option 1 does not pay it.

**Consequence for the datapath:** a LIF update becomes two comparisons against
threshold per timestep (one on the stored `V` to resolve the pending reset, one
on the new `V` to decide the spike) rather than one. Both compare the same
register against the same constant, so they share the comparator or cost a few
LUTs. Revisit only if M3 shows the LIF update on the critical path.

**Consequence for firing rate:** the delayed reset produces *fewer* spikes than
the immediate reset (3 vs 4 in the 40-step test above). Firing rate is the
independent variable of the thesis, so this is not a neutral choice — it must
be stated in the methodology, and the dense and event-driven designs must both
use it or the M7 comparison is meaningless.

---

## D0003 — Input encoding: event counts or binary spikes?

**Date:** 2026-08-15 · **Status:** OPEN — needs a decision before M0 training

`tonic`'s `ToFrame` does not produce spikes. It produces **event counts**: an
`int16` tensor where each value is how many events landed in that pixel during
that time bin. Measured over 64 N-MNIST test samples, T=4, after `Denoise`:

```
max events in one pixel/timestep : 10        -> 4 bits, not 1
mean events per non-zero pixel   : 3.06
fraction of non-zero that are >1 : 76.7%     -> not a rounding artefact
activity (fraction non-zero)     : 16.83%
```

So three quarters of the active input pixels carry a value the hardware cannot
represent as a spike. This is not a detail to fix later: the input layer is the
one place where the "spikes are 1-bit events" premise of the whole thesis meets
the dataset, and 4-bit graded inputs would quietly change what the event-driven
datapath has to carry per event.

**Options:**

1. **Binarise** — `frames = (frames > 0)`. Input becomes genuinely 1-bit.
   Discards the count information; input activity is then 16.83%.
2. **Keep counts, widen the first layer only.** The first layer multiplies a
   4-bit input by an 8-bit weight instead of gating it. Retains information,
   but the first layer stops being a spiking layer, and the event-driven engine
   would need a payload per event rather than just an address.
3. **Raise T so bins hold at most one event.** Physically the most honest — it
   is what the event camera actually produced — but T is fixed at 4 by
   the project brief and raising it multiplies latency and energy per inference.

**Recommendation: option 1, binarise.** It is what the snnTorch tutorials do,
it keeps the input consistent with every other layer, and it keeps the
event-driven engine's payload at "an address and nothing else", which is the
design the thesis is actually about. Option 2 would make the M7 comparison
harder to interpret, because the first layer would be dense by construction
regardless of firing rate. Record the accuracy cost when M1 measures it.

**Caveat to carry forward:** 16.83% input activity is the *input* rate, not the
network's firing rate. The hidden-layer rates M0 is meant to measure are the
ones that matter, and they are usually much lower.

### Verdict: defer to measurement

Chosen 2026-08-15. The input transform becomes a flag (`--binarise`), the
network trains both ways, and the measured accuracy difference decides. This
turns D0003 from a judgement call into an experimental result, which is worth
more in the methodology chapter than a defensible guess. Option 1 remains the
expected outcome; the cost is one extra training run.

---

## D0004 — The missing pool: reconciling the target network's parameter count

**Date:** 2026-08-15 · **Status:** DECIDED

the project brief's layer table does not close arithmetically. All three conv layers
and their spatial shapes are correct, but C3 emits `64 x 6 x 8 = 3072` features
while the table lists the FC layer as `768 -> 128`. Nothing in the table turns
3072 into 768.

This is not cosmetic. It moves the constraint the brief marks non-negotiable:

```
                      params    8-bit weights   % of PYNQ-Z2 BRAM (612.5 KB)
as written (FC 768)   121,632        118.8 KB        19.4%
as computed (FC 3072) 416,544        406.8 KB        66.4%
```

**Resolution: a 2x2 pool after C3.** `3072 / 4 = 768` exactly. Two independent
checks confirm this is the intended design rather than a convenient patch:

1. The brief's own membrane-state figure. Counting every neuron —
   C1 `16x24x32=12288`, C2 `32x12x16=6144`, C3 `64x6x8=3072`, FC `128` —
   gives 21,632 neurons, and at 16 bits that is 43,264 B = **42.25 KB**, which
   is the 42.2 KB the brief states. A pool has no membrane state of its own, so
   this number is consistent with a pool and inconsistent with the FC layer
   genuinely having only 768 inputs.
2. `118.8 + 42.2 = 161 KB`, which is **26.3%** of 612.5 KB — the brief's "about
   26% of the board's block RAM", to the decimal.

So the pool is missing from the table, not from the design. The model
implements it, `pool_before_fc` makes it switchable, and `train/model.py`
prints the parameter budget so this class of error surfaces immediately rather
than at synthesis.

**Consequence:** the FC layer holds 98,304 of 121,632 parameters — **81% of the
network's weights sit in one layer.** Whatever the event-driven engine does
about the FC layer dominates the M7 energy result. Worth knowing before M6.

---

## D0005 — Weight initialisation: the network starts silent

**Date:** 2026-08-15 · **Status:** DECIDED

With PyTorch's default Kaiming-uniform initialisation the network emits
essentially nothing. Measured on binarised N-MNIST, 32 samples, T=4:

```
C1 input current: mean |I| 0.1724, max 0.9458   <- threshold is 1.0
C2 input current: mean |I| 0.0000, max 0.0000   <- C1 never fired, so C2 is dead
```

C1's largest input current lands just under the threshold, so C1 barely fires;
C2 onward then receive exactly zero and the whole network is silent. Firing
rates by initial weight gain:

```
gain    c1      c2      c3      fc
 x1   0.0088  0.0000  0.0000  0.0000    silent
 x2   0.0474  0.0082  0.0000  0.0000    silent past C2
 x4   0.1716  0.1936  0.1876  0.1516    alive at every layer
 x8   0.2163  0.3454  0.3470  0.3498    denser than we want
```

**Decision: `INIT_GAIN = 4.0`**, applied to C1/C2/C3/FC at construction. It is
the smallest tested gain that leaves every layer firing, and it starts the
network near 17-20% activity rather than at either extreme.

**This is one knob, not two.** Multiplying every weight by `g` and multiplying
the threshold by `g` produce an identical network — the LIF update
`V = beta*V + sum(w*s)` and the reset-by-subtraction of `V_threshold` are both
linear in that scale. Two consequences:

- **For M1:** the hardware should pin `V_threshold` to a convenient fixed-point
  constant (a power of two, so the reset subtraction is free) and let the
  quantised weights carry the scale. Do not spend bits on a tunable threshold.
- **For M7:** "sweep the firing rate via the threshold" and "sweep it via a
  weight-scale term" are the same experiment. Whichever we use, it must be
  stated as a single scale parameter, or a reviewer will reasonably ask whether
  we swept two things and reported one.

**Guard:** `train/02_model_check.py` now fails if any layer emits zero spikes,
so this failure mode is caught in seconds rather than after a training run that
goes nowhere. Verified: the check fails at gain 1.0 and passes at gain 4.0.

### D0003 measurement (2026-08-15, MI210, 10 epochs, 4 seeds per arm)

```
                     final test accuracy            mean
binarised (1-bit)    96.81  96.95  97.25  96.70    96.93%
counts (4-bit in)    97.85  97.50  97.66  97.30    97.58%
```

Every counts run beats every binarised run: the gap is real, ~0.65 pp, and not
seed noise. Per-layer firing rates were essentially identical between arms
(c1 ~6.5%, c2 ~8%, c3 ~10%, fc ~30%), so the encoding choice does not move the
thesis's independent variable — it only trades accuracy against input-layer
hardware complexity. The decision is therefore: is 0.65 pp on N-MNIST worth
carrying a 4-bit payload per input event through the event-driven datapath?

---

## D0006 — M0 result: trained per-layer firing rates

**Date:** 2026-08-15 · **Status:** measurement, recorded

10 epochs on N-MNIST, MI210, T=4, binarised arm, final epoch:

```
c1    6.8%   c2    7.6%   c3   10.5%   fc   30.1%
```

Three observations that shape the hardware milestones:

1. **Conv layers are sparse (6-11%), the FC layer is not (30%).** The FC layer
   also holds 81% of the weights (D0004). The event-driven design's worst layer
   is therefore also its biggest layer. This combination decides M6's fate and
   must drive the M6 design discussion.
2. **Rates drifted down over training** (fc 34%->30%), not up. The runaway-rate
   worry from the synthetic smoke test did not materialise on real data at
   these settings; a rate regulariser is still expected for M7's sweep, but is
   not needed just to keep the network sane.
3. **Rates are stable across seeds and encodings**, so a single training run is
   a fair basis for hardware sizing.

### D0003 verdict: binarise

Chosen 2026-08-15, after measurement. The 0.65 pp accuracy cost is accepted in
exchange for keeping every event in the event-driven datapath payload-free (an
address and nothing else) and the input layer identical in kind to every other
layer. The cost is measured across 4 seeds and reportable as such in the
methodology. Binarised input is now the project default; `--counts` remains in
train/03_train.py for reproducing the comparison.

---

## D0007 — Leak becomes shift-based: β = 0.875

**Date:** 2026-08-16 · **Status:** DECIDED

The LIF leak `β·V` with β=0.9 would need a real multiply per neuron per
timestep — 21,632 multiplies per timestep on the target network, in the most-
executed operation on the chip. With β = 1 − 2⁻³ = 0.875 the leak is
`V − (V >> 3)`: shift and subtract, no multiplier. Standard neuromorphic
practice. Chosen with the proviso that a retrain at 0.875 must hold accuracy;
measurement to be recorded below when the retrain lands.

Note for the golden model: the integer form `V − (V >> 3)` truncates (shifts
round toward −∞ for negative V), so it is not identical to float `0.875·V`
rounded. The integer form is the definition; training in float at 0.875 is an
approximation of it, and the M1 accuracy budget absorbs the difference.

## D0008 — Weight scales restricted to powers of two

**Date:** 2026-08-16 · **Status:** DECIDED

Quantised weights are `w = int8 × 2^−k`, one k per layer. Rescaling between
layers becomes a bit-shift instead of a fixed-point multiply, and the golden
model becomes exact integer arithmetic with no rounding subtleties. Costs up to
~2× coarser quantisation steps than an arbitrary float scale; the M1 accuracy
check (~1% budget vs float) is the gate. Fallback if it fails: arbitrary float
scale per layer, revisit this entry.

### D0007 measurement (2026-08-16)

Retrained at β=0.875, 10 epochs, 3 seeds: 96.60 / 97.27 / 97.22, mean
**97.03%**, vs the β=0.9 baseline mean of 96.93% over 4 seeds. Same
distribution — the shift-based leak costs nothing measurable. Decision stands.
Checkpoints saved as train/checkpoints/m1_beta0875_seed{0,1,2}.pt; seed 0
(96.60%) is the quantisation input so the accuracy budget is judged against
the weakest of the three rather than a lucky seed.

---

## D0009 — Correction: N-MNIST is class-ordered; early sparsity figures were digit-0 only

**Date:** 2026-08-16 · **Status:** recorded

The N-MNIST test split (and tonic's ordering generally) is sorted by class:
the first 1000 samples are 980 zeros and 20 ones. Consequences:

- The input-activity figure measured in M0 over "the first 64 samples"
  (16.83%) was actually measured over digit 0 alone — the fattest digit.
  Re-measured over a seeded random 2000-sample subset: **13.80% mean**
  (per-digit range 7.9% for '1' to 16.9% for '0'). 13.80% supersedes 16.83%
  everywhere.
- Any `--limit N` evaluation on the packed arrays sees only the low digits
  and is biased. Smoke tests may use limits; **reported numbers must come
  from the full split.** The golden-model check learned this the hard way:
  its first-1000 accuracy read 98.7% purely because 98% of those samples
  were zeros.
- Training is unaffected: the DataLoader shuffles.

---

## M1 result (2026-08-16)

The all-integer golden model over the full N-MNIST test set:

```
float model (seed 0)     : 96.60%
golden integer model     : 96.75%      drop: -0.15 pp (gate was ~1 pp)

membrane ranges observed : c1 11 bits, c2 12, c3 13, fc 13  -> int16 holds
                           with >= 3 bits of headroom everywhere
```

The quantisation stack — int8 weights at 2^-6, shift-based leak, integer
thresholds 64/64/64/256, sum pooling — costs nothing measurable. Verification
supporting the number: golden conv and pool match torch bit-for-bit on random
integer inputs, and every reported figure is full-split (see D0009).

M1 done-when is met: accuracy within 1%, and per-layer spike/membrane/current
traces are emitted (golden/traces_m1.npz, regenerated exactly by
`python3 train/06_golden_check.py`). These traces are the reference for every
HDL testbench from M2 on.

---

## D0010 — HDL language and M2 neuron conventions

**Date:** 2026-08-16 · **Status:** DECIDED

**Verilog** (2001 subset), chosen over VHDL because both simulators already on
the development machine (iverilog 12, verilator) support it well and support
VHDL poorly or not at all, and PYNQ-community material is predominantly
Verilog. Revisit only if the lab standardises otherwise.

Conventions fixed in the M2 single-neuron module, to hold for every later one:

- **16-bit signed datapath** for membrane and current. Justified by trace
  measurement, not assumption: across all M1 traces, |I| <= 931 and
  |V| <= 2245, against an int16 ceiling of 32767.
- **Registered outputs.** Present I[n] with en=1; after the clock edge, v_out
  and spike hold V[n] and s[n]. One cycle per timestep, outputs change
  together.
- **No saturation logic yet.** Observed ranges leave 3+ bits of headroom, and
  the golden model (int32, no wrap) would flag any overflow as a mismatch in
  simulation. Whether wider layers need saturating accumulators is an M3
  decision, on M3's measured ranges.

---

## M2 result (2026-08-16)

hdl/common/lif_neuron.v matches the golden model bit-for-bit in simulation:
4,060 timestep checks across all four layers' traces (1,020 each for c1/c2/c3
at threshold 64, 1,000 for FC at threshold 256), zero mismatches, spikes and
membranes both compared with ===. Vectors are biased toward spiking neurons so
the reset path is genuinely exercised (~60% of vectors contain spikes).

The testbench itself was validated by fault injection: with LEAK_SHIFT
deliberately wrong, it reports 537/1020 mismatches; restored, all pass.
Lesson recorded on the way: iverilog's -P flag silently ignores overrides of
nested (non-top-level) parameters — the first injection attempt "passed"
because the bug was never applied. Fault injections must fail before they
count.

Status per the project brief's honesty rule: verified in SIMULATION only. Never
synthesised, never on hardware. M4 is where that changes.

---

## D0011 — Dense baseline in hand-written Verilog, not HLS

**Date:** 2026-08-16 · **Status:** DECIDED — supersedes the project brief's original plan

the project brief proposed Vitis HLS for the dense datapath. Two facts changed the
recommendation once the toolchain was real:

1. **Vitis HLS does not run on macOS.** The entire M2 discipline — edit,
   simulate, compare to golden, in seconds, locally — would break; every
   verification cycle would round-trip through the Vivado machine.
2. **Comparison hygiene.** The thesis's headline plot compares dense vs
   event-driven energy. If dense is tool-generated C++ and event-driven is
   hand-written Verilog, a reviewer can attribute the gap to authorship or
   tool quality. Same author, same language, same toolchain removes that
   objection.

Cost accepted: more code, written by a beginner. Mitigation: the dense engine
is structurally simple (nested counters, one adder, two BRAMs, the verified
LIF update), and every piece lands only after passing the golden traces.

---

## D0012 — M3 memory style: combinational reads, deferred BRAM discipline

**Date:** 2026-08-16 · **Status:** DECIDED, revisit at M4

The dense engine reads its weight ROM, input buffer and membrane RAM
combinationally and loads weights with $readmemh. Correct in simulation and
keeps the FSM one state simpler while the datapath is being proven. Block RAM
inference in synthesis, however, wants registered (1-cycle) reads — so M4
must add a registered-read pass, re-verified against this same testbench
before anything is synthesised. Synthesis happens in Vivado on the user's
Windows VM (no Vivado exists on the dev Mac).

---

## M3 result (2026-08-16)

The dense conv engine (hdl/dense/conv_layer.v) matches the golden model
bit-for-bit on all three conv layers, 16 samples x 4 timesteps each, every
output spike and every membrane word compared:

```
c1 (2->16,  34x34 -> 17x17):  591,872 comparisons, 0 mismatches
c2 (16->32, 17x17 ->  9x9):   331,776 comparisons, 0 mismatches
c3 (32->64,  9x9  ->  5x5):   204,800 comparisons, 0 mismatches
```

One engine, three geometries by parameter — the same source file serves all
conv layers. It contains no multiplier: spike-gated weight adds for the
convolution, the shared lif_update for the neuron.

Testbench validated by fault injection: one flipped bit in one weight
produces 5,148 mismatches; clean weights restore a clean pass.

Status: simulation only. Registered-read pass and synthesis are M4 work.

### D0012 pass applied (2026-08-16)

conv_layer.v converted to registered reads throughout: the kernel walk is now
read-cycle/add-cycle pairs, the membrane gets its own read state, and the
external spike/membrane ports carry one cycle of latency. All 1.13M golden
comparisons still pass on c1/c2/c3, and the M2 suite still passes.

Cost: ~2x cycles per timestep vs the combinational version (c1: ~38 cycles
per neuron vs ~19). A prefetch pipeline can reclaim most of that; it must
land, re-verified, before M5 records latency numbers, so the dense baseline
isn't measured at an artificial handicap. Left simple for now on purpose:
Stage B bring-up debugging wants the simplest correct FSM.
