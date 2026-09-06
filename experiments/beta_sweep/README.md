# Beta (membrane leak) sweep — N-MNIST, seed 0, 10 epochs (2026-09-06)

Why: D0007 fixed beta = 0.875 = 1 - 2^-3 so the leak is a shift
(`V - (V >> 3)`, no multiplier) and retrained at that value against the
beta = 0.9 float baseline (97.03 % vs 96.93 %, 3 vs 4 seeds). Only those
two betas had ever been trained. This sweep asks whether any OTHER
shift-friendly beta (1 - 2^-s) is better, and what beta does to the
firing rates — the thesis's independent variable.

Run on claude_svpn (MI210), `train/03_train.py --epochs 10 --seed 0
--beta <b> --save ...`, ~2 min 15 s per run. Files: per-epoch CSVs and
logs here (checkpoints stay on the box: `~/snn_parkour_fpga/experiments/
beta_sweep/beta<b>_seed0.pt`).

| beta | shift s | test acc (seed 0) | c1 rate | c2 | c3 | fc |
|---|---|---|---|---|---|---|
| 0.5 | 1 | 96.81 % | 0.0766 | 0.0892 | 0.1149 | 0.2675 |
| 0.75 | 2 | 96.85 % | 0.0712 | 0.0852 | 0.1134 | 0.2854 |
| **0.875** | **3** | **96.60 %** (D0007 seed 0; 3-seed mean 97.03 %) | 0.0679* | 0.0759* | 0.1050* | 0.3015* |
| 0.9375 | 4 | 96.98 % | 0.0658 | 0.0800 | 0.1019 | 0.2930 |
| 0.96875 | 5 | 96.85 % | 0.0694 | 0.0808 | 0.1030 | 0.2617 |

\* rates from the repo's last local `m0_firing_rates_binarised.csv`
(epoch-10 test row, 96.81 % in that file); accuracy quoted from D0007.

## Reading it

- **Accuracy is flat in beta**: 96.60-96.98 % across a 2^5 range of leak,
  inside the 3-seed spread already measured at 0.875 (96.60-97.27 %).
  There is no better beta to switch to, and no worse one to avoid — the
  network compensates for the leak during training. beta = 0.875 stands,
  chosen for hardware cost, at no accuracy cost.
- **Firing rates move a little, and in the expected direction**: a
  stronger leak (smaller beta) pushes the conv layers' rates UP (c1
  0.066 -> 0.077 from beta 0.9375 to 0.5) — neurons must be driven harder
  to cross threshold when the membrane forgets faster. The effect is
  ~15 % relative on c1, smaller elsewhere; fc is noisy. So beta is a weak
  knob on activity compared with the threshold (the M7 sweep variable).
- Single seed each; the differences between betas are at the seed-noise
  level, which is the finding. A 3-seed repeat would be ~30 GPU-minutes
  if a reviewer wants error bars.
- Hardware note: every beta here is a shift; the golden model and RTL
  carry LEAK_SHIFT as a constant (3), so any of these is a one-line
  change plus a retrain, quantise, and re-verify pass.
