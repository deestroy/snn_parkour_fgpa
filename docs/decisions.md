# Design decisions

Every judgement call, with the reasoning and the evidence. This file becomes
the thesis methodology chapter, so write entries as if a examiner will read
them. Newest at the bottom. Status is one of: OPEN, DECIDED, REVISITED.


## Index

| # | decision | date | status |
|---|---|---|---|
| D0001 | Start the golden model at one neuron, not at the network | 2026-08-15 | DECIDED |
| D0002 | Which LIF neuron are we actually building? | 2026-08-15 | DECIDED |
| D0003 | Input encoding: event counts or binary spikes? | 2026-08-15 | DECIDED |
| D0004 | The missing pool: reconciling the target network's parameter count | 2026-08-15 | DECIDED |
| D0005 | Weight initialisation: the network starts silent | 2026-08-15 | DECIDED |
| D0006 | M0 result: trained per-layer firing rates | 2026-08-15 | measurement |
| D0007 | Leak becomes shift-based: β = 0.875 | 2026-08-16 | DECIDED |
| D0008 | Weight scales restricted to powers of two | 2026-08-16 | DECIDED |
| D0009 | Correction: N-MNIST is class-ordered; early sparsity figures were digit-0 only | 2026-08-16 | recorded |
| D0010 | HDL language and M2 neuron conventions | 2026-08-16 | DECIDED |
| D0011 | Dense baseline in hand-written Verilog, not HLS | 2026-08-16 | DECIDED |
| D0012 | M3 memory style: combinational reads, deferred BRAM discipline | 2026-08-16 | DECIDED |
| D0013 | FC layer: fold the pool into weight-shared spike addressing | 2026-08-16 | DECIDED |
| D0014 | The board is a ZedBoard, not a PYNQ-Z2 | 2026-08-16 | recorded |
| D0015 | No official PYNQ image exists for the ZedBoard | 2026-08-16 | DECIDED |
| D0016 | M6 architecture: spike hand-off between layers | 2026-08-16 | DECIDED |
| D0017 | M6 architecture: membrane banking | 2026-08-16 | DECIDED |
| D0018 | M6 architecture: scatter mechanics | 2026-08-16 | DECIDED |
| D0019 | Event-driven neuron state is TWO words: membrane V and accumulator I | 2026-08-18 | DECIDED |
| D0020 | M6 engine interface fixed; testbench built and proven before the RTL | 2026-08-18 | DECIDED |

Board-day logs (D0015 parts 1–5, DDR notes) follow D0015. Milestone results (M1–M3, M6 step 1) are inline after the decisions that produced them.

---
- D0021 one AXIS wrapper, ENGINE parameter (divider caveat superseded)
- D0022 BURST measurement mode
- D0023 event-driven FC layer
- D0024 year-two platform: ES-Parkour recreation; robot geometry; P1
- RETRACTION C0028: M6 K=4 dense column (2026-08-20)


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

The project brief specifies `V[n] = beta*V[n-1] + sum(w*s[n])`, fire and reset when
`V >= V_threshold`. snnTorch's `snn.Leaky` defaults do **not** implement that.
Two differences, both confirmed by experiment:

**(a) When the reset is applied.** snnTorch's `reset_delay=True` computes the
reset from the *previous* membrane, so the threshold subtraction lands one
timestep after the crossing. The project brief describes an immediate reset. Same
input, same beta, same threshold:

```
reset_delay=True  (snnTorch default) : .........|.....|....|...................
reset_delay=False (the project brief's model): .........|....|....|....|...............
```

3 spikes vs 4 over 40 timesteps — a 33% difference in firing rate, which is the
independent variable of the entire thesis.

**(b) Strict vs non-strict threshold.** snnTorch fires on `V > threshold`
(it evaluates a Heaviside of `V - threshold`). The project brief says `V >=`. Driving
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

Chosen 2026-08-15. The project brief has been amended to describe the neuron we
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

**Date:** 2026-08-15 · **Status:** DECIDED — binarise (verdict below, after measurement)

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

The project brief's layer table does not close arithmetically. All three conv layers
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

The project brief proposed Vitis HLS for the dense datapath. Two facts changed the
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

---

## M4 Stage B RTL complete (2026-08-16)

hdl/dense/axis_conv.v wraps the dense engine in the DMA's stream protocol:
73 words in, engine timestep, 145 words out, per timestep; tlast on the final
word of the sample; spike maps streamed after EVERY timestep so hardware
verification keeps golden-model granularity. LSB-first bit packing, defined
in one comment block that exporter, wrapper and host must all cite.

Verified against golden word streams under a hostile handshake (random tvalid
gaps, random tready backpressure, 3 seeds): 9,280 output words bit-identical,
tlast correct on all 16 samples.

Two lessons paid for during bring-up of the bench itself:
- Sample AXI handshakes at the negedge, when signals are stable. Post-edge
  sampling silently dropped ~30% of delivered words and produced a drifting
  mismatch pattern that looked like a DUT bug and wasn't.
- A registered address register in front of a registered read port is TWO
  cycles of latency, not one; the wrapper drives the engine's read address
  combinationally from its bit counter for exactly this reason.

Remaining M4 work when the board arrives: loopback PASS (Stage A), then
rebuild the overlay with axis_conv + conv engine + weight hex as sources,
and host/conv_test.py comparing board output to golden. Simulation only
until then.

---

## D0013 — FC layer: fold the pool into weight-shared spike addressing

**Date:** 2026-08-16 · **Status:** DECIDED

The obvious FC implementation materialises the 2x2 sum-pool (values 0..4)
and multiplies by int8 weights — putting the datapath's first real multiplier
into the layer that holds 81% of the weights. The algebra folds instead:
W[n,j] * pooled[j] equals adding W[n,j] once per spike in pool window j, so
the engine walks the raw c3 spike map with 4 positions sharing each weight.
The pool never exists in hardware and the whole datapath stays
multiplier-free. Cost: 4x the inner iterations (~262k cycles/timestep,
same order as C1). Alternative recorded in case cycle budget ever tightens.

Consequence for M6: the event-driven engine can scatter c3 spike ADDRESSES
directly into FC weight lookups — no pool stage exists there either. One
c3 spike touches 128 weights (its pool window's column), which sets the
scatter fan-out for the M6 design discussion.

**Verified:** hdl/dense/fc_layer.v, 16,384 comparisons (all 128 neurons'
spikes + membranes, 16 samples x 4 timesteps) bit-identical to golden.
Fault injection (one weight bit) fails 61 checks. Simulation only.

### D0012 debt paid: pipelined reads (2026-08-16)

Both dense engines now issue the next read while consuming the previous one
(S_MAC), with a prologue flag and a tail state. ~21 cycles/neuron for conv
(was 38), ~1027 for FC (was 2050). Full regression bit-identical: conv
1.13M checks, fc 16,384, AXIS wrapper 9,280 words, M2 suite 4,060.

---

## D0014 — The board is a ZedBoard, not a PYNQ-Z2

**Date:** 2026-08-16 · **Status:** recorded — the project brief's board table is superseded

The physical board that arrived is an Avnet/Digilent **ZedBoard**. Same chip
as the planned PYNQ-Z2 (Zynq XC7Z020-CLG484 vs -CLG400: same fabric — 53,200
LUTs, 4.9 Mb BRAM, 220 DSPs — different package/pinout), so every HDL file,
golden trace, testbench and resource-budget figure in this repo stands
unchanged. What changes is board-level plumbing:

- Vivado board file: ZedBoard ships with Vivado; PS preset differs, so the
  block design is rebuilt (same clicks) rather than reused.
- SD image: PYNQ v3.0.1 ZedBoard build (official).
- Boot: JP7-JP11 = 0 0 1 1 0 for SD boot. Power: 12 V barrel, not USB.
- M5 metering moves to the 12 V input rail; same INA226 method. INA226 on
  PMOD JA1.

Thesis framing: unchanged. Portability claim (the project brief's "secondary board")
becomes PYNQ-Z2 or Nexys 4 if one is later available; the ZedBoard is now
primary and the methodology names it.

---

## D0015 — No official PYNQ image exists for the ZedBoard

**Date:** 2026-08-16 · **Status:** DECIDED — bare metal via Vitis + OpenOCD from the Mac (resolution and board-day logs below)

pynq.io ships images for PYNQ-Z1/Z2, ZCU104 and newer boards only. Options:

A. Community prebuilt PYNQ 2.7 image (sambuls/Pynq2.7OnZedboard). Ready to
   flash; API we use is unchanged; pairs with Vivado 2020.2. Try first.
B. Build PYNQ 3.0.1 from source (Vivado+PetaLinux+Vitis 2022.1 on Linux,
   BSP port, hours). Correct but a week of infrastructure for a beginner.
C. Drop PYNQ; bare-metal/PetaLinux + C DMA driver. Loses the Jupyter flow.

Chosen: A now. If A boots and loopback passes → done. If the 2022.x .hwh is
refused → rebuild the bitstream in Vivado 2020.2 (parallel install). If A
fails to boot at all → B or C, and a serious conversation about acquiring a
PYNQ-Z2 (~$150), which would turn the ZedBoard into the secondary/portability
board the brief already wanted. This is the cost of the board swap: same
chip, thinner support path.

### D0015 update (2026-08-16): every prebuilt ZedBoard image is dead

Checked exhaustively: sambuls 2.7 host returns 404 and its Releases page is
empty; ECSAlab/pynq-zedboard is build-only; the 2019 OneDrive link in the
PYNQ forum's 3rd-party-images wiki (PYNQ 2.3/2.4) is dead. **No prebuilt
PYNQ image for the ZedBoard exists anywhere reachable in 2026.**

Remaining paths, both costed above: build PYNQ 3.0.1 from source (1-2 weeks,
Linux host + 2022.1 toolchain, known forum snags), or acquire a PYNQ-Z2 (~$150,
zero friction, ZedBoard becomes the secondary/portability board the brief
already planned). Recommendation stands: PYNQ-Z2. Awaiting the user's
decision after checking lab availability. Board-independent work (M6 design)
proceeds meanwhile.

---

## D0016 — M6 architecture: spike hand-off between layers

**Date:** 2026-08-16 · **Status:** DECIDED

Options weighed with the user: (a) one global spike FIFO, (b) per-layer
address lists, double-buffered, (c) direct broadcast with no queue.

**Chosen: (b), per-layer address lists.** Each layer keeps two small BRAMs
of spike addresses — one written by this timestep's LIF sweep, one read by
the next layer's scatter engine — swapped each timestep. Sized for the worst
case (every neuron firing: C1 4,624 x 13 bits x 2 ≈ 15 KB), so **overflow is
impossible by construction**.

Reasoning: the drawbacks of (b) are fixed and countable (BRAM, sequential
layers within a timestep, an unavoidable N-per-timestep LIF sweep). The
drawbacks of (a) and (c) are data-dependent — FIFO overflow forces a
stall-or-drop policy that either makes timing data-dependent or breaks
bit-exactness; broadcast couples every layer's timing to its neighbour's.
For a thesis whose deliverable is a clean measured crossover, design
parameters must not become experimental confounds. Address lists, not
bitmaps: a bitmap makes the consumer scan all N bits, which is dense-style
work creeping back in.

Consequence: every layer's scatter engine is testable in isolation against
golden traces via its input address list. The per-timestep LIF sweep is the
event-driven design's fixed cost and must be reported as such.

---

## D0017 — M6 architecture: membrane banking

**Date:** 2026-08-16 · **Status:** DECIDED

Options weighed with the user: (a) single-port, 1 RMW/cycle, no banks;
(b) K banks with stall-on-conflict; (c) K banks interleaved by output
channel; (d) dual-port 2 RMW/cycle in one bank with compare-and-forward.

Sizing that framed the choice (trained rates, per timestep): the busiest
layer, C3, needs ~28k membrane RMWs vs 461k dense reads — event-driven is
already ~16x ahead in work at K=1, before any parallelism.

**Chosen: (c), channel-interleaved banks — sequenced as K=1 first, then K=4.**
`bank = output_channel mod K`: a spike's targets are one-per-channel at the
same position, so they spread across banks perfectly. Conflict-free for conv
layers by layout, no arbiter, no stall statistics to characterise. Option
(b) was rejected because conv targets cluster systematically (neighbouring
positions across every channel), so conflicts would be the norm rather than
the exception and the stall rate would become a quantity the thesis has to
defend.

The engine is parameterised by K from the first line. Bring-up and golden
verification happen at K=1 (the single-port design of option (a) as a
special case), then K=4 is a parameter change re-verified against the same
testbench. Consequences accepted with eyes open:
- K=1 vs K=4 becomes a *measured* delta on the crossover plot, not a baked-in
  assumption. If banking doesn't move the crossover, that is a finding.
- FC gains nothing from channel interleave (all 128 targets of a C3 spike are
  one "channel"); FC runs at K=1 by construction. If FC ever needs
  throughput, bank by neuron index — a separate decision.
- Weights must be banked alongside membranes so K weights arrive per cycle at
  K>1; the transposed weight layout (by input, targets contiguous) is
  designed with the bank split in mind from the start.
- The golden model / testbench must un-interleave bank-local addresses; the
  address <-> (bank, offset) mapping is one function, cited by both.

---

## D0018 — M6 architecture: scatter mechanics

**Date:** 2026-08-16 · **Status:** DECIDED

- **Targets computed on the fly**, not tabulated. Conv geometry (3x3, stride
  2, pad 1) means an input position lands in at most a 2x2 block of output
  positions across all C_OUT channels; a few adders and a bounds check per
  target. A precomputed target table would cost ~200 KB for C1 alone. Scope
  boundary worth stating in the thesis: this relies on the network being
  regular convs; a general SNN accelerator cannot assume it.
- **Transposed weight layout** `W_T[ic, ky, kx, oc]`: one input's weights
  for a kernel tap are C_OUT contiguous bytes, banked by oc mod K at K>1.
  Pure re-ordering of m1_weights_int8.npz at export; golden model unchanged.
- **The per-target RMW is `V += w` only.** Leak, pending-reset and threshold
  happen once per neuron in the per-timestep sweep, using the SAME
  `lif_update.v` as the dense engine, on the membrane's accumulated input.
  Integer addition is associative, so event-driven and dense produce
  bit-identical membranes and spikes from the same golden traces — the
  golden model needs no changes, and the same testbench data verifies both
  designs. This is the concrete form of M6's done-when ("identical results
  to the dense design").

Engine outline recorded here so the code has something to be checked
against:

    for addr in spike_list[t]:
        (ic, iy, ix) = decode(addr)
        for (oy, ox) in output_positions(iy, ix):     # <= 4
            (ky, kx) = tap(iy, ix, oy, ox)
            for oc in 0..C_OUT-1:                       # K-wide at K>1
                V[bank(oc), off(oc, oy, ox)] += W_T[ic, ky, kx, oc]
    sweep all N: (V, s) = lif_update(V, 0); if s: append to spike_list[t+1]

Build order (each step golden-verified before the next): transposed-weight
export + address<->bank mapping in Python; C1 scatter engine at K=1; LIF
sweep + address-list writer; C1 event-driven == dense on all traces; then
C2/C3 by parameter, FC at K=1, and finally K=4 as a parameter flip.

### D0015 resolved (2026-08-16): bare-metal via Vitis, Mac as host, UART

Supervisor's call: continue with the ZedBoard (no PYNQ-Z2 access for a
while). PYNQ-from-source was the last way to keep the Jupyter workflow; it
needs PetaLinux, which needs a supported Linux host. The available school
box is CentOS 7 (unsupported by PetaLinux 2022.x), no sudo, no Docker — so
that path is closed, not merely disfavoured.

**Decided:** the ZedBoard runs a bare-metal C program built in Vitis
(installed alongside Vivado in the Windows VM): DMA setup, stream a sample
in, stream results out, over UART to the Mac. The Mac keeps every Python
piece — golden comparison, plotting, sweeps — as a UART client. Nothing in
hdl/, golden/ or sim/ changes; the AXIS wrapper and block design are
identical. host/ is rewritten: a C server on the board plus a Python client
on the Mac.

Consequence for M5, actually favourable: with no Linux on the ARM, "idle"
is genuinely idle — a cleaner power delta than a PYNQ board running Jupyter
would have produced. Consequence for M7: UART (~1 MB/s) is fine for M4-M5
sample counts; Ethernet (lwIP) is the documented upgrade if sweep throughput
demands it.

Aside: the Linux box's PATH includes /CMC/scripts, which suggests CMC
Microsystems tooling — Vivado may exist there. Checked separately; would move
synthesis to a 32-core machine but doesn't change the board-side plan.

### D0015 toolchain note (2026-08-16)

Vivado 2024.1 + Vitis 2024.1 both already installed in the user's Windows VM
(matched versions, no .xsa pairing concerns). Whole flow lives on one machine:
Vivado block design → Export Hardware (.xsa incl. bitstream) → Vitis
platform + bare-metal C app → program board over USB-JTAG → output over
USB-UART. The CentOS 7 box has CMC-licensed Vivado 2023-2024 and Vitis
2024-2025 too; useful for scripted/batch synthesis later, not on the critical
path. Synthesis of this design takes 2-3 min in the VM, so no speed argument
for moving it.

### First bare-metal build (2026-08-17)

loopback.elf built clean in Vitis 2024.1 after two one-line fixes, both
from the Unified IDE's System Device Tree flow (`-DSDT` in the compile
line): drivers are looked up by base address, not numeric device ID, and
the constant carries the driver's X-prefix — `XPAR_XAXIDMA_0_BASEADDR`.
Kept behind `#ifdef SDT` so the file also builds on classic platforms.
Size: text 36.6 KB, bss 824 KB (the two 400 KB DMA buffers). Not yet run.

