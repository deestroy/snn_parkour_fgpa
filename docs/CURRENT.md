# What is current, what is superseded

One page, kept at the top of the repository's reading order. If a number
appears in two places and they disagree, **this page decides**, and the
"source of truth" column says which file the number is read from rather than
quoted from.

Last revised 2026-09-20 after a full audit of the repository against its own
data files. Every row below was recomputed from the file named, not carried
over.

---

## 1. Current headline numbers

| quantity | current value | basis | source of truth |
|---|---|---|---|
| ED vs dense, N-MNIST C1, matched K = P = 4 | ED 688.5 us vs dense 1,048.9 us, **ED 1.52x** | board, engine-only ticks | `docs/results_ledger.md` §1 |
| ED vs dense, N-MNIST C1, K = P = 8 | ED 575.5 us vs dense 540.3 us, **dense 1.065x** | board | `docs/results_ledger.md` §1 |
| ED vs dense, DVS-Gesture C1, K = P = 4 | ED 2,970.8 us mean vs dense 3,706.5 us, **ED 1.248x**, ED wins 6 of 8 clips | board | `docs/results_ledger.md` §3 |
| Parallelism crossover | **K = P = 7.4** (wrapper-inclusive), 7.3 engine-only | fitted from the cycle files every run | `docs/thesis_tables/crossover.md` |
| Activity crossover, DVS-Gesture C1 | ~10,000 input spikes per clip (~30.5 % density) | sim, confirmed on board | `experiments/dvsgesture/latency_sim/` |
| Trained-activity crossovers, C2 / C3 | N-MNIST 48 / 57 % at K=P=4, falling to 29 / 44 % at K=P=16; DVS-Gesture 43 / 48 %, falling to 26 / 37 % | sim | `docs/thesis_tables/crossover.md` |
| Robot event frames, 64 of them | ED 1.73 ms mean, 2.75 ms worst; dense 3.60 ms; **2.09x / 1.31x** | sim | `experiments/p1_distill/isaac_i1_ed_k4_cycles_64.txt` |
| Accuracy, N-MNIST | 96.6-97.3 %, mean 97.0 (3 seeds, **one run each**) | gpu | `docs/thesis_tables/accuracy_rates.md` |
| Accuracy, DVS-Gesture | 63-69 % at T=4 (3 seeds, one run each; run-to-run noise ~1 pp) | gpu | same |
| Verification ladder | **33 checks** | count of `run "` lines | `check_all.sh` |
| Board passes | **14**, zero correctness misses | | `experiments/silicon_ledger.md` |
| Energy | **none measured yet.** Every energy figure in the repository is a Vivado estimate. | | `experiments/power_estimates/README.md` |

## 2. Numbers that were wrong and have been corrected

Each of these was quoted somewhere in the repository until the date given.
They are listed so that an older copy of a file, or a note taken from one,
can be recognised as stale.

| was | is | why | correction |
|---|---|---|---|
| Parallelism crossover K = P ~ 6.6 | **7.4** | arithmetic slip; 6.6 never followed from the two fits printed beside it | C0049 |
| Robot frames 1.86 ms / 2.52 ms, 1.94x / 1.43x | **1.73 / 2.75 ms, 2.09x / 1.31x** | the "64 frames" figures were computed on the first 8 | C0048 |
| N-MNIST input density ~5-6 %, DVS-Gesture ~4x that | **13.6 %**, DVS-Gesture ~2x | miscounted; the vectors give 20,093 spikes over 16 samples | audit 2026-09-20 |
| "C1's ~31 % activity" | **13.6 %** activity; 31 % is the model-derived break-even | two different quantities conflated | audit 2026-09-20 |
| Ladder "30 checks" | **33** | stale count | audit 2026-09-20 |
| "Seven" power estimates | **fourteen** | stale count | audit 2026-09-20 |
| Sim-vs-board "0.4-1.5 %" | **0.5-2.3 %**, better stated as a constant per pass | mixed a raw offset with an offset-corrected residual | audit 2026-09-20 |
| dense fit 407.2k/P + 2.0k | **406.9k/P + 2.3k** | the stated fit misses the measured P=4 point by 259 cycles | audit 2026-09-20 |
| ED board-minus-sim +10.5 / +10.7 us | **+10.9 us** | taken from a rounded 678 us rather than the cycle file | audit 2026-09-20 |
| M1 baseline golden accuracy 96.60 % | **96.75 %** | disagreed with the same network's other record | audit 2026-09-20 |
| "15/15 gates pass" (T sweep) | **9/9** | the 15 was the rate sweep's run count | audit 2026-09-20 |
| "6 of 15 runs" fail the accuracy gate | **5 of 15**, plus 3 membrane failures | recount from the logs | audit 2026-09-20 |
| "BRAM grows ~2x with K" | flat 4.0 tiles of banks from K=2 to K=8, doubling at K=16 | primitive granularity, not bank count | C0052 |

