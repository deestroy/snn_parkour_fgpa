# Results ledger — every measured and simulated number, with provenance (kept current; last revised 2026-09-19)

Every number here is either **measured on silicon** (board), **simulated
bit-identically against the golden model** (sim), or **trained/evaluated
on a GPU** (gpu). Nothing here is an energy number: the meter (M5) has
not been delivered. Each row names its file.

## 1. Silicon: C1 of the N-MNIST network on the ZedBoard (100 MHz, engine-only latency, 16 check samples)

| build | config | latency mean | min-max | vs dense P=4 | WNS | LUT / BRAM tiles | record |
|---|---|---|---|---|---|---|---|
| 1 | ED K=4 | 688.5 us | 554.8-815.8 | 1.52x | +0.508 | ~3.4k / 12.5 | board_ed_k4_20260905.md |
| 2 | dense P=4 | 1048.9 us flat | -- | 1.00x | +0.299 | 5,760 / 6.5 | board_dense_p4_20260906.md |
| 3 | ED K=8 (pre-C0044 RTL; N-MNIST unaffected) | 575.5 us | 494.1-653.1 | 1.82x | +0.332 | -- / 13.5 | board_ed_k8_20260917.md |
| 4 | dense P=8 | 540.3 us flat | -- | 1.94x | +0.101 | -- / 8.5 | board_dense_p8_20260917.md |
| x8 | ED K=4, N_ENGINES=8 (C0003) | 688.5 us (unchanged) | 554.8-815.8 | -- | +0.430 | 11,733 / 86 | board_ed_k4_x8_20260917.md |
| x8 | dense P=4, N_ENGINES=8 | 1048.9 us (unchanged) | -- | -- | +0.041 | 27,829 / 46 | board_dense_p4_x8_20260917.md |

All bit-identical to the golden model (16/16, plus thousands of burst
inferences at zero CRC mismatches). Matched-parallelism verdicts on
silicon: **ED wins 1.52x at K = P = 4, dense wins 1.065x (0.939x) at
K = P = 8** — the parallelism crossover between 4 and 8 is on hardware.
Sim-vs-board agreement 0.4-1.5 % throughout (cycle model, C0028/C0035).

## 2. Simulation: parallelism and activity, N-MNIST C1 (sim, `experiments/latency_sim/ksweep_c0035/`)

| K = P | ED cycles | dense cycles | dense / ED |
|---|---|---|---|
| 1 | 135,520 | 407k | 3.0x |
| 4 | 67,756 | 104,059 | 1.54x (board 1.52x) |
| 8 | 56,464 | 53,195 | 0.94x (board 0.939x) |
| 16 | 50,822 | ~27k | 0.53x |

ED = 45.2k + 90.3k/K; crossover K = P ~ 6.6. Refined model (2026-09-18):
`cycles = 2NT + 5.0 s + 71.7 s/K`, dense `88.0 N/P` per T = 4 inference,
validated to 0.3 % per sample on a second dataset.

## 3. Second benchmark: DVS-Gesture (C0012), 2x64x64, T = 4 (gpu + sim)

- Accuracy: 3 seeds float 63.3 / 68.6 / 63.3 % (spread 5.3 pp on 264
  samples); golden integer 63.3 / 66.7 / 65.9 %. `experiments/dvsgesture/`.
- **C1 activity crossover on real data (sim):** at K = P = 4 the ED
  engine wins on 6 of 8 test clips and loses on the two densest (36 % and
  44 % input density); the rule is exact: ED wins below ~10,000 input
  spikes per clip = ~30.5 % density. Mean 2.88 ms vs dense 3.60 ms
  (1.25x); worst clip 4.57 ms (deadline reading: dense wins).
  `experiments/dvsgesture/latency_sim/`, pre-registered.
- Parallelism crossover K = P = 5.8 on this dataset (N-MNIST 6.6).
- T sweep (one seed): 63.3 / 65.2 / 68.9 % at T = 4 / 8 / 16 — but the fc
  membrane overflows int16 at T = 16, and at T = 8 for 1 of 3 seeds
  (C0046). T = 4 is the only setting with margin on every seed.
- Board-ready: DATASET=1 builds (g1 tables baked, both engines through
  the baked wrapper, hostile handshake) — `docs/vivado_session_next.md`.

## 4. Activity axis by training (gpu + sim), K = P = 4

N-MNIST (`experiments/rate_sweep/`): five networks at 2-30 % conv rates,
accuracy flat 96.8-97.2 % to 16 %, 95.6 % at 30 %; all golden-clean.

| layer | 2 % | 30 % | extrapolated crossover |
|---|---|---|---|
| C1 (input = data, unchanged) | 1.54x | 1.54x | ~31 % (model) |
| C2 | 10.0x | 1.60x | ~48 % |
| C3 | 14.1x | 1.92x | ~57 % |

DVS-Gesture (`experiments/rate_sweep_dvsg/`): accuracy RISES with
activity (63.3 -> 66.3 % float, one seed, inside the seed spread); the
34 % network overflows int16 in fc at T = 4. C2/C3 benches at this
geometry: in progress (2026-09-19). Seeds 1-2 for both sweeps: running.

## 5. Year two on the paper's own stack (gpu; `robot/isaac/`, `experiments/p1_distill/`)

- Teacher (extreme-parkour, IsaacGym, 1080 Ti): 15,000 iterations, 23.3 h.
  Success under their protocol: gap 95.3 %, hurdle 96.1 %, parkour
  97.2 %, step 99.2 %.
- The 58k FPGA-sized spiking encoder now trains inside their vision
  distillation loop (event simulator bit-identical to the recreation's;
  encoder verbatim). Distillation 200-00-fpga running: 10k iterations,
  ~13.6 s each, ETA 2026-09-21 ~03:00. Queued after it: GIFs per terrain,
  student evaluation, student-driven frames.
- Real robot event frames (64, teacher-driven, direct coding): both
  engines bit-identical; ED K=4 1.86 ms mean, 2.52 ms worst, dense 3.60
  ms: **1.94x mean, 1.43x worst frame** (placeholder weights; cycles
  are weight-independent).

## 6. What is NOT here, and why

- **Energy.** Nothing above is a joule. The tool estimate exists (ED K=4
  fabric ~49 mW), the meter does not yet; C0001-C0003 hold.
- **Seeds** on the sweeps and on DVS-Gesture's T points (running / one seed).
- **A student on the real stack** (training); the MuJoCo recreation's
  58k student is the placeholder for weights.
- **Board runs of anything but N-MNIST C1** (DVS-Gesture pair is ready).

## Verification state

Ladder 30 checks (`check_all.sh`), all bit-identity or self-test; every
board build's exact configuration was through the baked AXIS harness
with the hostile handshake before synthesis; the C0044 sweep bug found
by the second benchmark is fixed, guarded (synthetic corner set in the
ladder), and every number above post-dates the fix or is provably
unaffected by it (N-MNIST check set has zero corner exposure).
