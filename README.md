# snn_parkour_fpga

Measuring, rather than estimating, the energy of event-driven vs dense spiking
neural network hardware on an FPGA. See the project brief for the full project brief
and `docs/decisions.md` for the running log of design decisions.

## Layout

| Path | Contents |
|---|---|
| `golden/` | Python fixed-point reference model — the source of truth |
| `train/` | snnTorch training, quantisation, firing-rate logging |
| `hdl/` | HDL sources (`common/`, `dense/`, `eventdriven/`) |
| `sim/` | Testbenches and simulation scripts |
| `host/` | PYNQ Python host code |
| `measure/` | INA226 / Joulescope logging and plotting |
| `experiments/` | Result data, plots, notebooks |
| `docs/` | Notes, decisions, thesis material |

## Environment (verified 2026-08-15)

- Python 3.9.0, `torch` 2.2.2, `snntorch` 1.0.0, `tonic` 1.6.0,
  `numpy` 1.23.5, `matplotlib` 3.4.1
- `iverilog` and `verilator` available locally — HDL can be simulated on this
  machine without Vivado
- Vivado is not on this machine; synthesis and board bring-up happen elsewhere
- N-MNIST test split cached in `data/` (396 MB, gitignored). The train split is
  a separate ~1 GB download: `python3 train/01_nmnist_peek.py --train`
- This python.org build has no linked CA certificates, so downloads fail with
  `CERTIFICATE_VERIFY_FAILED`. Scripts fall back to certifi's bundle
  automatically. Permanent fix, run once:
  `open "/Applications/Python 3.9/Install Certificates.command"`

## Progress

- [x] **M0** repo skeleton + single-neuron golden model cross-check
- [x] **M0** N-MNIST loading, input sparsity measured (16.83% non-zero)
- [x] **M0** network defined, resource budget reconciled against the project brief
- [x] **M0** trained on N-MNIST (96.9-97.6%); per-layer rates logged and
      plotted. Conv layers fire at 6-11%, FC at 30%.
- [ ] **M1** golden model — 8-bit weights, fixed-point membrane, spike traces
- [ ] **M2** one LIF neuron in HDL, bit-identical in simulation
- [ ] **M3** one dense conv layer
- [ ] **M4** PYNQ overlay, AXI DMA
- [ ] **M5** power measurement rig — first thesis result
- [ ] **M6** event-driven datapath
- [ ] **M7** crossover experiment
- [ ] **M8** robot (year two)

## GPU training (gpu-host)

An AMD Instinct MI210 is reachable at the `gpu-host` SSH host. Setup that
already exists there — do not reinstall:

- `~/esparkour_venv` — torch 2.10+rocm7.0 with the GPU working, plus snntorch.
  This venv belongs to the parkour project; **never let pip touch its numpy**
  (tonic would downgrade it, which is why tonic is not installed there).
- `~/nmnist_prep_venv` — tonic only, used once to pack the dataset.
- `~/snn_parkour_fpga` — rsync'd copy of this repo, packed dataset in
  `data/packed/`.

Sync and train:

```
rsync -az --exclude data --exclude .git --exclude __pycache__ --exclude 'experiments/*' ./ gpu-host:~/snn_parkour_fpga/
```

```
ssh gpu-host 'cd ~/snn_parkour_fpga && ~/esparkour_venv/bin/python train/03_train.py --epochs 10'
```

## Checks

Every component ships with something that proves it works. Run them:

```
python3 train/00_lif_demo.py && python3 train/01_nmnist_peek.py && python3 train/02_model_check.py
```

## The network

`train/model.py`. Encoder = C1/C2/C3 convs + 2x2 pool + FC to 128, every layer
LIF. The readout `Linear(128, n_classes)` is training scaffolding and does
**not** go on the FPGA. Two variants, both verified by `02_model_check.py`:

| | input | params | neurons | on-chip |
|---|---|---|---|---|
| N-MNIST (what M0 trains) | 2x34x34 | 56,096 | 8,944 | 72.2 KB (11.8% BRAM) |
| Target (what the FPGA implements) | 2x48x64 | 121,632 | 21,632 | 161.0 KB (26.3% BRAM) |

The FC layer holds **81%** of the target's weights. Whatever the event-driven
engine does about the FC layer will dominate the M7 energy result.