### Board-day log (2026-08-17): programming from the Mac — status

**Works, verified on the ZedBoard from the Mac via OpenOCD 0.12:**
- JTAG chain enumerates (7z020 PL TAP + Cortex-A9 DAP); `reset halt` halts
  both cores reliably (a plain `halt` times out on parked cores).
- `pld load` accepts the ZedBoard bitstream without error.
- `ps7_init.tcl` runs unmodified under xsct-compat shims (mrd must return
  a string ending in 8 hex digits + newline; sourced at global scope;
  `configparams` stubbed). All three PLLs lock (PLL_STATUS 0x3F), DCI
  calibrates, DDRC reports normal mode with init complete (mode_sts 0x81).
- Silicon version auto-detects as 1.0 and that IS correct for this chip:
  the 2.0/3.0 tables both bus-fault on DDRC 0xF8006078, a register absent
  on this silicon.
- Root cause of "DDR reads back zero" found: BootROM leaves the L2 address
  filter at 0x40000001, routing all of DDR (<0x40000000) away from the DDR
  port. Disabling it (CPU-side write to 0xF8F02C00 = 0) fixes the routing.

**Not yet working:** with routing fixed, the first DDR access stalls the
core (bus hangs, no abort). Controller status is healthy but the DRAM does
not answer. Suspects, in order: DDRIOB output drivers not enabled by the
1.0 tables for this board's DDR3 (Vitis loads FSBL, which re-runs init
natively and would mask this); DDR clock gating; a `ps7_post_config` step
that xsct performs implicitly. Not a shim or sequencing error at this
point — a hardware-init detail specific to running the init from a debugger
instead of the FSBL.

**Practical fallback that avoids the whole DDR question:** link the loopback
program to run from **OCM (0x00000000, 256 KB)** instead of DDR, and shrink
the DMA buffers to fit — DDR then only matters as the DMA's target, and the
DMA reaches DDR through its own HP port, not the CPU's L2 route. Or: build
the FSBL in Vitis and JTAG-load *that* first; it initialises DDR the
production way, then hand off to the app. Both are next-session work.

### D0015 workaround (2026-08-17): run the loopback from OCM — TEMPORARY

To get past the stalled DDR access, the loopback program is relinked into
the Zynq's 256 KB on-chip memory (OCM at 0x0), and its DMA buffers shrunk
from 100,000 words (400 KB each way) to **12,288 words (48 KB each way)** so
the whole program fits. `host/board/loopback.c` N_WORDS reflects this.

**This is a bring-up workaround, not the design.** Once the DDR path is
understood (FSBL-style init, or whichever DDRIOB/clock detail the debugger
path misses), REVERT: N_WORDS back to 100,000 and the linker script back to
DDR. The Stage-B conv server needs DDR anyway — a real sample stream does
not fit in OCM alongside the code — so this cannot be left in place. Both
sizes are recorded here so the revert is a known step, not a rediscovery.

### Board-day log, part 2 (2026-08-17): the loopback runs; the UART was never enabled

OCM-relinked loopback loads and runs. Halting the CPU mid-run and mapping
the PC against the ELF's symbol table: cpu0 sits at `outbyte+0x8`, the
xil_printf character-output routine, spinning on the UART TX-ready flag.
Root cause: the ELF references UART0 (0xE0000000) only, and ps7_init.tcl
contains no UART clock or MIO writes at all — **the ZYNQ PS in the block
design has no UART enabled.** Vitis's BSP fell back to UART0, which has no
clock and no pins; the banner's first character never leaves.

