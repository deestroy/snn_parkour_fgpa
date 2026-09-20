# DVS-Gesture through the whole chain (C0012) — 2026-09-17

Second benchmark, chosen because N-MNIST is the weakest evidence in this
field (C0012). Everything below ran on the NVIDIA box (GTX 1080 Ti) via
the unchanged pipeline: `train/04b_pack_dvsgesture.py` -> `03_train.py
--dataset dvsgesture` -> `05_quantise.py --out` -> `06_golden_check.py`
-> `sim/export_dvsgesture_vectors.py` -> both engine testbenches.

## Data

tonic `DVSGesture` (IBM, 128x128 DVS, 11 classes), packed at the
robot-era geometry the engines are already verified on (D0024):
Denoise (10 ms), spatial downsample x0.5 -> **2 x 64 x 64**, `ToFrame`
with **T = 4** time bins over the whole ~6 s clip, then binarised (D0003:
any event in a pixel-bin -> 1). Train 1,077 samples, test 264.

| split | samples | input density | uint8-clipped pixel-bins |
|---|---|---|---|
| train | 1,077 | 22.3 % | 0.133 % |
| test | 264 | 27.2 % | 0.135 % |

Input density is ~2x N-MNIST's (13.6 % on the check set, 27.2 % on the test set here; corrected 2026-09-20, the '~4x N-MNIST's ~5-6 %' that stood here was wrong on both figures): DVS-Gesture sits near the C1
activity crossover (~31 % from the cycle model), which is the point —
an event-driven advantage here is not a foregone conclusion.

## Training (seed 0, beta 0.875, 30 epochs, batch 128, lr default)

`train_seed0.log`, `m0_firing_rates_binarised.csv`. Final epoch:

| | accuracy | c1 | c2 | c3 | fc |
|---|---|---|---|---|---|
| train | 100.00 % | 0.060 | 0.116 | 0.158 | 0.352 |
| test | **63.26 %** | 0.073 | 0.143 | 0.186 | 0.359 |

Honest reading: the network memorises 1,077 clips (train 100 %) and
generalises to 63 %. Published DVS-Gesture results (90-97 %) use
~100-frame temporal resolution, much larger nets, and augmentation;
at T = 4 over the whole clip most of the gesture's motion is averaged
away. This is an accuracy CEILING of the encoding, not a bug — it is
what the same 121k-parameter network the hardware runs can do on this
data, and it is the number the energy figures must be reported next to.
Firing rates are 1.4-2x N-MNIST's per layer; the fc layer at 36 % is
the densest layer the engines have seen.

## Quantisation (`quantise_seed0.log`)

