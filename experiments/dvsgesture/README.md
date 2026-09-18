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

Input density is ~4x N-MNIST's (~5-6 %): DVS-Gesture sits near the C1
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

## Not yet done

- T sweep on DVS-Gesture (C0023): T = 8/16 should lift accuracy at a
  known cycle cost; membranes and the fc range must be re-checked.
- Seeds: one seed only. The N-MNIST 3-seed spread was ~0.4 pp; on 264
  test samples one sample is 0.38 pp, so expect a wider spread here.
- Board run: needs a bitstream with C0044 (Build 3 onward) and the
  DVS-Gesture weights baked (`sim/gen_weight_vh.py` for g1).
