# snn_parkour_fpga

Spiking-neural-network hardware on a ZedBoard (Zynq XC7Z020), in two
datapaths behind one wrapper: **dense** (every neuron and synapse every
timestep) and **event-driven** (a spike queue and scatter-accumulate that
touch only what fired). The thesis question is where the event-driven
design stops winning as activity rises, answered with **energy measured at
the board's power input**, not a synthesis-tool estimate. The workload is a
learned quadruped perception network (ES-Parkour, Zhang et al., ICME 2025);
N-MNIST and DVS-Gesture are the benchmarks.

## How it is built

1. **Golden model first.** A Python fixed-point reference (`golden/`) is the
   source of truth; every hardware module must be **bit-identical** to it,
   never merely close. Trained networks (`train/`, snnTorch) are quantised
   to int8 weights with power-of-two scales and int16 membranes, and the
   golden model emits the traces the testbenches check against.
2. **One engine at a time, verified in simulation** (`hdl/`, `sim/`): the LIF
   neuron, the dense conv engine (P lanes), the event-driven conv engine
   (K banks), the FC layer, and the AXIS wrapper that feeds both engines
   identically. `bash check_all.sh` runs every check (30, ~15 min).
3. **Onto the board** with the exact configuration that was simulated: baked
   weights, bare-metal server over UART/DMA, a pre-write checklist on the
   exported hardware description, and a pre-registered prediction before
   every silicon pass (`experiments/*prereg*.md`).
4. **Sweep the axes**: parallelism (K = P), activity (data, encoding, and
   networks trained to target firing rates), timesteps T, and the dataset.
5. **Measure energy** (M5, meter pending) and put the learned robot
   network on the same hardware (year two: `robot/isaac/`).

Design decisions and their reasons are logged in `docs/decisions.md`; the
standing review of what could be wrong is `docs/corrections.md`; every
number with its provenance is in **`docs/results_ledger.md`**.

## Major results so far (2026-09-19)

All latencies are engine-only at 100 MHz, measured on silicon unless marked
sim, and every silicon or simulated run is bit-identical to the golden model.

| result | value | where |
|---|---|---|
| Matched parallelism, N-MNIST C1, silicon | **ED K=4 beats dense P=4 by 1.52x** (688.5 vs 1048.9 us); at K=P=8 **dense wins** (540.3 vs 575.5 us) | `experiments/board_*.md` |
| Parallelism crossover | K = P ~ 6.6 (N-MNIST), 5.8 (DVS-Gesture); cycle model `2NT + 5.0 s + 71.7 s/K` vs dense `88 N/P`, within 0.3 % of simulation and ~1 % of silicon | `experiments/latency_sim/`, `experiments/dvsgesture/latency_sim/` |
| Activity crossover on real data (sim) | DVS-Gesture at K=P=4: ED wins on clips below ~30 % input density and loses on the two densest; **2.88 ms mean vs 3.60 ms dense, but 4.57 ms on the worst clip** | `experiments/dvsgesture/latency_sim/` |
| DVS-Gesture on silicon | ED K=4: 8/8 bit-identical, 2,970.8 us mean, board = sim + 92.9 us on every clip; dense build next | `experiments/dvsgesture/board_ed_k4_20260919.md` |
| Activity by training (sim) | N-MNIST networks at 2-30 % conv rates, accuracy flat to 16 %; ED over dense on C2/C3 from 10-14x at 2 % to 1.6-1.9x at 30 %, crossovers ~48 % / ~57 % | `experiments/rate_sweep/` |
| Accuracy | N-MNIST 96.6-97.0 % (3 seeds), DVS-Gesture 63-69 % (3 seeds, T=4, 2x64x64); quantisation drop within noise | `experiments/dvsgesture/` |
| Hardware limit found | the int16 FC membrane overflows on DVS-Gesture at T=16, at T=8 for one seed in three, and at 34 % activity | C0046 |
| Year two on the paper's stack | teacher trained in IsaacGym (95-99 % success per terrain); the 58k spiking encoder distils inside extreme-parkour's own loop (running); on 64 real robot event frames ED K=4 is 1.94x faster than dense on the mean, 1.43x on the worst frame | `robot/isaac/`, `experiments/p1_distill/` |
| Verification result | the second benchmark exposed a sweep bug invisible to N-MNIST (neuron 0's current never zeroed, C0044): fixed, guarded in the ladder | `docs/corrections.md` |
| Energy | **not yet measured** (meter pending); tool estimate only | `docs/results_ledger.md` §6 |

## Layout

| Path | Contents |
|---|---|
| `golden/` | fixed-point reference model, the Python event-driven engine |
| `train/` | training, quantisation, golden check, dataset packing |
| `hdl/` | Verilog: `common/` (LIF), `dense/` (P-lane engine, AXIS wrapper, top), `eventdriven/` (scatter, K-bank engine) |
| `sim/` | testbenches, vector exporters, bench runners, lint |
| `host/` | bare-metal board server, Mac-side client and card tools, Vivado build script |
| `measure/` | meter protocol and report (M5) |
| `robot/` | year two: IsaacGym port of the event simulator, encoder, distillation, evaluation |
| `experiments/` | every result: board records, pre-registrations, sweeps, logs |
| `docs/` | decisions, corrections, results ledger, Vivado session notes, environment |

## Running the checks

```bash
bash check_all.sh
```

Board-side runs need the ZedBoard on USB after an SD boot:
`python3 host/uart_client.py` (see `docs/vivado_session_next.md` for the
build and card-writing procedure). Environment, hosts and the network
definition: `docs/environment.md`.