Fix is in Vivado: ZYNQ7 PS → Peripheral I/O Pins → tick **UART 1** on MIO
48/49 (the ZedBoard's USB-UART), regenerate bitstream, re-export .xsa,
rebuild the Vitis platform + app. Not a software bug and not a Mac-side
tooling bug: everything from JTAG through ELF execution is now proven.

Lesson for the walkthrough: "Run Block Automation" applies the board
preset for DDR/clocks but does not necessarily enable UART; verify it in
the PS dialog before generating. Added to Stage A §3.

Also learned: symbol-table lookup of a halted PC (host-side Python over the
ELF, no toolchain needed) is a fast, decisive way to see where bare-metal
code is stuck. Kept as a technique.

### Board-day log, part 3 (2026-08-18 00:xx): UART path proven; it's the BSP's stdout choice

Correction to part 2: the "PS has no UART enabled" diagnosis was WRONG. It
rested on register reads made through the halted CPU while the running
program's MMU was on — every such read returned 0 and was garbage. Reading
through the AHB-AP (a `mem_ap` target on the DAP, which bypasses the CPU)
shows UART1 fully configured by the BSP: CR=0x114 (TX/RX on), 115,207 baud,
MIO 48/49 routed, clocks on. The Vivado UART1 rebuild was harmless but was
not the fix (the design likely already had UART1).

Decisive test: 200 bytes written into UART1's TX FIFO by hand over the
AHB-AP arrive on the Mac intact. Zynq → MIO → Cypress bridge → USB → Mac
all work. The program spins in `outbyte` because the standalone BSP's
stdout is bound to **ps7_uart_0** (8 refs to 0xE0000000 in the ELF, none
to UART1) — polling an unclocked UART0 status register that never reads
"ready". Fix: platform BSP settings, stdin/stdout → ps7_uart_1. Rebuild.

Rules that would have saved two hours, now standing:
1. Never trust CPU-side memory reads of a halted target that has run a
   program — its MMU is on. Read peripherals via the AHB-AP mem_ap.
2. When a program hangs on I/O, drive the peripheral by hand from the
   debugger first. If that works, the bug is in the software's addressing,
   not the hardware — no Vivado round trip needed.

### Board-day log, part 4 (2026-08-18 ~01:00): console clean; DMA blocked on the CPU's PL routing

Progress: with the L2 address filter left at BootROM state, the paced
console prints perfectly — full banner, then the program's own DMA
diagnostics: `DMA at 0x40400000 SG=0 mm2s=1 s2mm=1`. Two earlier
"findings" are hereby retracted: the every-second-character loss was NOT
the BSP's outbyte (my own TXEMPTY-paced writer lost bytes identically) —
it was my "disable the L2 filter" change from part 1, which sent CPU
peripheral accesses down the DDR port. Reverting it fixed the console
instantly.

The remaining blocker, precisely characterised:
- Through the AHB-AP (bypassing the CPU), the AXI DMA at 0x40400000 is
  healthy: clocked (FPGA0_CLK on), out of reset (FPGA_RST_CTRL=0), level
  shifters on, DMASR=0x10002 (idle) on both channels.
- Through the CPU, the program reads MM2S_DMASR=0, S2MM_DMASR=1 — different
  values — and XAxiDma_CfgInitialize then hangs in its reset-complete poll.
- So the CPU's path to the PL (GP0, 0x40000000+) is misrouted, while its
  path to PS peripherals (0xE000_0000) is fine at BootROM filter state.
  The PL310 L2 address filter (0xF8F02C00/04) decides which of the two L2
  master ports an address takes; BootROM sets start=0x40000000 which is
  wrong for PL access, and "disabled" is wrong for peripherals. The FSBL
  sets the correct pair on a normal boot; JTAG loading skips the FSBL, and
  ps7_init.tcl does not touch these registers.

Next session, in order:
1. Look up the exact PL310 filter values Xilinx's FSBL writes for Zynq-7000
   (in the FSBL source or `boot.S`), instead of guessing: likely
   filter END = 0xFFF00000-ish and START = 0x00100001-ish so that DDR goes
   to M1 and everything else (OCM, peripherals, PL) to M0. Verify with a
   CPU-side UART flood AND a CPU-side DMA register read matching the AHB-AP
   view — both must pass.
2. Alternative that removes the whole class of problem: build the FSBL in
   Vitis (it's a template), JTAG-load and run it first, then load the app.
   The FSBL does ps7_init, DDR, and L2 setup the production way, which
   would also un-block DDR and let N_WORDS revert to 100,000.

Status: not yet LOOPBACK PASS. Every layer down to the DMA's own registers
is verified working; the last gap is one L2 register pair.

### Board-day log, part 5 (2026-08-18 ~01:40): LOOPBACK PASS

`LOOPBACK PASS: 12288 words round-tripped bit-identical` on the ZedBoard,
programmed and observed entirely from the Mac.

**The actual root cause of the whole night**, from UG585 devcfg registers:
`reset halt` asserts SRST, which leaves `devcfg.CTRL[PCFG_PROG_B] = 0` —
the PL's PROGRAM_B line held low, the fabric held cleared. `pld load` then
streamed the bitstream into a fabric that discarded it. Consequences that
looked like four different bugs: PL reads returned stable garbage that
differed by access path (the "CPU sees different DMA registers" mystery),
the first PL *write* hung the bus (no slave to respond), and the DAP went
sticky. My very first load of the evening had lit the DONE LED only because
it followed a plain `halt`, not an SRST — I never noticed the difference.

The L2 address filter was innocent throughout: UG585 confirms its reset
value (start 0x40000000 enabled, end 0xFFF00000) routes DDR to M0 and
everything else to M1, which is exactly right. My "disable it" change from
part 1 broke peripheral routing and caused the every-second-character UART
loss; both retracted. `boot.S`, the FSBL and `ps7_init` never touch it.

Fix, in host/mac/zynq_load.tcl: after ps7_init, pulse PCFG_PROG_B low→high
(devcfg.CTRL bit 30), then `pld load`, then ps7_post_config — the xsct/FSBL
order. Verified: a DMA write completes and reads back changed; the program
runs to PASS.

Also learned tonight, for the record:
- Never trust CPU-side memory reads of a halted target that has run a
  program (MMU on). Use the AHB-AP mem_ap.
- devcfg STATUS[PCFG_DONE] and MCTRL read 0 over the debug port on this
  part regardless of true state; don't gate on them.
- A wedged FTDI adapter (MPSSE assertion) recovers with a pyusb device
  reset — no replug needed.
- Vitis 2024.1: BSP stdin/stdout are in the domain's bsp.yaml
  (ps7_uart_1 for the ZedBoard); the platform GUI is unreliable for it.
- The BSP's xil_printf was NOT dropping bytes; the paced writer in
  loopback.c is now unnecessary but harmless (kept: it's simple and it
  gives the program its own diagnostics path with no library dependence).

### DDR status after LOOPBACK PASS (2026-08-18 ~02:00) — unresolved, well-characterised

With the PROG_B/config problem fixed and the L2 filter at its correct reset
state, DDR was retested cleanly. It still does not retain data: CPU-side
writes wedge the core, AHB-AP writes eventually bus-fault, reads return 0.
Yet every controller-side status is healthy — PLLs locked (0x3F), DDRC
normal mode + init done (mode_sts 0x1F1), DCI calibrated, PHY debug regs
populated. This is the signature of a DDR PHY that cannot actually talk to
the DRAM chips.

Silicon revision evidence: DDRC register 0xF8006078 bus-faults on a plain
read on fresh silicon (before any init) — it exists on rev 2.0/3.0 (whose
init tables write it) and not here. Together with MCTRL/IDCODE reading rev
0, this is a **rev-1.0 (2012 engineering-sample-era) XC7Z020** on a Rev-C
ZedBoard. Rev-1.0 silicon has known DDR limitations and the ps7_init 1.0
tables are the correct ones for it; they still do not bring the DRAM up
under debugger-driven init.

Not resolvable from the Mac tonight. Two remaining discriminators, both
needing the user's Vitis session:
1. Build the FSBL (Vitis template), JTAG-load and run it, watch its UART
   output: it prints DDR init status and, if DDR is bad, says so. If the
   FSBL brings DDR up, the difference is something the FSBL does that
   ps7_init.tcl doesn't, and it becomes our loader.
2. If the FSBL also fails: this board's DDR is unusable (hardware), and
   the design must live in the 192 KB OCM.

**Consequences for the project if DDR stays unavailable:**
- Stage A/B run from OCM. The C1 conv test needs ~4.6 KB per sample plus
  code — fits, with N_WORDS-style buffer discipline; the FC layer's traffic
  is smaller still. So M4 Stage B is NOT blocked.
- M5/M7 sweeps that stream many samples fit if the host streams them one at
  a time (which UART throughput demands anyway).
- The 100,000-word loopback revert stays deferred: N_WORDS remains 12,288
  and loopback.c documents why. Revert instructions unchanged from the
  D0015 workaround note.

---

## D0019 — Event-driven neuron state is TWO words: membrane V and accumulator I

**Date:** 2026-08-18 (overnight) · **Status:** DECIDED

Writing D0018 as code (golden/eventdriven.py) exposed a subtlety the prose
glossed over. The LIF leak and the pending-reset are functions of V[n-1]
alone. If scatter accumulated I[n] into the same word as V, the sweep could
no longer recover V[n-1] and both leak and reset would be computed on the
wrong value. So the event-driven engine keeps two words per neuron: the
membrane V and an input accumulator I. Scatter does I += w; the sweep does
(V, s) = lif_update(V, I) and zeroes I. This is exactly what the dense
engine does with V in RAM and I in a register — the difference is only that
here I must persist across the whole scatter phase, so it needs storage.

Cost: 2 x 16 bits per neuron instead of 1 x 16. For the target network's
21,632 neurons that is +42.2 KB of BRAM (membrane budget doubles from 42.2
to 84.4 KB; total on-chip 161 -> 203 KB, still 33% of the 612.5 KB). Must
be stated in the resource comparison: the event-driven design carries this
extra state and the dense design does not.

**Verified in software (M6 step 1):** golden/eventdriven.py reproduces the
golden traces bit-for-bit on c1/c2/c3 at K=1 AND K=4 (1.13M checks, 0
mismatches), and the D0017 bank mapping is proven bijective and
conflict-free for K in {1,2,4,8}. Measured work per timestep at trained
rates: C1 14.1k RMWs vs 83k dense reads (5.9x), C2 29.3k vs 373k (12.7x),
C3 38.3k vs 461k (12.0x). Sweep cost is N per timestep as predicted.
sim/export_ed_vectors.py imports the same mapping functions, so the
Verilog testbench cannot drift from the Python.

### DDR, further characterised (2026-08-18 ~03:30)

Read the decisive PHY register (UG585 dll_lock_sts, DDRC+0x1E0): **both
master DLLs locked**, slave DLLs at ~115 taps, all four per-slice results
populated with real values, phy_ctrl_sts 0xEE73. The PHY has trained and
locked to the DRAM clock, so "PHY cannot see the DRAM" is eliminated. Yet
data does not retain and AXI writes stall. The read-leveling debug block
(0xF80061F0) bus-faults: another register absent on this silicon rev,
consistent with rev 1.0.

Remaining explanations both need the FSBL to discriminate: the AXI-side
port path into the DDRC (port enables / arbitration a debugger-driven Tcl
init may leave wrong), or rev-1.0 silicon workarounds present in the C
ps7_init the FSBL compiles in but absent from the .tcl. This is as far as
the Mac can take it. Morning: FSBL build in Vitis (steps in
docs/overnight_2026-08-18.md), JTAG-run it, read its UART verdict.

---

## D0020 — M6 engine interface fixed; testbench built and proven before the RTL

**Date:** 2026-08-18 (overnight) · **Status:** DECIDED

The event-driven conv engine's port contract (hdl/eventdriven/ed_iface_shim.v
header): `clear` / `spk_we`+`spk_addr` (push input spike addresses, any
number, any order) / `start` (scatter all pushed, then sweep) / `done` /
registered `out_*` and `v_*` read ports in golden order. The only difference
from the dense engine's interface is the input: an ADDRESS LIST (D0016)
instead of a bit buffer.

The testbench for that contract (sim/tb_ed_conv.v, sim/run_ed_tb.sh) exists
NOW and is proven with the dense engine as DUT behind a thin shim that turns
address pushes into buffer writes: c1/c2/c3, 1.13M comparisons, 0
mismatches, spike counts matching the Python engine exactly; a single
dropped address fails 124 checks. When ed_conv_layer.v is written it
replaces the shim (`bash sim/run_ed_tb.sh c1 ed_conv_layer`) and the
harness does not change. This is the M2/M3 discipline applied to M6: the
check exists before the thing it checks.

### DDR — resolved as unusable on this board (2026-08-18 09:40)

The last discriminator was run: Vitis's own FSBL (compiled C ps7_init with
Xilinx's silicon-rev workarounds), JTAG-loaded from the Mac. It ran to
completion of its init and reached its status-print routine (halted PC in
`OutputStatus`; its output was invisible only because the FSBL domain's
stdout is UART0 — irrelevant to the DDR question). Immediately afterwards,
DDR still does not retain data: writes read back as 0 via the AHB-AP and
0xFFFFFFFF via the CPU. Combined with a locked, trained PHY and the
rev-1.0 register signature, this is hardware — DRAM that does not answer
on a 2012-era ZedBoard — not a missing software step.

**Decision: the design runs from the 192 KB OCM for the rest of the
project.** Consequences (unchanged from the overnight report, now firm):
Stage B fits; sweeps stream one sample at a time; the buffer-size revert
in loopback.c is cancelled rather than deferred; the methodology states the
board's DRAM was unavailable and that all state was on-chip — a stricter
version of the brief's own constraint. Nothing in M4–M7 is blocked. If a
PYNQ-Z2 or working ZedBoard appears, everything transfers unchanged.

Addendum (09:55): the user checked physically — the two DDR3 chips are warm
under load, so the DRAM is powered and clocked (consistent with PLL and PHY
DLL lock). Failure is therefore in the data path (DQ/DQS lanes or PHY
write-leveling on rev-1.0 silicon), not power or clock. Physically present,
powered, clocked, cannot move data: a board fault, not a software step.
This is the sentence the methodology uses.

**Correction (10:10): the "unusable" verdict above is PROVISIONAL.** Every
DDR test so far — mine and the FSBL run — read and wrote DDR through the JTAG
debug path, which produced four false diagnoses last night. The professor
who supplied the board reports it working. A program-driven self-test
(host/board/ddr_test.c: runs from OCM, patterns across five DDR regions plus
walking-ones, reports over UART) is the actual discriminator. Until it runs,
"DDR faulty" is a hypothesis, not a finding.

**Resolved (10:30): DDR is faulty — confirmed by native code, no debugger in
the loop.** host/board/ddr_test.c ran from OCM: banner printed, OCM control
region 0 errors (test logic proven), then the first CPU write to DDR
(0x00100000) hung the core so hard the debugger could not halt it. A working
DRAM returns data, right or wrong; a hang means the controller never
completed the transaction. Chips warm, PHY DLLs locked, silicon rev 1.0,
CPU-native access stalls: a data-path fault on this board. Final.
Recommend telling the supervisor: everything on the board works except
DDR3; a replacement ZedBoard would be a 20-minute swap, otherwise OCM.

**Re-opened (10:45).** Supervisor confirms DDR worked for him — and his
"≤32 GB SD" remark means he booted Linux from SD, i.e. DDR carried a whole
OS. Every failing run here, including the FSBL, went through JTAG boot mode
plus a debugger SRST with init driven from a halted CPU. Zynq DDRIOB/DCI is
documented to want a power-on init; a warm SRST can leave it in a state
ps7_init does not fully recover while still reporting "done". Native-code
hang is therefore consistent with EITHER a board fault OR a JTAG-warm-reset
artefact. Decisive test: BOOT.BIN (FSBL + bit + ddr_test.elf) on SD, cold
power-up in SD boot mode, no debugger anywhere. "Final" retracted until
that runs.

**(10:55)** Attempted to reproduce a cold boot from the debugger: SLCR
PSS_RST_CTRL soft reset does not take while a JTAG debug session holds the
core (REBOOT_STATUS stays 0x2 = SRST, DCI status unchanged). The debugger
cannot fake a power-on init of the DDRIOB. Working hypothesis, now favoured
over "board fault": the DDR failure is an artefact of the JTAG-warm-reset
init path shared by every failing run. Discriminator unchanged: BOOT.BIN on
SD, cold power-up. If DDR passes there, the fix is to boot DDR-dependent
programs via SD (or via a JTAG flow that reruns the FSBL from BootROM state),
not via OpenOCD's reset-halt-init sequence.

**(11:20) SD cold boot works up to the FSBL.** With jumpers 00110 verified by
photo and BOOT.BIN on a FAT32/MBR card: BOOT_MODE=5 (SD), REBOOT_STATUS
0x60000000 (BootROM handoff OK, error code 0), CPU parked in the FSBL's
OutputStatus. So BootROM->FSBL succeeded from a genuine cold boot; the FSBL
is stuck printing to UART0 (its domain's stdout), so it never reaches the
bitstream/app partitions -> no DONE LED, silent UART1. Fix: zynq_fsbl
domain bsp.yaml stdout->ps7_uart_1, rebuild platform, rebuild BOOT.BIN.
Encouraging for DDR: the FSBL passed its DDR init before parking on print.
Also learned: JP7-JP11 shunts move sideways (GND/SIG/3V3 columns), JP7=MIO2.

**(11:50) Retraction:** the FSBL is a RELEASE build (no debug strings, prints
nothing by design) with STDOUT_BASEADDRESS already 0xE0001000. Its silence
was never evidence; "stuck on UART0" was another theory built on nothing.
Real clues after cold SD boot: BOOT_MODE=SD, REBOOT_STATUS=FSBL_IN_MASK with
no error code, PCFG_DONE=0 (bitstream never loaded), DDRC mode_sts=0x1
(controller NOT init-done — the FSBL's own ps7_init left DDR less
initialised than the debugger path did). Next: FSBL rebuilt with
FSBL_DEBUG_INFO so it narrates its progress on UART1; splice into BOOT.bin
locally (Create Boot Image keeps reusing the stale fsbl.elf).

**ROOT CAUSE FOUND (12:15): the block design's DDR is configured for the
wrong memory part.** The .xsa says PCW_UIPARAM_DDR_PARTNO = "MT41J128M8
JP-125" (Vivado's generic default, x8 organisation) with default board/DQS
delays; the ZedBoard has MT41J128M16 HA-15E (x16) with its own trace
delays. "Run Block Automation" did NOT apply the ZedBoard preset to the PS.
Every DDR init — mine, the FSBL's, from JTAG or SD — has therefore been
training and addressing a memory geometry that is not on the board.
Observed signature matches: PHY locks (clock right), status says trained,
but data written to DDR is not there — and in the FSBL-initialised state
the contents visibly DECAY toward all-ones over seconds (un-refreshed /
mis-addressed DRAM). The debug FSBL stalled on its first print for the
sibling reason: the platform's compiled ps7_init.c predates the UART1
change (UART1 CR/MR read 0 after its init).

Not silicon (rev-1.0 registers were a red herring for DDR), not the board
(the supervisor's Linux image was built with the correct preset), not JTAG.
One dropdown: ZYNQ7 PS -> Presets -> ZedBoard -> Apply. Then re-export,
recreate the platform from the new .xsa (so ps7_init.c and the FSBL are
regenerated), rebuild BOOT.BIN, cold-boot ddr_test.

Retracting, in order: "DDR faulty (hardware)", "rev-1.0 silicon
limitation", "JTAG-warm-reset artefact". All three were wrong. The lesson
that survives: when a peripheral trains-but-fails, check what the DESIGN
told it to expect before reading its status registers a dozen ways.

**RESOLVED (13:00): DDR WORKS.** With the platform recreated from the .xsa
that carries the ZedBoard preset (MT41J128M16, correct PHY delays, correct
PLL/MIO), the debug FSBL boots from SD, narrates every step, initialises
DDR, loads the bitstream (FPGA Done), and its own DDR memory test passes.
Then, in that state: words written to DDR at 0x100000/0x08000000/0x1FF00000
read back bit-perfect after 50 ms and after 2 s, from the AHB-AP and from the
CPU. `deadbeef cafef00d 12345678 a5a5a5a5` — the first DDR round trip to
survive on this board.

Root cause, final: Run Block Automation did not apply the ZedBoard preset;
the PS was configured for Vivado's default MT41J128M8. Every layer of
software above it (my Tcl init, xsct-style init, the FSBL, the native
program) was correctly initialising the wrong memory. Retracted for good:
"hardware fault", "rev-1.0 silicon DDR limitation", "JTAG artefact",
"BSP outbyte", "no UART enabled".

One loose end: the FSBL stops at "No Execution Address JTAG handoff"
because ddr_test is linked at OCM 0x0, which the Zynq FSBL treats as the
"no app / hand to JTAG" sentinel. Fix: link apps at OCM 0x00000100 (or any
non-zero base) — or use DDR now that it works. Then the FSBL hands off and
the app runs unattended from SD.

Consequences: 512 MB back. loopback N_WORDS returns to 100,000; apps link
to DDR again; the JTAG loader gains a proper "run FSBL first" stage (or we
simply boot from SD, which is what a deployed board would do anyway). Stage
B proceeds with the CORRECT bitstream — the FIFO/engine bitstream must be
rebuilt on top of the fixed block design, since the old ones carry the wrong
PS config.

**(14:00) Stage B on silicon, first attempt:** cold SD boot -> FSBL ->
`SUCCESSFUL_HANDOFF` -> conv_server running from DDR, PING round trip OK
over the framed UART protocol. First RUN_CONV stalled: MM2S DMADecErr,
channel halted. Cause in the .xsa: PCW_USE_S_AXI_HP0=0 and the DMA masters
have no address map — applying the ZedBoard preset reset the PS config and
cleared the HP0 tick. Fix: re-enable HP0, connection automation, assign
DDR to both DMA masters in the Address Editor, rebuild. Documented in both
walkthroughs.

---

## M4 RESULT (2026-08-18 15:30) — BOARD PASS

`BOARD PASS: 16 samples, 9280 words, bit-identical to the golden model
(4.96 s, 310 ms/sample incl. UART)`

The C1 dense conv engine, synthesised from hdl/dense/{lif_update,
conv_layer_c1, axis_conv, axis_conv_top}.v with the int8 weights inlined,
running on the ZedBoard's XC7Z020, booted from SD (BootROM -> debug FSBL ->
DDR -> bitstream -> conv_server in DDR), fed golden N-MNIST samples over the
framed UART protocol by host/uart_client.py, returned every output spike word
identical to golden/network.py. M4's done-when ("call the accelerator and
get correct results back from real hardware") is met.

Final design facts: ZedBoard preset applied (DDR MT41J128M16), S_AXI_HP0
enabled with both DMA masters mapped 0x0-0x1FFFFFFF, single FCLK_CLK0
domain, no clocking wizard, no FIFO. Everything runs from DDR with default
linker scripts. Timing per sample is UART-bound (292+580 words at 115200
baud ~= 76 ms of wire time; the rest is Python + protocol overhead) — the
engine itself is far faster, and M5 measures that properly.

Path here, for the record: PYNQ unavailable -> bare metal -> OpenOCD from
the Mac -> PROG_B (loopback pass) -> the DDR "fault" that was a wrong DDR
part in the block design -> SD boot with debug FSBL -> HP0 cleared by the
preset -> baked weights (Vivado can't find $readmemh files) -> PASS. Every
wrong turn is logged above with its retraction.

---

## M6 step 2 result (2026-08-18) — scatter unit RTL, K=1

hdl/eventdriven/ed_scatter.v is the first event-driven RTL: one spike address
in, `I[n] += W_T[ic,ky,kx,oc]` over the <=2x2 output block x all C_OUT, from
the transposed weight table, no multiplier. Verified against a NEW, tighter
checkpoint than the golden traces: the Python engine's accumulator I dumped
right after scatter(), before sweep() (sim/vectors/ed_<L>_i.hex).

    c1: 295,936 I words bit-identical, 25,078 spikes,  76 cycles/spike
    c2: 165,888 I words bit-identical, 26,017 spikes, 148 cycles/spike
    c3: 102,400 I words bit-identical, 16,777 spikes, 296 cycles/spike
    fault injection (one weight bit): 3,108 mismatches

Cycle cost is ~4.6 per (position, channel) RMW at K=1 — the sequential inner
loop, which is exactly the K seam: at K=4 the same loop issues 4 RMWs/cycle
into 4 banks. Per timestep at trained rates that is ~24k cycles for C1 vs the
dense engine's ~97k (4624 neurons x 21) — the first RTL-level number for the
event-driven advantage, before any banking.

---

## M6 RESULT, K=1 (2026-08-18) — event-driven engine bit-identical to dense

hdl/eventdriven/ed_conv_layer.v (address list + ed_scatter + sweep + V
memory, behind the D0020 interface) replaces the dense-engine shim in the
SAME harness with the SAME golden traces:

    c1: 591,872 comparisons bit-identical, 25,078 spikes
    c2: 331,776 comparisons bit-identical, 26,017 spikes
    c3: 204,800 comparisons bit-identical, 16,777 spikes
    fault injection (one W_T bit): 5,353 mismatches; shim still passes

M6's done-when — "identical results to the dense design" — is met in
simulation at K=1. Two engines, two loop orders, one set of bits.

Two bugs the harness caught, both invisible to inspection and both of the
"works on sample 0, drifts later" kind:
1. A 64-deep input FIFO silently dropped 81% of a timestep's spikes under
   the harness's burst push. Replaced by the D0016 address list, sized for
   the worst case (every input firing once), so overflow is impossible.
   This is not a workaround; it is the design D0016 specified.
2. That list's ring pointers used $clog2 bits over a non-power-of-two
   depth (2312) and indexed past the array once wr_p crossed 2312 -- first
   at sample 1, timestep 2. Depth is now rounded up to a power of two.
Also fixed pre-emptively: the sweep's I-zeroing needed its own cycle so
i_addr is held while the scatter unit performs the write (an off-by-one
that happened not to be the failing symptom).

Cost model, from the RTL: sweep = 4 cycles/neuron fixed (18.5k for C1);
scatter = ~76 cycles/spike at K=1 (~30k at trained rates for C1). Total
~48k vs dense ~97k for C1 per timestep. K=4 (next) attacks the scatter
term only; the sweep term is the event-driven design's floor and the M7
crossover lives where scatter shrinks below it.

---

## M6 RESULT, K=4 (2026-08-18) — banking verified; ~~the crossover is visible in cycles~~

**[RETRACTED IN PART, 2026-08-20 — see the C0028 retraction below. The
K-sweep verification and scatter measurements stand; the dense column of
the cycle table and the "K=1 loses on C2/C3" finding do not.]**

ed_scatter.v is now parameterised by K (bank = oc mod K, offset per D0017);
the K RMWs of one inner-loop step target K distinct banks and issue in one
cycle. ed_conv_layer.v did NOT change: the i_addr port translates golden
flat indices to (bank, offset), so the sweep and every testbench are
K-agnostic. Verified in the SAME harness, SAME golden traces:

    K=4 scatter vs Python I-dump: c1/c2/c3 bit-identical (564k words)
    K=4 full layer vs golden:     c1/c2/c3 bit-identical (1.13M checks)
    K=1 regression after refactor: unchanged; fault injection at K=4: 5,001

Measured cycles per input spike, scatter unit:
    C1  76 -> 22  (3.45x)    C2  148 -> 40  (3.70x)    C3  296 -> 77  (3.84x)
approaching the ideal 4x as fan-out grows.

Per-timestep cycle model at the golden traces' activity (busy digit-0
samples), sweep = 4 cyc/neuron, dense = 21 cyc/neuron:

           dense    ED K=1   ED K=4   |  dense/K1  dense/K4
    C1     97,104   48,276   27,116   |    2.0x      3.6x
    C2     54,432   70,532   26,628   |    0.8x      2.0x
    C3     33,600   83,993   26,584   |    0.4x      1.3x

**Finding, stated plainly:** at K=1 the event-driven engine LOSES to dense on
C2 and C3 — larger fan-out per spike (72, 144 targets) makes sequential
scatter cost more than visiting every neuron. Banking flips both. This is
the crossover the thesis is about, already visible in RTL cycle counts
before any power is measured, and it moves with K. M7 will measure it in
energy; this table is the cycle-level prediction it will be checked
against. Caveats to carry into M7: (a) these traces are on the busy side
of true mean activity; (b) cycles are not energy — the banked design has
4x the RMW datapath and 2x the neuron state (D0019), and only the meter
says what that costs.

Also: the sweep (4 cyc/neuron) is now the dominant term at K=4 for C1
(18.5k of 27.1k). The next lever after banking is the sweep — e.g. skipping
neurons whose I is zero AND V has decayed to zero, which the address-list
architecture makes possible. Not pursued now; recorded as the obvious M7+
optimisation, to be weighed against its bookkeeping cost.

---

## D0021 — One AXIS wrapper for both engines (ENGINE parameter)

**Date:** 2026-08-18 · **Status:** DECIDED

axis_conv.v / axis_conv_top.v gain `ENGINE` (0 dense, 1 event-driven) and
`ED_K`. Same framing, same words in and out; the only behavioural
difference inside is one line in the unpack state — dense writes every bit,
event-driven pushes an address only for a 1. Both engines are verified
through the SAME hostile-handshake testbench (9,280 words bit-identical:
dense, ED K=1, ED K=4). This is deliberate: identical framing and identical
host software are what make M7's dense-vs-event-driven energy comparison
apples-to-apples — the only variable on the board is the engine.

Synthesis variants generated (no $readmemh): conv_layer_c1.v (dense),
ed_scatter_c1.v (W_T inlined). Board default: ENGINE=1, ED_K=4.

Known-and-accepted for this first board run: ed_scatter decodes the spike
address with `/` and `%` by constants and translates i_addr with `/ %`;
Vivado will build small constant dividers. **[SUPERSEDED 2026-08-19:
D0020 rev 2 removed every divider from the address paths after they
failed timing; do not act on this caveat.]**

### D0021 board attempt 1 (2026-08-18 21:40) — LUT overrun, cause and fix

First event-driven bitstream failed in place_design: `[DRC UTLZ-1] LUT as
Logic over-utilized: 62,456 required, 53,200 available`. Cause: the
accumulator memory `imem` in ed_scatter.v was written from three different
addresses (sweep zero at p_off, scatter add at off_hold, clear at clr) and
read from two (p_off with a variable bank index, off_r). A block RAM has two
ports; Vivado could not map that and built 4,624 x 16 bits of flip-flops
with two 4,624:1 read-mux trees. iverilog has no notion of ports, so every
simulation passed. Lesson for the methodology chapter: "bit-identical in
simulation" says nothing about what the memories became -- the port
discipline has to be designed in.

Fix: each bank is now its own array with exactly ONE write port (address,
data, enable muxed by FSM state) and ONE registered read port (address
muxed: p_off when idle, off_r when scattering); the external i_rdata is a
post-register bank select. Every access lands on the same clock edge as
before, so the sweep handshake with ed_conv_layer is unchanged -- confirmed
by the cycle counts being identical (76/spike K=1, 22/spike K=4) and by
every check re-passing: scatter vs I-dump (K=1, K=4), engine vs golden
(K=1, K=4, 591,872 comparisons each), AXIS wrapper hostile handshake
(ED K=4 and dense, 9,280 words), verilator lint clean.

Also seen on the way (all Vivado process, not design): the ENGINE=1
customisation had not been applied on the first rebuild (the .xsa said
ENGINE=0 -- caught by unzipping the .xsa before writing the card);
"Spawn failed" during validation while background block runs were active;
a half-regenerated interconnect (`auto_us` clock unconnected) after that;
M_AXI_S2MM briefly unconnected until connection automation re-ran. The
standing check before any card write: unzip the .xsa and grep the .hwh for
ENGINE, ED_K, PCW_USE_S_AXI_HP0 and the DDR part.

## M6 RESULT ON THE BOARD (2026-08-18 22:25) — event-driven engine, K=4, BOARD PASS

`BOARD PASS: 16 samples, 9280 words, bit-identical to the golden model
(4.91 s, 307 ms/sample incl. UART)`

Same block design, same conv_server, same uart_client.py, same 16 golden
samples as the M4 dense pass this afternoon; the only change is the engine
behind the AXIS wrapper: axis_conv_top with ENGINE=1, ED_K=4 (ed_conv_layer
+ K=4-banked ed_scatter_c1, address list 4096 x 12, weights inlined). Booted
from SD: BootROM -> debug FSBL -> DDR -> bitstream -> conv_server at
0x100000. M6's done-when — "the event-driven design produces identical
results to the dense design" — is met on silicon.

What the pass does and does NOT prove. The two engines are DESIGNED to emit
identical words, so the client output alone cannot tell which fabric ran.
The chain of evidence that it was the event-driven one: the .xsa's .hwh
says ENGINE=1 ED_K=4; the PL partition of the BOOT.bin on the card is
byte-for-byte (1.000000, after undoing bootgen's 32-bit byte swap and the
dropped .bit length word) the bitstream inside that .xsa; and the previous
BOOT.bin, checked the same way, was byte-for-byte the 15:07 dense bitstream
(0.958 against the ED one) — which is how the stale-platform mistake was
caught before the card was written. That comparison is now the standing
pre-write check, alongside the .hwh grep.

Timing is UART-bound (307 vs 310 ms/sample this afternoon): the host link
hides the engine entirely. Separating the two engines in TIME and ENERGY is
exactly M5+M7's job (meter on the rail, timestamps at the DMA), not this
run's. Resource numbers (LUT/FF/BRAM/DSP) for the ED build to be taken from
Vivado's utilization report and recorded next to the dense build's.

Process lessons tonight, all recorded above: (1) block-design parameter
customisation must be verified in the .hwh, not assumed; (2) the Vitis
platform carries the bitstream — Create Boot Image reuses it, so the
platform must be updated (or the .bit path overridden) after every Vivado
export, even when the ELF is unchanged; (3) "bit-identical in simulation"
says nothing about whether the memories became block RAM — port discipline
is a design input (the 62k-LUT overrun).

### Resource use, C1 on the XC7Z020 (2026-08-18, post-implementation, whole design incl. DMA + interconnects)

| build | LUT | LUTRAM | FF | BRAM tiles | DSP | Vivado est. total on-chip power |
|---|---|---|---|---|---|---|
| event-driven, ENGINE=1, K=4 (the 21:53 bitstream, BOARD PASS) | 3,383 (6.4%) | 218 | 4,036 (3.8%) | 13 (9.3%) | 2 | 1.731 W (confidence: medium) |
| dense, ENGINE=0 (stale in-memory implemented design; TO CONFIRM by re-opening that run) | ~1,860 (3.5%) | 161 | ~2,510 | 3 (2.1%) | 0 | — |

Both numbers include the fixed platform (AXI DMA, two interconnects,
reset block) — roughly 1,000–1,500 LUTs of that is not the engine. What
the delta says: the event-driven layer costs ~4x the block RAM (address
list 4096x12, four accumulator banks, membranes vs. the dense engine's
membranes + input buffer) and ~1.5–1.8x the logic of the dense one, for
identical outputs. The two DSPs are the constant multipliers in the
scatter address arithmetic (a "post-M7 optimisation" already noted).
This is the "the event-driven machinery costs area — and therefore
static power — itself" half of the thesis argument, in numbers. Vivado's
1.731 W is the estimate M5's meter is meant to be compared against
(most of it is the ARM PS, not the fabric; the meter reads the board rail).

### 22:40 addendum — the event-driven build FAILS TIMING (WNS −4.534 ns, TNS −287 ns at 100 MHz)

Seen in the Design Runs tab after the pass. The bitstream that produced
tonight's BOARD PASS does not meet setup timing: its worst path needs
~14.5 ns against a 10 ns clock. It worked at the bench because typical
silicon at 25 °C is faster than the worst-case model Vivado signs off
against — that is luck, not margin. Consequences, stated plainly:
tonight's result is a FUNCTIONAL verification (correct words on real
hardware) and nothing more; no timing, latency or energy figure may be
taken from this bitstream; the failure must be fixed and the board run
repeated with WNS >= 0 before M5 measures anything on the ED design.
Suspected path (to be confirmed from the timing report): the constant
`/` and `%` in ed_scatter.v's flat-to-(bank,offset) translation and spike
decode, feeding BRAM addresses combinationally — the D0021 "post-M7"
optimisation, now mandatory. Standing rule from here: WNS is checked
alongside the .hwh parameters before any card is written.

### 23:00 — timing fix: incremental address registers in the scatter unit

The timing report (report_timing, five worst paths) put every violation on
one path, repeated per bank: `oc_reg -> off_r1 (x17, DSP48) -> off_r (x17,
DSP48) -> bank BRAM address`, 13.8 ns data path (9.6 ns logic: two chained
3.84 ns DSP multiplies) against 10 ns. That was the bank offset
`((oc/K)*H_OUT + oy)*W_OUT + ox` and the weight row `((ic*3+ky)*3+kx)*C_OUT
+ oc` recomputed combinationally from the loop counters every cycle.

Fix: both are now 16-bit REGISTERS initialised once per spike (from the
decoded iy/ix, shift-adds on 6-bit values) and stepped by constants as the
loops advance — oc += K: off += H_OUT*W_OUT, row += K; ox += 1: off += 1,
row -= 2*C_OUT; oy += 1 (ox back to ox_lo): off += W_OUT - (ox - ox_lo),
row += 2*C_OUT*(ox - ox_lo) - 6*C_OUT; and on both wraps oc -> 0: off -=
(C_OUT/K - 1)*HW, row -= C_OUT - K. Register -> one adder -> register; no
multipliers remain on the address path (the two DSPs should disappear).
Verified: scatter vs I-dump K=1/K=4, engine vs golden K=1/K=4, AXIS
hostile handshake ED and dense, lint clean — cycle counts unchanged (76 and
22 per spike), i.e. the change is invisible to the harness, as intended.

Next suspect if WNS is still negative after the rebuild: the external
`i_addr -> p_off` translation (constant `/ 289`, `% 289` in LUTs) into
the same BRAM address mux — not in the top five, so probably passing but
with little margin. Proper fix if needed is a pipelined sweep in
ed_conv_layer (read n+1 while updating n), which would also cut the sweep
from 4 to ~2 cycles per neuron — a design improvement, not just a timing
patch — but only after WNS says it is needed. Standing rule stays: WNS
checked before any card is written.

## D0020 rev 2 — Event-driven addresses are packed FIELDS, not flat indices

**Date:** 2026-08-18 23:40 · **Status:** DECIDED (supersedes the address
format in D0020; the rest of D0020 stands)

**Trigger.** After the incremental-offset fix, the fresh timing report put
the worst path (WNS −3.541 ns, 17 logic levels, 13.3 ns) on the spike
decode `iy = (a % 1156) / 34` in ed_scatter.v — a 12-bit divide-by-constant
in one cycle — and the sweep-port translation `i_addr / 289` was estimated
to sit right at the 10 ns edge behind it. Every `/` and `%` on an address
was a timing failure waiting to be found one build at a time.

**Options.** (1) Split the decode divider over two cycles: +1 cycle per
spike (~4.5% at K=4), leaves the sweep-port divider in place, probably a
third round. (2) Change the address format so no divide is needed
anywhere: the producers already walk in order and can keep the fields as
counters for free. Chose (2) — it removes the class of problem, adds no
cycles, and D0021 had already named it as the intended final design.

**Format.**
    spk_addr = {ic, iy, ix}   widths clog2(C_IN), clog2(H_IN), clog2(W_IN)
    i_addr   = {oc, pos}      widths clog2(C_OUT), clog2(H_OUT*W_OUT)
The fields are the flat index's mixed-radix digits, so golden ORDER and the
list semantics are unchanged; the address list simply stores 13 instead of
12 bits for C1. out_addr / v_addr (the layer's own memories) stay flat.

**Where the fields come from.** axis_conv.v's unpacker keeps (u_ic, u_iy,
u_ix) counters in lockstep with the flat bit index and pushes {ic,iy,ix};
ed_conv_layer's sweep keeps (sw_oc, sw_pos) alongside n and presents
{oc,pos}; ed_scatter decodes by bit-slicing (S_DEC is now wires) and
translates i_addr with `oc % K`, `(oc/K)*HW + pos` on a 4-bit oc — a
2-bit constant multiply, not a divider. ed_iface_shim (sim only) does
fields -> flat with a multiply, so the dense engine keeps proving the
harness. Testbenches pack the vector files' flat indices at the point of
use; the Python side and the vector files are untouched.

**Verified.** Scatter vs I-dump K=1/K=4 (76 and 22 cycles/spike — unchanged);
engine vs golden K=1/K=4 (591,872 comparisons each); shim harness C1, C2,
C3 (widths differ per layer — the width bug would show there); AXIS hostile
handshake ED K=4, ED K=1, dense (9,280 words each); verilator lint clean.
Board result: pending the next bitstream; the pass criterion is now WNS ≥ 0
AND BOARD PASS AND the byte-exact BOOT.bin check.

### 00:10 (2026-08-19) — third timing pass: LIF chain sourced from BRAM latches

After D0020 rev 2 the build had ONE failing endpoint, WNS −0.420 ns
(from 93 endpoints / −3.5 ns). The path: vmem block RAM output (2.45 ns
clock-to-out latch) -> lif_update (pending compare, subtract, add, spike
compare) -> out_mem/vmem write data, 10.04 ns. That is the intended
arithmetic; it was simply starting from the slowest possible source.

Fix, no cycles added: the sweep already has a wait state between read and
update. v_r2 <= v_r and i_r2 <= i_rdata are captured there (plain
flip-flops, ~0.5 ns clock-to-out) and lif_update reads those. For the
accumulator I to be readable in that state, i_addr for neuron n is now
presented one state EARLY (in the previous S_SW_ZERO, and at sweep start
for n=0); the zero write in S_SW_ZERO still sees n because the assignment
takes effect at the end of the state. Expected gain ~2 ns on both the V
and I paths. Verified: engine vs golden K=1/K=4 (591,872 comparisons
each), AXIS hostile handshake ED K=4/K=1 and dense (9,280 words each),
lint clean; sweep still 4 cycles/neuron.

Process note (recorded because it cost an hour): after copying changed
.v files, confirm Vivado sees them with `get_files *.v` + a `string first`
check on a marker string, and remember that the Timing tab and
report_timing read the implemented design OPEN IN MEMORY — click Reload
in the "out-of-date" banner after a run, or trust the Design Runs WNS
column, which is always the latest run.

### 00:35 (2026-08-19) — TIMING MET (WNS +0.735 ns, 0 failing endpoints) — but the .xsa lost the DMA address map

Third pass closed timing at 100 MHz: WNS +0.735 ns, TNS 0, 0 of 11,117
endpoints failing, "All user specified timing constraints are met." The
event-driven design is now sign-off clean on the fabric.

The delivered .xsa was NOT written to the card: its .hwh carries ZERO
memory ranges for axi_dma_0's M_AXI_MM2S / M_AXI_S2MM (the known-good
designs carry two, HP0_DDR_LOWOCM 0x0-0x1FFFFFFF). One of the evening's
module refreshes / interconnect regenerations dropped the Address Editor
assignments — the identical symptom to the 2026-08-18 morning HP0 problem
(DMADecErr on the first transfer). Standing pre-write check extended: the
.hwh must show ENGINE, ED_K, DDR part, HP0=1, AND two DMA MEMRANGEs to
HP0_DDR_LOWOCM; and in Vivado, before Generate Bitstream,
`get_bd_addr_segs -of [get_bd_addr_spaces axi_dma_0/Data_MM2S]` (and
Data_S2MM) must each return an HP0_DDR_LOWOCM segment.

