# Notation: what every symbol in this project means

Written for the thesis's "List of Symbols" front matter, and for reading the
READMEs and tables without having to reverse-engineer a letter. Each entry
says what the symbol is, where it is set, and what it changes.

---

## 1. The network

The same small convolutional spiking network is used throughout, in two
sizes ("geometries"). A **layer** takes a stack of images in and produces a
smaller stack out.

| symbol | meaning |
|---|---|
| **C1, C2, C3** | The three **conv**olutional layers, in order. C1 is the first: it sees the raw input. C2 sees C1's output, C3 sees C2's. Each uses a 3x3 kernel with stride 2, so each halves the image size and doubles the channel count. |
| **FC** | The **f**ully **c**onnected layer at the end: every input connects to every output (768 -> 128). It has by far the most weights, which is why its membrane is the one that overflows. |
| **C_IN, C_OUT** | Channels in and out of a layer. "Channel" = one feature map, one image in the stack. C1 is 2 -> 16, C2 is 16 -> 32, C3 is 32 -> 64. |
| **H, W** | Height and width of a layer's feature maps. N-MNIST input is 34x34, DVS-Gesture and the robot 64x64. |
| **N** | The number of **output neurons** in a layer, `C_OUT x H_out x W_out`. For N-MNIST C1 that is 16 x 17 x 17 = 4,624. In the thesis `N` means only this: the engine replication count is written **R** and the BURST repeat count **B**, both below. (The repository and the board records predate that choice and use `N_ENGINES` and `N` respectively.) |
| **geometry** | Shorthand for the input size: the "34-geometry" (N-MNIST, 2x34x34) and the "64-geometry" (DVS-Gesture and the robot, 2x64x64). Same layer structure, different image sizes. |

**Layer names in the repository.** Vector sets and bench files use a letter
per dataset and a number per layer, so a file name says which network and
which layer it belongs to:

| prefix | dataset | example |
|---|---|---|
| `c1, c2, c3` | N-MNIST | `ed_c2_spk.txt` = event-driven vectors for N-MNIST's C2 |
| `g1, g2, g3` | DVS-Gesture | `ed_k8_0.30_g2.txt` = ED bench, K=8, the 30 %-activity network, DVS-Gesture C2 |
| `r1` | robot, weights from the MuJoCo recreation | `r1_thresh.txt` |
| `i1` | robot, frames from the IsaacGym port | `isaac_i1_ed_k4_cycles_64.txt` |

---

## 2. The neuron

Each neuron holds a running total called the **membrane potential** and fires
when it gets large enough.

| symbol | meaning |
|---|---|
| **V** | Membrane potential: the neuron's accumulated charge. Stored as a 16-bit signed integer in hardware (range -32,768 to 32,767). `V[n]` is its value at timestep n. |
| **I** | Input current at this timestep: the sum of the weights of every spike arriving at this neuron. Added to V each timestep. |
| **s** (per neuron) | The spike output, 0 or 1. A neuron fires when `V > theta`, strictly greater. |
| **theta**, V_threshold | The firing threshold. Always an integer power of two, `2^k`, so that comparisons and the reset are shifts rather than multiplies. |
| **beta** | The leak: each timestep V decays to `beta x V`. Fixed at 0.875, implemented as `V - (V >> 3)` so no multiplier is needed. |
| **pending** | The delayed-reset flag. When a neuron fires, the threshold is subtracted on the **next** timestep, not the same one. This matches snnTorch's default and is load-bearing for bit-exactness. |
| **T** | **Timesteps per inference.** Each input sample is split into T time bins and the network is run T times, accumulating spikes. Default 4. Raising T raises accuracy and also raises how large V grows, which is what eventually overflows the 16-bit membrane. |
| **k** | The quantisation shift for a layer: weights are stored as 8-bit integers at scale `2^-k`, and the layer's threshold is `2^k`. Larger k = finer weight steps but a larger membrane range. This is the knob in the C0046 decision. |

