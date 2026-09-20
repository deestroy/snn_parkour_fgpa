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
Sim-vs-board agreement 0.5-2.3 % (ED K=4 +1.6 %, K=8 +1.9 %, dense P=4 +0.8 %,
P=8 +1.6 %). It is better read as a constant per pass than as a percentage:
+10.9 us ED and +8.3 us dense on N-MNIST, +29.4 / +20.0 us on DVS-Gesture
against wrapper-inclusive totals.

## 2. Simulation: parallelism and activity, N-MNIST C1 (sim, `experiments/latency_sim/ksweep_c0035/`)

| K = P | ED cycles | dense cycles | dense / ED |
|---|---|---|---|
| 1 | 135,520 | 407k | 3.0x |
| 4 | 67,756 | 104,059 | 1.54x (board 1.52x) |
| 8 | 56,464 | 53,195 | 0.94x (board 0.939x) |
| 16 | 50,822 | ~27k | 0.53x |

ED = 45.2k + 90.3k/K, dense 406.9k/P + 2.3k, both on the WRAPPER-INCLUSIVE
basis; engine-only they are 43.3k + 90.4k/K and 406.9k/P + 4. Crossover
K = P = 7.4 (7.3 engine-only); mixing the two bases gives 7.0 or 7.7, so
always state which. The dense engine has essentially no fixed cost of its
own -- its +2.3k is the wrapper -- which is the real asymmetry: ED carries a
43.3k floor it cannot divide. Crossover K = P = 7.4
(C0049: quoted as ~6.6 until 2026-09-20; arithmetic, not data). Refined model (2026-09-18):
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
- Parallelism crossover K = P = 5.8 on this dataset (N-MNIST 7.4).
- T sweep (3 seeds at every T): 65.0 / 65.7 / 69.3 % mean at T = 4 / 8 / 16;
  the fc membrane sits at 98-121 % of int16 at T = 16 (2 of 3 overflow), at
  88-101 % at T = 8 (1 of 3), and at T = 8 the ceiling also moves down to
  ~15 % activity (T x activity compound, C0046). N-MNIST does not bind: 9-25 %
  of int16 up to T = 16 while gaining +0.7 pp per doubling (98.0 % at T=16,
  3 seeds; `experiments/tsweep_nmnist/`).
- **C0046 option costing (gpu, 2026-09-20):** fc at k = 7 instead of the
  chosen k = 8 on the seven overflowing / near-ceiling DVS-Gesture networks
  (T = 16 and T = 8 seeds 1-2, T = 4 at 34 % activity seeds 0-2): accuracy
  -1.5 to +1.9 pp (mean +0.1), 0.000 % weight clipping, fc range 95-186 %
  -> 47-93 % of int16 (k = 6: 23-47 %). The chosen-k golden accuracy is
  option (a)'s (18-bit) accuracy, so a wider membrane buys no accuracy
  here. `experiments/dvsgesture/c0046/README.md`.
- **Reproducibility (gpu, 2026-09-20, C0050):** training is NOT deterministic
  at a fixed seed on the MI210. Same code, same seed, same pack, two runs:
  fc membrane 98 % vs 102 % of int16 (fits vs overflows), float accuracy
  69.32 vs 68.18 %, quantised weights differing by up to 38 counts in fc.
  Every DVS-Gesture accuracy number in this ledger is therefore a single-run
  number with ~1 pp of run-to-run noise; the cycle counts are unaffected
  (simulation is exactly reproducible and every bench is bit-identical).
- **On silicon (board, 2026-09-19 13:27 build, parallel session):** ED K=4
  DATASET=1, 8/8 clips bit-identical, mean 2,970.8 us, spread 2.24x
  (2,084.6-4,663.9), board = sim + 92.9 us constant on every clip against
  the engine-only sim column -- later decomposed (b85ec60): against the
  wrapper-inclusive total the board is +29.4 us; clips 1 and 5 above the
  dense P=4 prediction, so the per-clip crossover is visible on hardware
  pending the dense P=4 build. WNS +0.190, server build 5. The PING
  DATASET check rejected a mis-built image first.
  `experiments/dvsgesture/board_ed_k4_20260919.md`.
