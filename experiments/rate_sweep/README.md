# M7 activity axis on real data: N-MNIST networks trained to target firing rates (2026-09-18)

Why: every activity point so far came from a threshold knob or from
synthetic Bernoulli inputs (C0040: real activity is spatially clustered).
Here the ACTIVITY is trained in: `train/03_train.py --rate_target r
--rate_lambda 100` adds `100 * sum_{c1,c2,c3} (rate_l - r)^2` to the
training loss, so the conv layers' output rates -- the inputs of C2, C3
and FC -- land at r. C1's own input is the dataset's density (13.6 % on
the check set) and does not move; the sweep is the activity axis for C2
and C3, which have bit-identical dense and event-driven benches.

Lambda calibration (3 epochs, target 0.03): lambda 20 -> c2 0.039,
100 -> 0.033, 500 -> 0.031, accuracy unchanged (96.6 %); 100 chosen.
MI210: ~9-14 s per epoch. Seed 0, 10 epochs, one seed per point.

## Training, quantisation, golden (all on the 10,000-sample test set)

| target | achieved c1 / c2 / c3 / fc | float | int8 | golden integer | golden - float | shifts k (c1/c2/c3/fc) | max membrane bits |
|---|---|---|---|---|---|---|---|
| none (M1 baseline) | .069 / .081 / .103 / .262 | 96.60 % | 96.69 % | 96.60 % | 0.00 | 6/6/6/6 | -- |
| 0.02 | .024 / .026 / .022 / .222 | 96.91 % | 96.91 % | 96.90 % | -0.01 pp | 5/6/5/6 | 12 |
| 0.04 | .042 / .042 / .041 / .266 | 97.18 % | 97.30 % | 97.26 % | +0.08 pp | 5/6/6/6 | 12 |
| 0.08 | .081 / .079 / .080 / .275 | 96.92 % | 96.93 % | 96.96 % | +0.04 pp | 6/6/7/6 | 13 |
| 0.16 | .160 / .158 / .158 / .324 | 96.82 % | 96.80 % | 96.81 % | -0.01 pp | 6/7/6/6 | 13 |
| 0.30 | .297 / .297 / .298 / .305 | 95.62 % | 95.64 % | 95.49 % | -0.13 pp | 6/6/6/6 | 14 |

The penalty lands within 0.003 of the target at every point. Accuracy
is FLAT from 2 % to 16 % (96.8-97.2 %, within the 3-seed spread of the
baseline) and drops 1.2 pp at 30 %: on N-MNIST the network does not need
its activity, which is the strongest possible case for an event-driven
engine -- and also a warning that "activity" is a free parameter of the
training recipe, not a property of the task. Every point is golden-clean
and fits int16 with room. Note the shifts move with the rate: the
threshold each network runs at is 2^k for THAT network, so the bench
runners now read it from the exporter (`VEC_WEIGHTS` / `VEC_TRACES`).

Files: `train_rate<r>.log`, `quantise_rate<r>.log`, `golden_rate<r>.log`,
`rates_binarised_nmnist_target<r>_seed0_t4.csv`, `nmnist_rate<r>_int8.npz`
(committed, 60 KB each); `traces_rate<r>.npz` local + on the AMD box
(regenerable from the checkpoints there, `runs` under experiments/rate_sweep).

## Seeds (2026-09-19, seeds 1-2 added on the MI210; `*_seed1*`, `*_seed2*`)

| target | float test acc, seeds 0 / 1 / 2 | mean +- sd |
|---|---|---|
| 0.02 | 96.9 / 97.3 / 97.2 | **97.1** +- 0.2 |
| 0.04 | 97.2 / 97.5 / 97.2 | **97.3** +- 0.2 |
| 0.08 | 96.9 / 97.3 / 97.5 | **97.2** +- 0.3 |
| 0.16 | 96.8 / 96.5 / 96.9 | **96.7** +- 0.2 |
| 0.30 | 95.6 / 94.6 / 95.6 | **95.3** +- 0.6 |

With three seeds the shape is confirmed: **flat from 2 % to 8 % (97.1-97.3 %),
-0.5 pp at 16 %, -1.9 pp at 30 %**; the seed sd is 0.2-0.6 pp, so the 30 %
drop is real and the 16 % one is at the edge. All 15 runs quantise and
pass golden (seed-1/2 logs alongside seed 0's).

## Engine cycles vs activity (both engines, K = P = 4, 16 check samples)

All 18 runs bit-identical to the golden model (6 networks x 3 layers, ED
K=4 and dense P=4). Per-sample ED cycle files `bench/ed_k4_<net>_<layer>.txt`,
dense lines `bench/dense_p4_<net>_<layer>.txt`. "Input rate (bench)" is
the fraction of input bits set over the 16 check samples x 4 timesteps,
i.e. the previous layer's firing rate on the CHECK set (the training-log
rates are on the test set; they agree to ~0.01).