The full update, which the hardware implements exactly:

```
pending[n] = 1 if V[n-1] > theta else 0      # from the STORED membrane
V[n]       = beta*V[n-1] + sum(w*s[n]) - pending[n]*theta
s[n]       = 1 if V[n] > theta else 0        # strict >, not >=
```

---

## 3. The two engines and their parallelism

Two hardware designs compute the same layer. They differ only in the order
they do the work, which is the whole point of the thesis.

| symbol | meaning |
|---|---|
| **dense** (clock-driven) | Walks every output neuron every timestep, whether or not anything arrived. Predictable, wasteful. |
| **ED** (event-driven) | Keeps a list of the input spikes and processes only those, then makes one pass over the neurons to apply leak and threshold. Work scales with activity, but the machinery costs something. |
| **P** | **Dense lane count**: how many output neurons the dense engine updates in parallel. Its cost is exactly `1/P` — double P, halve the time. |
| **K** | **Event-driven bank count**: how many membrane memory banks the engine has, and so how many neuron updates its scatter stage can apply per cycle. Only *part* of the ED cost divides by K. |
| **K = P** ("matched parallelism") | The fair comparison. Both engines split the layer's output channels the same way (channel mod K, channel mod P), so the two knobs count the same unit of work; what that unit costs in hardware differs (bank ports and adders vs lanes and accumulators), which is why LUT and BRAM counts are always reported beside the latency. See the note below the table. |
| **B** (the BURST repeat count) | How many times one sample is replayed back to back during a measurement, so that the meter has a long steady window and latency averages over many runs. Sized for 15-30 s per window (for example B = 24,000 for the event-driven N-MNIST build). The metering pre-registration calls this N; it is written B in the thesis. |
| **s** (in the cycle model) | The number of input spikes in one sample, summed over all T timesteps. This is the activity variable: ED cost rises with it, dense cost does not. |
| **R** (the RTL parameter is `N_ENGINES`; builds are written x8, x4, x2) | How many **copies of the whole engine** are built into one bitstream. Used only for power measurement: one engine's power is too small to resolve on the meter, so R of them run at once and the measured difference is divided by R. **Written R in the thesis** to keep it apart from the `N` of the cycle model; the Verilog parameter, the build tags and the board records keep the name `N_ENGINES`, so a reader moving between thesis and repository should read `N_ENGINES = 4` as R = 4. |
| **activity** / firing rate | The fraction of neurons that fire per timestep, or for an input, the fraction of input bits set. The independent variable of the whole thesis. |
| **crossover** | The activity (or the parallelism) at which the two engines cost exactly the same. Below it ED wins, above it dense wins. |

**Why K = P is the fair comparison** (C0029, resolved by D0026). The
event-driven engine always had a parallelism knob: K banks, so K neuron
updates land per cycle. The first dense engine had none -- it processed one
tap per cycle, single-issue -- so the original headline compared a 4-wide
event-driven engine against a 1-wide dense one. The fix was to give the dense
engine the *same* partition the event-driven one already used: output channels
split by `channel mod P`, with P banked weight reads and P accumulators
advancing together. Because both engines then split the same thing the same
way, **K and P count the same unit of hardware, and K = P is matched
parallelism by construction** rather than by assertion. When the dense engine got its knob the C1 verdict flipped to dense by 8 %
(D0026, 2026-08-20) -- and then flipped back when the wrapper was
re-baselined (C0037): at K = P = 4 on C1 the event-driven engine now wins
1.54x in simulation and 1.52x on silicon. What survives from that episode is
not the verdict but the axis: giving the dense engine its knob is what moved
the crossover onto parallelism, where it has stayed.

**The cost models** (cycles per inference, validated against simulation and
silicon):