- **Dense P=4 DATASET=1 on silicon (board, 2026-09-19, parallel session):**
  8/8 bit-identical, **3,706.5 us on every clip** (rev 3 engine, WNS
  +1.091). Against ED K=4's 2,970.8 us mean: **ED 1.248x at the mean,
  wins 6 of 8 clips, loses clips 1 and 5** -- the pre-registered per-clip
  activity crossover, on hardware. Board-minus-sim offsets against the
  engine-only column were dense 8.3 / 102.0 us, ED 10.7 / 92.9 us (N-MNIST /
  DVS-Gesture); against wrapper-inclusive totals the DVS-Gesture ones are
  dense +20.0 us, ED +29.4 us (b85ec60) -- compare board to wrapper-inclusive
  totals from now on.
  `experiments/dvsgesture/board_dense_p4_20260919.md`.

## 4. Activity axis by training (gpu + sim), K = P = 4

N-MNIST (`experiments/rate_sweep/`): five networks at 2-30 % conv rates,
accuracy flat 96.8-97.2 % to 16 %, 95.6 % at 30 %; all golden-clean.

| layer | 2 % | 30 % | extrapolated crossover |
|---|---|---|---|
| C1 (input = data, unchanged) | 1.54x | 1.54x | ~31 % (model) |
| C2 | 10.0x | 1.60x | ~48 % |
| C3 | 14.1x | 1.92x | ~57 % |

DVS-Gesture (`experiments/rate_sweep_dvsg/`, 3 seeds): a 3 pp accuracy
step between the 2-5 % and 10-35 % regimes; the 34 % network overflows
int16 in fc at T = 4 on every seed. C2 / C3 benches (12/12 bit-identical):
ED over dense 8.4x / 11.0x at 3 % activity, 1.33x / 1.36x at 32-35 %,
fitted crossovers ~43 % / ~48 % at K=P=4; per-spike constants match
N-MNIST's (40.4 vs 41.0, 74.0 vs 76.4 cycles). At K=P=8 / 16 (24 more
bit-identical runs) the crossover activity falls to ~36 / ~26 % (C2) and
~44 / ~37 % (C3), and at K=P=16 the 32 %-activity network is past it on
C2 (0.85x) -- the first real-data point where dense wins a conv layer. N-MNIST seeds: accuracy flat 2-8 %,
-0.5 / -1.9 pp at 16 / 30 % (sd 0.2-0.6). N-MNIST at K=P=8 / 16 (24/24 bit-identical, 2026-09-20): crossover
C2 48 / 40 / 29 %, C3 57 / 52 / 44 % at K=P=4 / 8 / 16; the 29 %-activity
C2 network is exactly at the crossover at K=P=16 (1.00x); per-spike constants
equal DVS-Gesture's at every K (`experiments/rate_sweep/README.md`).

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
  engines bit-identical; ED K=4 1.73 ms mean, 2.75 ms worst (spread 2.01x),
  dense 3.60 ms: **2.09x mean, 1.31x worst frame** over all 64 frames
  (C0048: the earlier 1.86 / 2.52 ms were the first 8 frames only;
  `experiments/p1_distill/isaac_i1_ed_k4_cycles_64.txt`) (placeholder weights; cycles
  are weight-independent).

## 6. What is NOT here, and why

- **Energy.** Nothing above is a joule. Tool estimates now exist for fourteen
  builds (ten board builds plus four C0019 strategy variants) (experiments/power_estimates/: fabric 48 mW ED K=4, 62.6 mW per
  dense P=4 engine from the x8 build, 135 mW dense DVS-Gesture ...) and
  predict ED 3.2x in energy at K=P=4; the meter does not yet exist;
  C0001-C0003 hold. Pre-registered: measure/metering_prereg_2026-09-19.md.
- **Energy against K** (C0025): pre-registered 2026-09-20
  (`measure/k_energy_prereg_2026-09-20.md`), needs three to five new
  bitstreams and the meter. Predicts the fabric-energy optimum at K = 8
  against a latency optimum at K = 16, and a board-level optimum at K = 16
  either way -- so the "most efficient K" depends on where the probe goes.
- **Seeds** on the sweeps and on DVS-Gesture's T points (running / one seed).
- **A student on the real stack** (training); the MuJoCo recreation's
  58k student is the placeholder for weights.
- **Board runs beyond C1** on either dataset (both DVS-Gesture builds are now on silicon).

## Verification state

Ladder 33 checks (`check_all.sh`), all bit-identity or self-test; every
board build's exact configuration was through the baked AXIS harness
with the hostile handshake before synthesis; the C0044 sweep bug found
by the second benchmark is fixed, guarded (synthetic corner set in the
ladder), and every number above post-dates the fix or is provably
unaffected by it (N-MNIST check set has zero corner exposure).