## M6 RESULT ON THE BOARD, SIGN-OFF CLEAN (2026-08-19 00:55) — event-driven K=4, WNS +0.735, BOARD PASS

`BOARD PASS: 16 samples, 9280 words, bit-identical to the golden model
(4.91 s, 307 ms/sample incl. UART)` — run twice.

This supersedes the 2026-08-18 22:25 pass, which was functional only
(that bitstream failed timing by 4.5 ns). This bitstream: WNS +0.735 ns,
TNS 0, 0 failing endpoints at 100 MHz; ENGINE=1, ED_K=4, BAKED_WEIGHTS=1;
ZedBoard preset (MT41J128M16), HP0 enabled, both DMA masters mapped
0x0-0x1FFFFFFF; BOOT.bin PL partition byte-identical (1.000000) to the
.xsa bitstream; app at 0x100000; DDR-init FSBL. Same server, client and
16 golden samples as every previous pass.

What it took from the first ED bitstream to this one, all logged above:
(1) 62k-LUT overrun — accumulator banks given one write/one read port so
they map to BRAM; (2) WNS −4.5 — bank offset and weight row stepped in
registers instead of recomputed (two chained DSP multiplies removed);
(3) WNS −3.5 — D0020 rev 2, addresses carried as fields, every divider
on an address path gone; (4) WNS −0.42 — LIF chain fed from re-registered
V and I, not BRAM latches; (5) the DMA address map dropped by a block-
design refresh, caught by the pre-write .hwh check. Cycle counts never
changed (76 / 22 per spike K=1/K=4; sweep 4 cycles/neuron), and every
step re-passed the identical harness. The dense design needed none of
this — that asymmetry is a thesis observation, not an aside.