```
These are the C1 constants. The general forms, verified on all six
layer-dataset pairs, are below them.

dense:  88.0 x N / P            per T = 4 inference   (data-independent)
ED:     2 N T  +  5.0 s  +  71.7 s / K                (data-dependent)
        ^sweep    ^queue   ^scatter

general dense:  (N / P) x T x (9 C_IN + 4) + 4    exact to the cycle; the +4
                per neuron is the engine's serial tail (S_TAIL, S_VRD,
                S_VREG, S_UPDATE), 18.2 % of C1 and 1.4 % of C3
general ED:     2 N T + 5.0 s + (~1.12 x 4 C_OUT) s / K   empirical, ~4 %
                spread; the 4 is the stride-2 3x3 fan-out (a 2x2 block of
                output positions), NOT the T = 4 of the dense law
```

The crossover exists because the ED **sweep** term `2NT` does not shrink when
K grows, while the whole dense cost shrinks with P. More parallelism therefore
favours the dense engine.

---

## 4. The board and the tools

| symbol | meaning |
|---|---|
| **PS / PL** | The Zynq chip's two halves: the **P**rocessing **S**ystem (two ARM CPUs, DDR memory) and the **P**rogrammable **L**ogic (the FPGA fabric, where the engines live). |
| **LUT / FF / BRAM / DSP** | The fabric's building blocks: **l**ook-**u**p **t**ables (logic), **f**lip-**f**lops (1-bit registers), **b**lock **RAM** (on-chip memory, counted in 36-kilobit "tiles"), and **DSP** blocks (hardware multipliers). This design uses zero DSPs by construction, because every operation is a shift or an add. |
| **WNS / WHS** | **W**orst **n**egative (and **h**old) **s**lack, in nanoseconds: the timing margin of the slowest path after place-and-route. Positive means the design meets its clock; negative means it does not and the bitstream must not be used. |
| **AXI / AXI-Stream / DMA** | The bus standard connecting PS and PL (AXI), its streaming flavour used to feed the engine (AXI-Stream), and **d**irect **m**emory **a**ccess, the block that moves data between DDR and the fabric without the CPU copying it. |
| **BURST** | The board command that replays one sample many times back to back, so that a power measurement has a long steady window and a latency measurement averages over many runs. |
| **bitstream** | The file that configures the FPGA: one build of one engine at one K or P. Every result names the bitstream that produced it. |

---

## 5. Energy, and the three quantities that must not be merged

| symbol | meaning |
|---|---|
| **energy per inference** | The figure of merit: joules (microjoules) to process one sample. Power alone is misleading, because a slower design can draw less power and still use more energy. |
| **fabric delta** | The extra power drawn by the PL when the engine runs, compared with idle. This is what a Vivado estimate reports. |
| **board-input delta** | The extra power drawn at the board's 12 V input when the engine runs. This is what the meter measures, and it includes losses the estimate omits. |
| **energy per control period** | Board power multiplied by the robot's 100 ms control period: what a deployment actually pays per decision, dominated by the always-on ARM subsystem. |
| **tool estimate vs measured** | The gap between the first and second rows above is a result of this thesis in its own right, not a diagnostic. |

---

## 6. Housekeeping identifiers

| symbol | meaning |
|---|---|
| **M0 - M8** | Project milestones, from "simulation only" (M0) through "power measurement rig" (M5) and "the crossover experiment" (M7) to the robot workload (M8). |
| **D0001, D0002, ...** | Numbered design decisions in `docs/decisions.md`: a judgement call, the options, and why one was chosen. |
| **C0001, C0002, ...** | Numbered items in `docs/corrections.md`: a flaw found in the plan or the work, and what was done about it. C0044 was an RTL bug, C0049 an arithmetic slip, C0050 the reproducibility finding. |
| **golden model** | The Python integer reference implementation. Hardware is correct only if it matches it **bit for bit** on the same input. Not "close" — identical. |
| **pre-registration** | A file written *before* a board run, stating what is predicted and what would count as a failure. Kept unchanged afterwards, so a wrong prediction stays on the record. |