int8 power-of-two scales: conv1 2^-7 (threshold 128), conv2 2^-7 (128),
conv3 2^-8 (256), fc 2^-8 (effective shift 10 with the /4 pool fold).
float 63.26 % -> int8 weights 65.15 % (rounding acts as a regulariser
here; the +1.9 pp is one seed's noise, not a result). The re-quantised
file reproduces `golden/dvsgesture_weights_int8.npz` array-for-array.

## Golden integer model (`golden_check_seed0.log`)

264/264 test samples: **63.26 %, 0.00 pp drop** from float. Membrane
ranges: c1 13 bits, c2 12, c3 14, fc 16 (max |V| 19,777 of 32,767) —
fits the int16 budget, with the fc layer using 60 % of it. Traces for
the 16 C0039-seeded samples -> `golden/traces_dvsgesture.npz` (not
committed; regenerate with the command in the log header).

## Engines vs golden on the C1 vectors (`g1`, 8 test samples, THRESH=128)

Vectors: `sim/export_dvsgesture_vectors.py` (in rate 20.9 %, out rate
5.9 %, |V|max 2,454). 8 samples x 4 timesteps x 16 x 32 x 32 neurons;
the two benches count comparisons differently (the dense bench also
checks the packed output words).

| engine | config | comparisons | result |
|---|---|---|---|
| dense | P=4 | 1,572,864 | bit-identical (360,444 engine cycles/sample) |
| event-driven | K=1 | 1,048,576 | bit-identical (after C0044) |
| event-driven | K=4 | 1,048,576 | bit-identical (after C0044) |

Both runners default THRESH to 128 for `g1` (the value is the layer's
weight scale, not a knob); the ladder (`check_all.sh`) is 23/23 with
the fix.

**The event-driven engine FAILED on first contact** with this data, at
output neuron 0 only, with an error that grew by one input-current's
worth per timestep. Cause: the sweep's I-zero write was gated on the
update pipeline's valid flag, which is clear on the first read beat, so
I[0] was never cleared (C0044, `hdl/eventdriven/ed_conv_layer.v`). N-MNIST
never exercised it: in all 64 timesteps of the check set, no spike falls
in neuron 0's receptive field (input rows/cols 0-1). DVS-Gesture puts one
there in 3 of 32 timesteps. Every previously recorded N-MNIST result is
numerically unaffected; the board's ED K=4 bitstream predates the fix
and must not be reused for data with corner activity.

## Files

- `m0_firing_rates_binarised.csv` — per-epoch training record (committed)
- `train_seed0.log`, `quantise_seed0.log`, `golden_check_seed0.log` — local only
  (`*.log` is gitignored, as for the beta sweep); every number they hold is
  quoted above, and all three regenerate from the checkpoint on the box
  (M1 chain re-runs 2026-09-17 21:48 EDT)
- checkpoint `dvsgesture_beta0875_seed0.pt` and packed frames stay on the box (`~/snn_parkour_fpga/experiments/dvsgesture/`, `data/packed_dvsgesture/`)

## Three seeds at T = 4 (2026-09-18, CPU runs on the box, 30 epochs each)

| seed | float | int8 weights | golden integer | golden - float | fc |V|max | M1 gate |
|---|---|---|---|---|---|---|
| 0 | 63.26 % | 65.15 % | 63.26 % | 0.00 pp | 19,777 | pass |
| 1 | 68.56 % | 67.80 % | 66.67 % | -1.89 pp | 21,252 | FAIL (gate ~1 pp) |
| 2 | 63.26 % | 63.64 % | 65.91 % | +2.65 pp | 21,221 | pass |

Float accuracy 63.3 / 68.6 / 63.3 %: mean **65.0 %, spread 5.3 pp** on a
264-sample test set (one sample = 0.38 pp). The quantisation "drop" is
-1.9 to +2.7 pp across seeds, i.e. it is noise around zero, not a bias:
seed 1 loses 5 test samples to integer arithmetic, seed 2 gains 7. The
~1 pp M1 gate was calibrated on N-MNIST's 10,000-sample test set and is
too tight for 264 samples; seed 1's FAIL is recorded as such, not
tuned away, and the gate stays (it is the right gate for the datasets it
was set on; a per-dataset tolerance is a C-item, not a quiet edit).
Membranes fit int16 on every seed (fc uses 65 % of the budget at worst).
Seeds 1 and 2 are 68.56 % and 63.26 % test; the coincidence with seed 0's
63.26 % is 167/264 on both, different networks (their int8 and golden
numbers differ). Logs: `train_seed{1,2}.log`, `quantise_seed{1,2}.log`,
`golden_check_seed{1,2}.log`, `seed{1,2}_m0_firing_rates_binarised.csv`.

## T sweep (C0023), seed 0, 30 epochs each (2026-09-18)

Packed with `04b_pack_dvsgesture.py --T <T>` into `packed_dvsgesture_t<T>`,
trained with `03_train.py --T <T>`; each run through quantise and golden.
`t8/`, `t16/` hold the seed 1 and seed 2 logs and firing-rate CSVs. **Seed 0's
original T=8/T=16 golden logs were lost on 2026-09-20 (C0051)**; its numbers
below are the transcription made at the time, and a RETRAIN of seed 0 (a
different network -- training does not reproduce at a fixed seed, C0050) is in
`c0046/rerun_seed0/`.

| T | test input density | float | int8 | golden integer | golden - float | fc |V| range | fits int16? | rates c1 / c2 / c3 / fc |
|---|---|---|---|---|---|---|---|---|
| 4 | 27.2 % | 63.26 % | 65.15 % | 63.26 % | 0.00 pp | -19,777 .. 17,154 | yes (60 %) | .073 / .143 / .186 / .359 |
| 8 | 21.7 % | 65.15 % | 66.29 % | 65.53 % | +0.38 pp | -28,768 .. 22,533 | yes (88 %) | .063 / .122 / .150 / .288 |
| 16 | 15.1 % | 68.94 % | 71.59 % | 70.83 % | +1.89 pp | **-34,472 .. 28,983** | **NO (17 bits)** | .046 / .088 / .117 / .235 |

Reading:
- Accuracy rises with T (63 -> 65 -> 69 % float), as expected when the
  gesture's motion is split into more bins; the gain from 4 to 16 bins
  (+5.7 pp) is about the size of the seed spread at T = 4 (5.3 pp), so it
  is real but not large, and one seed per T.
- **At T = 16 the fc membrane overflows int16 on this run.** C0050 qualifies
  this: the same configuration and seed lands on either side of the ceiling
  depending on the training run (98 % and 102 % in two runs of identical code),
  so 'T = 16 overflows' is a statement about runs, not about a configuration.
  See `c0046/README.md`. Original reading follows:
- At T = 16 the fc membrane overflows int16 (-34,472 below the
  -32,768 floor). The golden model computes in unbounded integers, so its
  70.83 % is NOT what the hardware would produce; the RTL's 16-bit
  membrane would wrap. This is the hardware limit of the encoding as
  built: T = 8 fits with 12 % headroom, T = 16 does not. Options, none
  taken here (judgement call for the thesis): widen the membrane to 18
  bits (RTL change, +12 % membrane BRAM); drop the fc scale one bit
  (k = 7, halves the range at a rounding cost); or accept T <= 8. The
  golden check now has a concrete case where "fits int16" is the gate
  that bites.
- Per-neuron firing rates fall with T while accuracy rises: shorter bins
  carry fewer events each. Total spikes per clip still grow (see below).
- The "drop" column is again noise around zero (-0.4 to +1.9 pp on 264
  samples).

Cycle projection from the model validated at T = 4 (`latency_sim/`,
0.3 % per sample; `cycles = 2NT + 5.0 s + 71.7 s/K`, dense `22.0 N T / P`,
i.e. 88.0 cycles per neuron per T = 4 inference),
using the full test set's density for spikes per clip `s`:

| T | spikes / clip | ED K=4 | dense P=4 | dense / ED |
|---|---|---|---|---|
| 4 | 8,900 | 335k (3.35 ms) | 1,442k/4 = 360k (3.60 ms) | 1.08x |
| 8 | 14,200 | 587k (5.87 ms) | 721k (7.21 ms) | 1.23x |
| 16 | 19,800 | 979k (9.79 ms) | 1,442k (14.42 ms) | 1.47x |

(The T = 4 row uses the whole test set's 27.2 % density; the measured
8-sample subset was sparser, 20.9 %, hence its 1.25x.) Longer T favours
the event-driven engine slightly, because the input gets sparser per
bin while the dense engine's cost is exactly linear in T. These are
projections, not simulations; the T = 8 vectors can be exported and run
through both benches when a T = 8 build is on the table.

## T = 8, three seeds (2026-09-18, MI210 runs; `t8/`)

| seed | float | int8 | golden integer | golden - float | fc |V| range | fits int16? |
|---|---|---|---|---|---|---|
| 0 | 65.15 % | 66.29 % | 65.53 % | +0.38 pp | -28,768 .. 22,533 | yes (88 %) |
| 1 | 66.67 % | 65.53 % | 64.39 % | -2.27 pp | **-33,013 .. 21,573** | **NO** |
| 2 | 65.15 % | 65.53 % | 64.77 % | -0.38 pp | -31,200 .. 24,559 | yes (95 %) |

Float 65.2 / 66.7 / 65.2 % (mean 65.7 %, spread 1.5 pp, tighter than
T = 4's 5.3 pp). **The int16 verdict at T = 8 is seed-dependent:** seed
0 had 12 % headroom, seed 2 has 5 %, seed 1 overflows. So the earlier
"T = 8 fits" was one seed's luck. As built (int16 membranes, fc scale
k = 8), T = 4 is the only setting with margin on every seed; T = 8 needs
the membrane widened or the fc scale dropped a bit before it can be a
board configuration. Recorded as a hardware limit of the encoding, not
tuned away.

## T = 16, three seeds (2026-09-20, `t16/`)

| seed | float | golden integer | fc |V| range | share of int16 |
|---|---|---|---|---|
| 0 | 68.94 % | 70.83 % | -34,472 .. 28,983 | 105 % (overflow) |
| 1 | 70.08 % | 70.45 % | -32,210 .. 21,145 | 98 % (fits by 557 counts) |
| 2 | 68.94 % | 69.32 % | -39,677 .. 16,747 | 121 % (overflow) |

T = 16 is AT the int16 ceiling on every seed (98-121 %): two of three
overflow and the third clears it by 1.7 %. Accuracy 69.0 / 70.1 / 69.0 %
(mean 69.3, +4.3 pp over the T = 4 mean of 65.0) is real across seeds but
is not a hardware number as built. See the T = 8 x activity table in
`../rate_sweep_dvsg/README.md`: the ceiling is a T x activity product.

## Board readiness (2026-09-18)

Baked for silicon: `hdl/dense/conv_layer_p_g1.v` and
`hdl/eventdriven/ed_scatter_g1.v` (sim/gen_weight_vh.py), selected by
the new top-level parameter DATASET=1, which also sets the geometry and
the threshold. Both exact synthesis configurations pass the baked AXIS
harness with the hostile handshake (ED K=4 and dense P=4: 16,384 words
bit-identical each, 8 samples). Server build 5 takes -DDATASET=1 and
reports the dataset in PING. Session steps: docs/vivado_session_next.md,
"DVS-Gesture pair". Latency predictions for the card:
`latency_sim/README.md`.

## Not yet done

- T sweep on DVS-Gesture (C0023): T = 8/16 should lift accuracy at a
  known cycle cost; membranes and the fc range must be re-checked.
- Seeds: one seed only. The N-MNIST 3-seed spread was ~0.4 pp; on 264
  test samples one sample is 0.38 pp, so expect a wider spread here.
- Board run: the DATASET=1 pair (above) is ready to build; the K=P=8
  N-MNIST pair and the x8 builds took the Vivado time on 2026-09-17.