M6 done-when — "the event-driven design produces identical results to
the dense design" — met on silicon with a timing-clean bitstream. Next
on the critical path is unchanged: the meter (M5), then the crossover
sweep (M7) with both engines behind the same wrapper.

## D0022 — BURST mode: the engine at ~100 % duty for the meter (M5 infrastructure, feeds M7)

**Date:** 2026-08-19 · **Status:** DECIDED, desk-tested vs the mock; board run pending

**Problem.** Under RUN_CONV the engine works for microseconds per ~300 ms
of UART, so any meter on the board rail sees the ARM idle floor plus a
blip. "Power while running minus power while idle" would not measure the
engine. (Noticed while planning the multimeter-based first measurement.)

**Decision.** One new protocol command, BURST (0x03, host/protocol.md):
replay the last-loaded sample N times back to back through DMA + engine
with no UART traffic; time the loop; reply with N, elapsed ticks, tick
rate, a mismatch count (every iteration's 580 words compared with
iteration 1) and the CRC of the last output. The client verifies
mismatches == 0 and CRC == golden, then prints latency per inference.
Energy per inference = meter delta_W x elapsed / N. Same command for both
engines behind the same wrapper.

**Judgement call: where the clock lives.** Chose the Cortex-A9 global
timer (333 MHz) around the loop in conv_server.c over a cycle counter in
the fabric: no RTL/Vivado change, and it measures the SYSTEM latency the
meter actually sees (engine + DMA + loop). Engine-only cycles are known
exactly from simulation (dense C1 ~340k cycles/sample; ED K=4 ~110k), so
the loop/DMA overhead is the difference — if it turns out large, a fabric
counter is the follow-up. Recorded so the two numbers are never confused.