## 3. Superseded material, marked in place

**Do not cite these.** Each file carries its own marker too.

| where | what is superseded | use instead |
|---|---|---|
| `docs/baseline_table.md`, our two rows | 1.51 ms ED and 4.409 ms dense P=1, from board passes 1-2 (2026-08) before the engine and wrapper were rebuilt | 688.5 us ED K=4, 1,048.9 us dense P=4 |
| `measure/dmm_protocol.md` burst sizing | "ED K=4 1.51 ms", "--burst 12000 = ~18 s" | 688.5 us, so 12,000 bursts is ~8.3 s |
| `docs/vivado_session_next.md` BRAM note | "expect ~2x the K=4 count" | failed at pass 5; see C0052 |
| `experiments/power_estimates/README.md`, four rows | marked superseded/intermediate; **their reports are not in this repository** | cite only the fourteen named rows |
| `experiments/dvsgesture/t8/`, `t16/` seed 0 | the original logs were overwritten and cannot be regenerated (training is not reproducible, C0050) | the transcribed numbers in `experiments/dvsgesture/README.md`; the retrain in `c0046/rerun_seed0/` is a *different network* |
| Dated entries in `docs/decisions.md` | an append-only log: entries are correct as of their date and are not edited | the current value in this table |
| Pre-registration files | never edited after the fact, by design; corrections are appended as footnotes | the footnote at the end of each |

## 4. Claims that are weaker than they read

These are not errors in a number; they are statements that need qualifying.

- **The cost models quoted in most places are C1 constants.** Dense `88.0 N/P`
  and the ED `71.7 s/K` hold for C1 only. The general dense law is
  `(N/P) x T x (9 C_IN + 4) + 4`, exact to the cycle on all six layer-dataset
  pairs; the general ED scatter term is about `1.12 x 4 C_OUT` per spike, an
  empirical fit with ~4 % spread. The dense law is a derivation from the state
  machine; the ED one is a regression. They should not be presented with equal
  confidence.
- **"Engine-only" latency includes the DMA round trip.** The ARM's global timer
  brackets a cache flush, both transfers, a busy-poll and a cache invalidate.
  Only UART framing and CRC are outside it.
- **Accuracy figures are single training runs.** Training is not reproducible
  at a fixed seed on this hardware (C0050): two runs of identical code put the
  DVS-Gesture output membrane at 98 % and 102 % of int16.
- **One layer is on silicon.** C1. C2, C3 and FC are bit-identical in
  simulation only.

## 5. Open questions that affect results (not yet decided)

| # | question | why it matters | status |
|---|---|---|---|
| 1 | The dense engine's 4-cycle tail is not pipelined; the ED sweep was (C0030) | 18.2 % of dense cycles on C1. Pipelining it moves the C1 verdict from ED 1.54x to ~1.3x, the DVS-Gesture mean from 1.25x to ~1.03x, and the parallelism crossover from 7.3 to ~5.6-6.0. Every verdict's direction survives; the margins roughly halve | **open, user's decision** |
| 2 | Engine replication does not enforce lockstep | per-engine energy divides a measured delta by the replica count, which assumes the replicas do identical work | **open, before the meter** |
| 3 | T is not parameterised past the wrapper | the synthesis top and the board server hardwire 4, so the T-sweep projections describe a build the flow cannot produce | **open**, ~3 lines to fix |
| 4 | K dividing C_OUT is assumed but not enforced | a non-dividing K would corrupt silently | **open**, one elaboration check |
| 5 | The int16 membrane ceiling on DVS-Gesture | C0046 options costed; fc k=7 makes the verdict run-independent | **open, user's decision** |