### C1 (dense P=4 constant: 101,724 cycles/sample)

| network | input rate (bench) | input spikes / sample | ED K=4 mean | min | max | dense / ED |
|---|---|---|---|---|---|---|
| M1 baseline | 0.136 | 1,256 | 65,876 | 52,544 | 78,589 | 1.54x |
| target 0.02 | 0.136 | 1,256 | 65,876 | 52,544 | 78,589 | 1.54x |
| target 0.04 | 0.136 | 1,256 | 65,876 | 52,544 | 78,589 | 1.54x |
| target 0.08 | 0.136 | 1,256 | 65,876 | 52,544 | 78,589 | 1.54x |
| target 0.16 | 0.136 | 1,256 | 65,876 | 52,544 | 78,589 | 1.54x |
| target 0.30 | 0.136 | 1,256 | 65,876 | 52,544 | 78,589 | 1.54x |

No fit here: all six networks share the input (1,256 spikes/sample on
the check set), so the sweep has one C1 point. C1's activity model is
the validated one (`2NT + 5.0 s + 71.7 s/K`, experiments/dvsgesture/
latency_sim): crossover at K = P = 4 near 31 % input density.

### C2 (dense P=4 constant: 383,612 cycles/sample)

| network | input rate (bench) | input spikes / sample | ED K=4 mean | min | max | dense / ED |
|---|---|---|---|---|---|---|
| M1 baseline | 0.069 | 1,270 | 72,885 | 52,407 | 90,877 | 5.26x |
| target 0.02 | 0.023 | 427 | 38,297 | 33,086 | 42,922 | 10.02x |
| target 0.04 | 0.041 | 751 | 51,550 | 39,438 | 61,397 | 7.44x |
| target 0.08 | 0.078 | 1,451 | 80,259 | 55,807 | 100,332 | 4.78x |
| target 0.16 | 0.156 | 2,886 | 139,222 | 86,277 | 185,850 | 2.76x |
| target 0.30 | 0.290 | 5,359 | 240,475 | 149,704 | 306,981 | 1.60x |

Fit `ED = 20,803 + 41.0 x spikes` (max residual 0.1 %; sweep floor 2 x 2,592 x 4 = 20,736); **crossover at 8,849 input spikes per sample = 48 % input rate** (beyond the swept range; extrapolated)

### C3 (dense P=4 constant: 467,196 cycles/sample)

| network | input rate (bench) | input spikes / sample | ED K=4 mean | min | max | dense / ED |
|---|---|---|---|---|---|---|
| M1 baseline | 0.082 | 851 | 78,214 | 58,695 | 96,727 | 5.97x |
| target 0.02 | 0.025 | 264 | 33,084 | 28,122 | 38,267 | 14.12x |
| target 0.04 | 0.042 | 430 | 45,978 | 35,307 | 55,089 | 10.16x |
| target 0.08 | 0.079 | 814 | 75,168 | 55,693 | 93,086 | 6.22x |
| target 0.16 | 0.156 | 1,615 | 136,827 | 94,304 | 167,239 | 3.41x |
| target 0.30 | 0.292 | 3,023 | 243,776 | 166,051 | 294,656 | 1.92x |

Fit `ED = 13,105 + 76.4 x spikes` (max residual 0.6 %; sweep floor 2 x 1,600 x 4 = 12,800); **crossover at 5,946 input spikes per sample = 57 % input rate** (beyond the swept range; extrapolated)

## Reading it

- **C1 is identical for all six networks** (65,876 cycles, 1.54x), as it
  must be: its input is the data. The rate penalty cannot move the C1
  board point; that axis is data, dataset and encoding (the DVS-Gesture
  per-sample result is the C1 activity axis).
- **C2 and C3 are where trained activity moves the verdict**, and it
  moves a long way: at 2 % activity ED K=4 beats dense P=4 by 10x (C2)
  and 14x (C3); at 30 % it still wins 1.6x / 1.9x. The dense engine's
  per-neuron cost grows with the fan-in (18 / 144 / 288 taps for C1 /
  C2 / C3) while ED's per-spike scatter cost grows only with C_OUT, so
  the deeper layers are more event-driven-friendly at any given rate.