**Implementation.** conv_server.c BUILD_ID 2: sample kept in its own
buffer (every request payload lands in rx_words, so BURST's own payload
would otherwise clobber the sample's first word), one_pass() shared by
RUN_CONV and BURST, error 6 = no sample loaded. snn_link.py BurstResult +
crc_words; mock_server.py answers BURST with plausible fabric ticks so the
client arithmetic and checks are exercised; uart_client.py --burst N
[--sample S] [--burst-only]. C syntax-checked against stub headers (cannot
be compiled here); mock selftest passes incl. burst.

**Board procedure (unchanged bitstream):** rebuild conv_server in Vitis,
Create Boot Image, card, boot, `python3 host/uart_client.py --burst 2000`
-> PING must say build 2; expect ~1-3 ms/inference; mismatches 0; CRC ok.
Then the meter: `--burst-only --burst N` with N sized for the run
duration, idle reading before and after.

### D0022 amendment (01:15) — global timer read directly; tick rate cross-checked

The SDT BSP does not ship xtime_l.h (build error). conv_server.c now reads
the Cortex-A9 global timer's three registers at 0xF8F00200 directly
(64-bit, hi/lo/hi read) and enables it at start; TICKS_PER_S is the
ZedBoard-preset constant 333,333,333 (CPU 666.67 MHz / 2). Because that is
a constant and not a measurement, uart_client.py cross-checks the board's
elapsed time against Mac wall-clock around the call (must agree within 5 %
+ 0.5 s once the burst exceeds 1 s) and fails the check otherwise. The
mock now sleeps for the time it claims so the cross-check is exercised in
the selftest (400 iterations, 1.36 s). Syntax-checked; mock PASS.

## BURST RESULT ON THE BOARD (2026-08-19 01:30) — event-driven K=4: 1.51 ms/inference, deterministic

conv_server build 2 (BURST) on the timing-clean ED bitstream, SD boot.
16-sample BOARD PASS first, then:

| sample | iterations | elapsed | latency/inference | mismatches | CRC = golden |
|---|---|---|---|---|---|
| 0 | 2,000 | 3.029 s | 1,514.5 us (660/s) | 0 | yes |
| 1 | 1,000 | 1.543 s | 1,542.5 us | 0 | yes |
| 5 | 1,000 | 1.492 s | 1,492.5 us | 0 | yes |
| 9 | 1,000 | 1.556 s | 1,556.1 us | 0 | yes |
| 0 | 12,000 | 18.174 s | 1,514.5 us | 0 | yes |

Board timer vs Mac wall-clock agree to 5 ms over 18 s (tick rate
verified). Latency varies with the sample's activity (1.49-1.56 ms), as an
event-driven engine's should; the 12,000-iteration run reproduces the
2,000-iteration figure to the microsecond — the mode is stable for
meter-length runs.

Decomposition against the cycle model (100 MHz): scatter ~35k cycles
(1,567 spikes/sample x 22) + sweep 74k (4 x 4,624 x 4) + AXIS wrapper
bit-serial unpack/pack ~46k = ~155k cycles = 1.55 ms, vs 1.51 ms measured
-> DMA + software loop overhead is small; the wrapper's serial packing is
~30 % of the ED figure. It is shared by both engines (fair for the
comparison) but is a real cost to note; a word-parallel pack is a
post-M7 optimisation.

This is the latency half of the metrics table for the ED design at the
trained C1 activity. Energy needs the meter: `uart_client.py --burst-only
--burst 12000` gives an 18 s window; idle before/after; delta_W x 18.17 s
/ 12,000 = energy per inference. The dense engine gets the same command
once its bitstream is back on the card (ENGINE=0 rebuild).

### Standing next steps (2026-08-19 01:40) — also in README "Next steps"

1. Meter on the 12 V input: DMM first (professor's suggestion), INA226 if
   it cannot resolve the delta. Window: `uart_client.py --burst-only
   --burst 12000` (18 s, ~100 % duty). Energy/inference = delta_W x 18.17 s
   / 12000, reported next to Vivado's 1.73 W estimate.
2. Dense engine back on the board (ENGINE=0 rebuild): BURST latency and
   energy, and the exact utilisation to replace the provisional dense row.
Later: word-parallel AXIS pack/unpack; pipelined sweep; ED FC layer
(D0013); repo rename; delete the pre-rewrite backup.

## Latency in simulation, per sample, both engines (2026-08-19 overnight)

AXIS testbench gained a no-gap mode and per-sample cycle counters
(`NOGAP=1 CYCLES=file`; engine-busy probed hierarchically). C1, 16 golden
samples, 100 MHz: dense 436,247 cycles/sample, exactly constant (4.36 ms);
ED K=1 234,009 mean (2.34 ms); ED K=4 149,273 mean (1.49 ms), 3 % under the
board's measured 1.51 ms — so DMA + loop overhead is ~46 us and the model
is trustworthy. Predicted dense on the board ~4.4 ms. Wrapper pack/unpack
is 39-48k cycles of every figure (11 % dense, 26 % ED K=4). Table and raw
counts in experiments/latency_sim/. Hostile-handshake regression re-run,
still passing.

### 2026-08-19 overnight — ED engine verified on C2 and C3 (K=4)

`K=4 bash sim/run_ed_tb.sh c2 ed_conv_layer` -> 331,776 comparisons
bit-identical (26,017 input spikes); `c3` -> 204,800 (16,777 spikes). With
C1 already on the board, the event-driven conv engine is now verified
against golden for every conv layer of the network at the board's K. The
FC layer remains dense-only (D0013 records the event-driven FC as future
work). Not added to check_all.sh (runtime); run on demand.

## M7 REHEARSAL IN SIMULATION + per-layer latency (2026-08-19 overnight)

Two simulation results, both saved under experiments/ with raw counts.

**Firing-rate sweep, C1 (experiments/m7_sim/):** synthetic Bernoulli
inputs at ten densities (0.4 %-89 % realised), both engines, 30 runs, all
bit-identical. Dense flat at 436,247 cycles. ED K=1 = 121.9k + 75.8/spike,
crosses dense at ~45 % input rate. ED K=4 = 121.8k + 21.9/spike, never
crosses (300.8k at 89 %). Plot m7_sim_crossover.png, labelled SIMULATION.

**Per-layer, trained rates (experiments/latency_sim/layers.md):** dense
C1/C2/C3 = 3.90 / 15.26 / 18.63 ms; ED K=4 = 1.10 / 1.08 / 1.07 ms; conv
stack 37.8 ms vs 3.26 ms (11.6x). All 9 runs bit-identical (ED engine now
verified on every conv layer, K=1 and K=4). C1 ED K=4 agrees with the AXIS
bench (110,070 vs 110,078) and the board (3 %).

**What this means for the thesis, said plainly.** In LATENCY, on this
network at K=4, the event-driven design wins at every activity level
tested; there is no latency crossover to find. The crossover question is
therefore purely an ENERGY question — the ED design carries ~4x the BRAM
and ~1.7x the logic (static/leakage and clocking power that is paid every
cycle) against far fewer memory accesses (dynamic power). Which effect
wins, and at what activity, cannot be answered without the meter. That is
exactly CLAUDE.md's thesis and it is why the meter is the critical path.
It also sharpens M7's design: sweep activity, measure ENERGY per inference
for both engines, plot energy (not just latency) — the latency curve above
is the known half.

Also tonight: check_all.sh 17/17 green (ED AXIS, K=4 scatter, DMM
arithmetic and ED lint added); measure/dmm_protocol.md +
measure/manual_meter.py; docs/status_2026-08-19.md.

### D0017 note (2026-08-19) — K=4 is a baseline, not an optimum; K is an M7 variable

Recorded after the overnight sweep raised the question. K was chosen as
the first banking step under three constraints: K must divide C_OUT=16
(K=6 would leave 4 of 6 banks idle on the last group, 16=6+6+4);
power-of-two K keeps `oc mod K` a bit-slice, no divider on an address
path (see the 2026-08-18/19 timing history); and at trained rates the
scatter (35k cycles) is already below the fixed sweep floor (74k) at K=4,
so higher K buys little latency (K=8: ~11 % on C1) while doubling the
accumulator bank BRAMs each step — a static-power cost only the meter can
judge. Therefore: K in {1,2,4,8,16} is an experiment axis for M7
(latency already known from simulation; energy and area per K measured),
listed in README "Next steps / later". K=4 stays the baseline the meter
sees first.

### 2026-08-19 21:50 — the dense engine failed timing too (WNS −3.934); fixed the same way

The ENGINE=0 rebuild for the meter session was the FIRST dense build whose
WNS was ever read: −3.934 ns, 119 failing endpoints. The 2026-08-18 dense
BOARD PASS therefore gets the same caveat the first ED pass got — it was a
functional result on a bitstream that did not meet timing, and its
"engine is far faster than the UART" observation stands, but no timing or
energy figure may be taken from that bitstream. Timing was simply never
checked before the ED work made it a standing rule. Honest bookkeeping
cuts both ways.

The paths were the dense engine's own copies of the same two diseases:
(1) input-buffer address (ic*H_IN+iy)*W_IN+ix rebuilt from loop counters
each cycle — two chained DSP48s into the distributed-RAM read (13.7 ns);
(2) neuron_addr (oc*H_OUT+oy)*W_OUT+ox — two DSP48s into the vmem/out_mem
BRAM address ports (−1.5 ns); and, waiting behind them, the vmem output
latch feeding lif_update in one cycle.

Fix in conv_layer.v, mirroring ed_scatter's: all three addresses are now
registers stepped by constants as the loops advance (n_a raster +1; w_a
consecutive within a window, restarting at w_base = oc*C_IN*9; in_a
stepped kx +1 / ky +W_IN−2 / ic +H_IN*W_IN−2*W_IN−2 from a window base wb,
with the in_bounds mask still zeroing out-of-window DATA exactly as the old
ternary did). The membrane read is issued one state early (S_TAIL) and
re-registered in S_VRD (v_r2), so the LIF chain starts from a fabric FF —
zero added cycles. Address DSPs on the dense side should now be 0, which
also matches the design intent (the datapath itself has no multiplies:
spikes are binary, the leak is a shift).

Verified: conv c1/c2/c3 bit-identical (1.13 M comparisons), FC regression,
AXIS dense hostile + ED K=4 hostile, lint clean, and the per-sample cycle
count asserted EXACTLY 436,247 on all 16 samples — the fix changes wiring,
not behaviour or latency. conv_layer_c1.v regenerated. Board rebuild
pending; the pre-write rule (WNS >= 0) now applies to both engines.

### 2026-08-19 22:10 — use_dsp="no" on both engines: DSP count is now a checked property

Answering "why do we have 2 DSPs at all": the datapath never needed any
(binary spikes -> adds; shift leak; compares). Every DSP in every build was
Vivado mapping a variable-x-constant in my ADDRESS arithmetic onto a DSP48
-- and at 3.8 ns per traversal they were the timing problem, not a help.
The stepped-register fixes removed most; `(* use_dsp = "no" *)` on
ed_scatter and conv_layer (and the generated _c1 variants) now forbids the
rest (the ED sweep-port translation (oc/K)*HW+pos and the per-spike off_r/
wt_row init -- 2-to-5-bit operands, register-to-register, comfortably fabric
logic). Expected utilization after the next builds: DSP = 0 for BOTH
engines; anything else in the report is a flag. Harness re-run after the
attribute: scatter K=1/K=4, engine K=4, dense c1, AXIS both, lint -- all
bit-identical/clean, cycle counts unchanged (76/22 per spike).

### 2026-08-19 22:56 — dense build, sign-off clean: WNS +0.787, DSP = 0; the real dense resource row

Post-implementation, whole design incl. DMA/interconnects: LUT 3,167
(6.0 %), LUTRAM 218, FF 4,059, BRAM 7.5 tiles (5.4 %), DSP **0**, Vivado
total on-chip power estimate 1.706 W. Replaces the provisional row (from
the stale, timing-failing build: ~1,860 LUT / 3 BRAM / 0 DSP) — meeting
timing honestly cost the dense engine ~1.3k LUTs and 4.5 BRAM tiles of
address registers and re-registering, which narrows the dense-vs-ED gap:

| post-impl, timing-clean | dense | event-driven K=4 |
|---|---|---|
| LUT | 3,167 | 3,383 |
| FF | 4,059 | 4,036 |
| BRAM tiles | 7.5 | 13 |
| DSP | 0 | 1 (sweep-port translation; use_dsp now forbids it — expect 0 next ED build) |
| Vivado power est. | 1.706 W | 1.731 W |

The area asymmetry that remains is the honest one: the ED design's extra
5.5 BRAM tiles ARE the event-driven machinery (address list + I banks).
Vivado's own estimates now differ by only 25 mW — at or below its
resolution, which is itself an argument for the meter. BOOT.bin verified
byte-exact against this .xsa; ENGINE=0 confirmed; ED image kept at
host/mac/ed_k4_BOOT.bin.bak. Board run next: prediction 4.36 ms/inference.

### 2026-08-19 23:00 — dense build power breakdown (Vivado estimate): the engine is ~32 mW on a 1.7 W board

Implemented power report, dense build: total 1.706 W = dynamic 1.564 W +
static 0.143 W. Of the dynamic, PS7 (the ARM side) is 1.533 W (96 %); the
FABRIC — the thing the thesis compares — is ~31 mW: clocks 16 mW, signals
6 mW, logic 5 mW, BRAM 5 mW. Consequences, written down before the meter
session: (1) the idle->burst delta to resolve is ~32 mW = ~2.7 mA at 12 V
on a ~0.5 A baseline — a 4.5-digit bench DMM's job, hopeless for a
3.5-digit handheld (matches measure/dmm_protocol.md); (2) the fair
tool-vs-meter comparison for the ENGINE is this fabric number, not the
1.7 W total (the total is dominated by the ARM, identical for both
engines); both get reported (project brief: estimate next to measurement);
(3) the dense-vs-ED estimate gap at the fabric level is ~25 mW on ~30 mW
— the tool genuinely cannot rank the two designs. The meter can.

## DENSE RESULT ON THE BOARD, SIGN-OFF CLEAN (2026-08-19 23:10) — 4.409 ms/inference, data-independent, BOARD PASS

Dense bitstream (ENGINE=0, WNS +0.787, DSP 0), conv_server build 2, SD
boot. 16-sample BOARD PASS (9,280 words bit-identical), then BURST:
sample 0 x 2,000 -> 4,408.7 us/inference; sample 5 x 1,000 -> 4,408.7 us
(identical to 0.1 us — data-independent, exactly as a clock-driven design
must be); sample 0 x 4,100 (18.08 s, the meter-length window) -> 4,408.7
us. 0 mismatches everywhere, CRCs = golden, timer cross-checked.

Predicted from simulation: 4.362 ms + ~46 us DMA/loop overhead = 4.41 ms.
Measured: 4.409 ms. The cycle model is now verified on BOTH engines.

The board-measured latency table (C1, 100 MHz, timing-clean bitstreams):
| engine | latency/inference | rate | data-dependent? |
|---|---|---|---|
| dense | 4.409 ms | 227/s | no (0.1 us spread across samples) |
| event-driven K=4 | 1.51 ms (1.49-1.56) | ~660/s | yes, with activity |

Event-driven is 2.9x faster at trained activity, on silicon, both engines
sign-off clean behind the same wrapper, same server, same client, same
samples. Latency half of M7's table: done for these two points. Meter
windows rehearsed for both engines (~18 s each: ED --burst 12000, dense
--burst 4100). Everything now waits on the instrument.

### 2026-08-19 23:30 — the K axis filled in simulation (K = 1,2,4,8,16)

All divisors of C_OUT run through the same three benches, bit-identical at
every K. C1 totals: 234.0k / 177.5k / 149.3k / 135.2k / 128.2k cycles
(2.34 / 1.78 / 1.49 / 1.35 / 1.28 ms). Scatter cycles/spike: 76 / 40 / 22 /
13 / 8. Diminishing returns as D0017 predicted — the fixed sweep floor
dominates from K=4 up. Latency half of M7's K axis done; energy per K is
the meter's question. Table in experiments/latency_sim/README.md.

## D0023 — Event-driven FC layer (simulation): design choices

**Date:** 2026-08-20 (overnight) · **Status:** DECIDED overnight, flagged
for morning review — implemented and verified in simulation only.

The FC layer is where 81 % of the weights live, so an event-driven variant
matters for any whole-network event-driven claim. The dense engine costs
128 neurons x 256 windows x 4 positions ~= 131k cycles/timestep regardless
of activity; FC input activity (pooled C3) is the highest in the network
(~30 %), so this is also where event-driven has the least headroom — worth
having in simulation before the meter decides anything.

Judgement calls, options, and what was chosen:

1. **Fan-out structure.** A C1 spike touches a 2x2 window x C_OUT; an FC
   spike touches ALL 128 outputs through one weight column W[., j] (pool
   window j from the spike's coordinates by bit-slices — the pool's /4 is
   already folded into THRESHOLD=256, D0004/D0013). No window arithmetic,
   no bounds logic. Chose a SINGLE module (ed_fc_layer.v) holding queue +
   scatter + sweep rather than reusing ed_scatter, whose decode is conv-
   window-specific; the shared pieces (lif_update, the D0020 interface,
   the bank discipline) are reused unchanged.
2. **Cropping.** Spikes at y==4 or x==4 fall outside the floor-cropped
   pool and contribute nothing (fc_layer.v never addresses them). Options:
   filter at enqueue vs in the scatter. Chose ENQUEUE (cheaper: one
   compare on the fields; the queue then holds only work).
3. **Queue sizing.** Worst case 64x5x5 = 1,600 spikes/timestep -> depth
   2,048 (power-of-two ring, D0016 rule). 13-bit entries {c,y,x}.
4. **Banking.** Neuron n -> bank n mod K, offset n / K (bit-slices, K a
   power of two); every spike walks n in steps of K, so K banks are
   conflict-free by construction, same as D0017. K=4 default for symmetry
   with the conv engine; 128/K cycles per spike.
5. **Weights.** Transposed table W_T[j][n] (32,768 bytes) via $readmemh
   only — NO baked variant, because this layer is simulation-only until a
   board target needs it (the baked generators exist when it does).
6. **Timing discipline inherited, not rediscovered:** one write + one read
   port per bank, addresses stepped/sliced (never formulas), v_r2
   re-registration in the sweep, use_dsp="no".

### D0023 result (2026-08-20 00:20) — event-driven FC bit-identical, all K

ed_fc_layer.v + sim/run_ed_fc_tb.sh: 16,384 comparisons (every fc spike
and membrane, 16 samples x 4 timesteps, 13,273 c3 input spikes)
bit-identical to the golden traces at K = 2, 4, 8 and 16 on the FIRST
simulation run — the sign-off rules learned on the conv engine (one
write/one read port per bank, sliced/stepped addresses, v_r2/i_r2
re-registration, enqueue-side cropping, use_dsp="no") were applied at
design time instead of discovered on silicon. Lint clean. Note: K=1 and
K=N_OUT are not supported (zero-width slices); K in {2,4,8,...,64}.
Added to check_all.sh (18 checks). Every layer of the network now has a
verified event-driven implementation in simulation; the conv layers
additionally have C1 on silicon. Cost per spike: N_OUT/K cycles + 2
(128/4 = 34 at the default) — FC event-driven latency for M7's model can
now be computed rather than assumed.

## D0024 — Year-two platform: the ES-Parkour recreation is the simulator AND the policy source

**Date:** 2026-08-20 (overnight) · **Status:** DECIDED overnight, flagged
for morning review

Found on the GPU box: es_parkour_recreation — a complete MuJoCo-based
recreation of the ES-Parkour paper (event sim from depth, PPO teacher,
SNN-student distillation with DAgger, terrain curriculum, evaluation).
State: teacher TRAINED and strong (L3: 94-100 % on all four terrains;
L6: 91-97 % on step/hurdle); the paper-sized student (11.19M spiking
ResNet-18) was distilled for only 12k iterations (~92 min) and is
UNDERTRAINED (L_act plateau ~1.0; 19 % step-L3, 0 % elsewhere) — the
pipeline works, the training time was insufficient.

Decisions: (1) the year-two simulator is this repo's MuJoCo env — the
simulator and policy source are coupled, and the policy source is here
(supersedes the PyBullet/spot_mini_mini candidate). (2) The robot-era
network geometry follows the framework as built: event frames 2x64x64,
T=4 direct coding, encoder output = latent 32 + heading 2 (corrects the
older 48x64/latent-128 table). (3) P1 = distill the FPGA-SIZED encoder
inside this framework: c1 2->16 s2, c2 16->32 s2, c3 32->64 s2, 2x2 sum
pool, FC 1024->34 — 58,178 parameters, ~200x smaller than the paper's,
with the HARDWARE's neuron semantics in float (beta 0.875, delayed
reset-by-subtraction, strict >, D0002) and no batch norm, so M1
quantisation and the golden-model contract carry over unchanged.
(4) Launched overnight: scripts/distill_fpga.py (additive, nothing in
their package modified), warm-up 6k + DAgger 90k (~8x the undertrained
run), teacher ckpt_018000, checkpoints every 500. Either outcome is a
result: a working 58k student, or evidence on what this task needs.

Also: DVS-Gesture training DEFERRED — the shared GPU box is at 95 % disk
(9.9 GB free); the dataset+extraction would risk filling a machine other
people use. Revisit when disk is cleared or with a streamed pipeline.

### D0024 addendum (2026-08-20 01:40) — engines verified at robot geometry; C1 budget numbers

sim/export_robot_vectors.py: synthetic golden at the year-two shape
(2x64x64 -> 16x32x32, "r1"), seeded random int8 weights, Bernoulli inputs
at 8 %, LIF rule IMPORTED from golden/network.py so it cannot drift. Both
engines bit-identical: 1,048,576 comparisons each (dense and ED K=4).
Cycles/sample at 100 MHz: dense 1,378,872 (13.79 ms — 3.2x C1-N-MNIST,
matching the 2.65x pixels x deeper windows); ED K=4 321,104 (3.21 ms,
data-dependent). Against the perception budgets in the link-budget doc:
ED K=4 C1 alone fits 10 Hz easily and 25 Hz comfortably; 50 Hz needs
either the pipelined sweep or a K=8/16 build (both on the later list);
dense C1 alone misses even 20 ms. The engines are geometry-clean: no RTL
changes were needed, only parameters and vectors — the retarget risk for
P1 is retired on the conv side.

### S0 + S1 done (2026-08-20 02:00) — sim reproducibility proven; the stale-latent loop built and tested

S0: scripts/s0_repro_check.py (additive, on the GPU box): two rollouts at
seed 7 hash bit-identical over 300 steps incl. event frames; seed 8
diverges. PASS beside the running training job.

S1: robot/host/perception_loop.py — lockstep control loop with the
perception path's WALL-CLOCK time charged against an explicit budget;
misses deliver the stale latent (never wait, never crash — a first-tick
miss yields a zero latent), overruns logged in ms with the stage, and the
trial is flagged after N consecutive misses. Pluggable perceive/sim/policy
so it runs against the golden model, the FPGA link, or a test fake.
test_perception_loop.py drives it with a FAKE CLOCK and scripted delays:
exactly 5 predicted misses at the predicted ticks, stale-latent identity
verified through a 3-tick miss run, escalation at exactly cycle 25,
t_command_sent strictly increasing (no silent waits). The physical-robot
groundwork (cycle_log) carried over unchanged.

### P1 close-out pipeline PROVEN mid-training (2026-08-20 02:50)

The whole chain from a distillation checkpoint to verified RTL ran
end-to-end using the 2h-old MID-TRAINING checkpoint (proof of pipeline,
to be re-run on student_final):

  record_event_frames.py (box): 8 samples of REAL teacher-rollout event
  frames, T=4 windows, rate 6.2 % ->
  export_fpga_student_vectors.py (Mac): c1 weights quantised per D0008
  (k=4, threshold 2^4=16, rms rounding err 0.018), golden traces via the
  imported LIF rule, |V|max 568 (int16 fine) ->
  both engines at 2x64x64 with THRESH=16: 1,048,576 comparisons each,
  BIT-IDENTICAL. ED K=4: 306,480 cycles = 3.06 ms/sample at the real 6 %
  activity.

So: the year-two network's C1, quantised exactly as year one's, runs
bit-identical on both verified engines, on real simulated-camera data.
What remains for P1 proper: the final checkpoint (training ends ~noon),
its evaluation (scripts/evaluate_fpga.py, ready), the same export for
C2/C3/FC, and the accuracy-after-quantisation check inside the task.
Threshold plumbing (THRESH env) and a real-vs-synthetic switch (R1_REAL)
added to the runners.

### Board-retarget prep (2026-08-20 03:10) — r1 baked variants generated

gen_weight_vh.py now also emits conv_layer_r1.v / ed_scatter_r1.v with the
DISTILLED quantised c1 weights inlined (288 entries each), syntax-checked,
regenerated whenever the real-weight r1 vectors exist. NOT yet selectable
from ed_conv_layer/axis_conv (their baked branches name the c1 variants);
wiring that selection is a 3-line generate change deliberately left for
the actual board-retarget session, when the harness will be re-run around
it — no churn of verified RTL for a build that is not imminent. Vivado
customization for the 64x64 build, when it comes: C_IN=2 H_IN=64 W_IN=64
C_OUT=16 H_OUT=32 W_OUT=32 THRESHOLD=16(=2^k from the final checkpoint's
export), WORDS_IN 256/timestep, WORDS_OUT 512/timestep.

## P1 RESULT, hardware side (2026-08-20 09:45) — the year-two network runs bit-identical on both engines

Distillation finished: 96,000 iterations, 9.2 h, checkpoints kept. The
FINAL checkpoint's c1, quantised per D0008 (k=4, threshold 16, rms
rounding err 0.018), verified BIT-IDENTICAL on the dense and event-driven
engines at the robot geometry on real simulated event frames: 1,048,576
comparisons each. ED K=4: 306,480 cycles = 3.065 ms/sample at the real
6.2 % input activity. conv_layer_r1.v / ed_scatter_r1.v regenerated from
the final weights. Behavioural evaluation (L3/L6, 32 episodes) running;
mid-training signal (54 % trained): step 12 % / others 0 % with waypoint
fractions 0.29-0.39 — already at the 11.19M ResNet student's FINAL level
with 1/200th the parameters; theoretical encoder energy 0.0059 mJ vs the
ResNet's 0.184 mJ (31x). Success rates from the full run to follow.

## P1 RESULT, behavioural side (2026-08-20 10:10) — the 58k encoder matches/beats the 11.19M reference student

Full evaluation of the distilled FPGA-sized student (96k iterations), 32
episodes/terrain, against the same teacher:

| | teacher | 11.19M ResNet student (their run, 12k its) | 58k FPGA student (ours, 96k its) |
|---|---|---|---|
| L3 step | 88-100 % | 19 % | **25 %** |
| L3 others | 53-97 % | 0 % | 0 % |
| L6 step | 78 % | 0 % | **19 %** |
| L6 others | 0-94 % | 0 % | 0 % |
| theoretical encoder energy | 0.666 mJ (ANN) | 0.184 mJ | **0.0059 mJ** (31x below ResNet) |

Reading, stated carefully: absolute success is LOW for both students —
the distillation recipe/iteration budget is the limiter, and that is a
finding, not a failure to hide. Within that recipe, the FPGA-sized
encoder is NOT the bottleneck: at 1/200th the parameters it equals or
beats the paper-sized student everywhere, including a level the larger
one never passed. Combined with the hardware half (bit-identical on both
engines at 3.065 ms), P1's risk questions are answered: the year-two
network fits the engines, quantises cleanly, and loses nothing observable
to its size under this training. Lifting absolute success (longer
DAgger, recipe tuning) is year-two work, listed in the outline's future
work. Artifacts: experiments/p1_distill/ (L3, L6, mid-training tables);
checkpoints and logs on the GPU box under runs/fpga_student/.