- **Crossovers (extrapolated from the linear fits above): C2 ~48 %,
  C3 ~57 % input activity**, against ~31 % for C1 from the cycle
  model. No trained N-MNIST network reaches them: even the 30 % network
  sits at 1.6x. On this dataset the event-driven engine wins every conv
  layer at every activity a training run produces, and the question the
  meter has to answer is whether the fabric's energy per cycle follows
  the cycle count (C0003/C0038).
- Per-sample spread on ED grows with activity (C2: 1.30x at 2 %, 2.05x
  at 30 %) -- the deadline-latency caveat from the DVS-Gesture note
  applies here too.
- One seed per point; the cycle numbers are exact for these networks,
  the accuracy column carries the ~0.4 pp seed spread.

## Parallelism x activity: ED at K = 4 / 8 / 16 vs dense P = 4 / 8 / 16 on C2 and C3 (2026-09-20)

Same six networks and the 16-sample check set as the K = 4 bench above; ED K = 8
and K = 16 runs all bit-identical (24/24, `bench/ed_k8_*`, `bench/ed_k16_*`).
Dense P = 4 is the measured reference; P = 8 / 16 are that constant divided by
2 / 4 (the dense cost is exactly 1/P). Input rate is the fraction of the
layer's input bits set on the check set.
### C2 (dense P=4 383,612 cycles; P=8 191,806; P=16 95,903)

| network | input rate | ED K=4 | ED K=8 | ED K=16 | dense/ED at K=P=4 | at K=P=8 | at K=P=16 |
|---|---|---|---|---|---|---|---|
| baseline | 0.069 | 72,885 | 49,994 | 38,548 | 5.26x | 3.84x | 2.49x |
| target 0.02 | 0.023 | 38,297 | 30,592 | 26,739 | 10.02x | 6.27x | 3.59x |
| target 0.04 | 0.041 | 51,550 | 38,029 | 31,268 | 7.44x | 5.04x | 3.07x |
| target 0.08 | 0.078 | 80,259 | 54,132 | 41,069 | 4.78x | 3.54x | 2.34x |
| target 0.16 | 0.156 | 139,222 | 87,201 | 61,191 | 2.76x | 2.20x | 1.57x |
| target 0.30 | 0.290 | 240,475 | 144,011 | 95,779 | 1.60x | 1.33x | 1.00x |

Fits `ED = a + b x spikes` and matched-parallelism crossovers: K=P=4: a=20,803, b=41.0, crossover 48 %; K=P=8: a=20,778, b=23.0, crossover 40 %; K=P=16: a=20,765, b=14.0, crossover 29 %

### C3 (dense P=4 467,196 cycles; P=8 233,598; P=16 116,799)

| network | input rate | ED K=4 | ED K=8 | ED K=16 | dense/ED at K=P=4 | at K=P=8 | at K=P=16 |
|---|---|---|---|---|---|---|---|
| baseline | 0.082 | 78,214 | 47,643 | 32,358 | 5.97x | 4.90x | 3.61x |
| target 0.02 | 0.025 | 33,084 | 23,611 | 18,874 | 14.12x | 9.89x | 6.19x |
| target 0.04 | 0.042 | 45,978 | 30,473 | 22,720 | 10.16x | 7.67x | 5.14x |
| target 0.08 | 0.079 | 75,168 | 46,027 | 31,457 | 6.22x | 5.08x | 3.71x |
| target 0.16 | 0.156 | 136,827 | 78,859 | 49,875 | 3.41x | 2.96x | 2.34x |
| target 0.30 | 0.292 | 243,776 | 135,854 | 81,893 | 1.92x | 1.72x | 1.43x |

Fits `ED = a + b x spikes` and matched-parallelism crossovers: K=P=4: a=13,105, b=76.4, crossover 57 %; K=P=8: a=12,960, b=40.7, crossover 52 %; K=P=16: a=12,888, b=22.8, crossover 44 %

Reading: the same law as on DVS-Gesture -- the ED sweep floor (a ~ 2NT) does
not shrink with K while the dense reference halves with P, so the crossover
activity falls with parallelism: C2 48 / 40 / 29 %, C3 57 / 52 / 44 % at
K = P = 4 / 8 / 16. At K = P = 16 the 29 %-activity C2 network sits exactly on
the crossover (1.00x). The per-spike constants match DVS-Gesture's at every K
(C2 41.0 / 23.0 / 14.0 vs 40.4 / 22.7 / 13.9; C3 76.4 / 40.7 / 22.8 vs 74.0 /
39.5 / 22.2 cycles per spike): the cost model transfers across datasets at
every parallelism, not only at K = 4. Figure:
`experiments/figures/fig_crossover_vs_kp.png` (now both datasets at all three
K) and `fig_crossover_heatmap.png`.