## RETRACTION (C0028, 2026-08-20 15:35) — the M6 K=4 table's dense column was wrong for C2 and C3

The 2026-08-18 M6 K=4 entry applied "dense = 21 cycles/neuron" to all
three layers. 21 is C1-ONLY: cycles/neuron = taps + 3, and taps =
C_IN x 9, so C2 is 147 and C3 is 291. Verified independently today from
the MEASURED per-layer simulation (experiments/latency_sim raw counts):
97,499 / 381,434 / 465,865 cycles per timestep = 21.1 / 147.2 / 291.2 per
neuron — exactly taps + 3. The log briefly held two inconsistent dense
figures (the layers.md measurement was already correct); the wrong one
was attached to a highlighted finding.

**Retracted finding:** "at K=1 the event-driven engine LOSES to dense on
C2 and C3 — this is the crossover the thesis is about, visible in RTL
cycle counts." With the corrected dense column:

| per timestep | dense (measured) | ED K=1 | ED K=4 | dense/K1 | dense/K4 |
|---|---|---|---|---|---|
| C1 |  97,499 | 48,276 | 27,116 | 2.0x |  3.6x |
| C2 | 381,434 | 70,532 | 26,628 | 5.4x | 14.3x |
| C3 | 465,865 | 83,993 | 26,584 | 5.5x | 17.5x |

Event-driven wins every layer at every K; there is no cycle-level
crossover in the layer dimension. What DOES survive: the K-sweep
bit-identity results, the scatter cycles/spike measurements, and the C1
activity-sweep crossover for K=1 at ~45 % input rate (measured against
the real dense engine, not the model). Downstream check: the D0017 note's
"K=4 wins everywhere" framing was accidentally right for the wrong
reason; the day summaries citing "K=1 loses on C2/C3" are wrong and this
entry supersedes them. Cause: every later figure was checked against the
same hand model instead of an independent derivation — the fix (measured
per-layer counts) is now the source of record for dense costs.

### C0017 housekeeping (same pass)
- Index brought current to D0024 + retractions (below).
- D0021's divider caveat marked superseded in place.
- The 22:56 resource table's "DSP = 1 (ED)" note: use_dsp="no" landed
  after that build; the property is CONFIRMED MEASURED for dense (DSP 0,
  22:56 build) and remains expected-unconfirmed for ED until its next
  build — the table note now says exactly that.

## C0031 result + D0025 — the sweep-skip decision, made with data (resolves C0006)

**Date:** 2026-08-20 15:55 · full test split, 10,000 samples x T=4
(experiments/touched_fraction.md, run on the GPU box):

| layer | touched (I!=0) | alive (V!=0) | skippable ceiling |
|---|---|---|---|
| c1 | 31.3 % | 39.9 % | 60.1 % |
| c2 | 45.6 % | 49.1 % | 50.9 % |
| c3 | 66.1 % | 69.0 % | 31.0 % |
| fc | 99.8 % | 99.9 % | 0.1 % |

**Decision (D0025).** Two-part, both recorded now:
(1) For the CURRENT builds and any near-term measurement, take option (b):
state plainly that this architecture is event-driven SYNAPTIC processing
with a dense NEURON update — as most accelerators in this family are —
and report the sweep floor's share of engine time (68 % at K=4 on C1)
with the measured skippable ceilings above. The defence question is
pre-empted with numbers, not silence.
(2) The skip (option a) IS worth building for the conv layers — a 60 %
ceiling on C1 against a floor that is 68 % of engine time is too large to
leave — but it lands AFTER the pipelined sweep (C0030), which halves the
same floor for every layer including FC with far less bookkeeping, and
after the first meter session, so its benefit is measured against a
stable baseline. For FC the skip is provably worthless (99.8 % touched)
and will not be built.

## D0026 — The P-wide dense baseline (resolves C0029): the crossover is real, and it lives in fan-in

**Date:** 2026-08-20 16:00 · conv_layer_p.v + sim/run_conv_p_tb.sh

The dense engine now has the parallelism knob the comparison was missing:
P output channels advance together (one input-bit read + P banked weight
reads + P accumulators per cycle; weights and membranes banked oc mod P —
the same partition ed_scatter uses for K, so P == K is matched parallelism
by construction). Sign-off rules applied from the start; external ports
keep the 1-cycle read contract. Bit-identical at P = 1/2/4/8 on C1, P=4
on C2/C3, and P=4 at the ROBOT geometry with the real distilled weights
(1,048,576 comparisons). Scaling is exact: 406,908 / 203,452 / 101,724 /
50,860 cycles per sample.

**The matched-parallelism table (engine-only cycles/sample, trained
activity, P = K = 4):**

| layer | dense P=4 | ED K=4 | winner |
|---|---|---|---|
| C1 (N-MNIST, 18 taps/neuron) | 101,724 | 110,070 | **dense, by 8 %** |
| C2 (144 taps) | 383,612 | 108,191 | ED, 3.5x |
| C3 (288 taps) | 467,196 | 107,403 | ED, 4.3x |
| C1 robot geometry, real weights (6 % activity) | 360,444 | 306,480 | ED, 1.18x |

Stated plainly, replacing the retracted C0028-era finding with a measured
one: **against a fairly-parallelised dense baseline, the event-driven
design loses narrowly on the shallow layer and wins multiples on the deep
ones. The crossover the thesis is looking for exists, and its axis is
LAYER FAN-IN (taps per neuron), not just input activity.** Dense P=4
walks 21/4 ~= 5.25 effective cycles/neuron regardless of data; ED pays
scatter per spike x fan-out plus the sweep floor. Where fan-in is small
(C1: 18 taps), walking it all is cheap and dense edges ahead; where
fan-in is large (C2/C3: 144/288 taps), skipping zeros wins big. Both
engines behind the same wrapper still; the P=1 figures are hereby
relabelled the NAIVE baseline, and P = K is the primary comparison.
Caveats carried forward: the wrapper's fixed cost saturates both arms at
high P/K (C0035, next), and cycles are not energy — dense P=4 holds 4x
weight-bank BRAMs just as ED K=4 holds 4x accumulator banks; the meter
arbitrates, now with a genuinely fair pair at every K.
