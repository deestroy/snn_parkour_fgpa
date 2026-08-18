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
| `host/` | board<->Mac link: bare-metal C servers (`board/`), Mac-side JTAG loader + UART tools (`mac/`), framed protocol + client + golden mock |
| `measure/` | INA226 driver, idle-run-idle protocol, report (M5) |
| `experiments/` | Result data, plots, notebooks |
| `docs/` | Notes, decisions, thesis material |

## Environment (verified 2026-08-15)

- Python 3.9.0, `torch` 2.2.2, `snntorch` 1.0.0, `tonic` 1.6.0,
  `numpy` 1.23.5, `matplotlib` 3.4.1
- `iverilog` and `verilator` available locally — HDL can be simulated on this
  machine without Vivado
- Vivado/Vitis 2024.1 live on a Windows machine reached over RDP; the
  **ZedBoard is plugged into this Mac** and is programmed over its Digilent
  JTAG with OpenOCD (`host/mac/program.sh`) and observed over USB UART. Build
  outputs travel Windows -> Mac via Google Drive (RDP clipboard corrupts
  binaries; RDP folder redirection is blocked by the school).
- Board is a **ZedBoard (rev C)**, not the PYNQ-Z2 the brief planned for; no
  PYNQ image exists for it, hence bare metal. **Boot from SD** (BootROM ->
  FSBL -> app in DDR) is the normal run mode; JTAG from the Mac is for
  debugging. The block design MUST carry the ZedBoard preset (correct DDR
  part) and have HP0 enabled — see `docs/decisions.md` D0014/D0015 and
  `docs/m4_vivado_walkthrough.md`.
- N-MNIST test split cached in `data/` (396 MB, gitignored). The train split is
  a separate ~1 GB download: `python3 train/01_nmnist_peek.py --train`
- This python.org build has no linked CA certificates, so downloads fail with
  `CERTIFICATE_VERIFY_FAILED`. Scripts fall back to certifi's bundle
  automatically. Permanent fix, run once:
  `open "/Applications/Python 3.9/Install Certificates.command"`

## Progress

- [x] **M0** repo skeleton + single-neuron golden model cross-check
- [x] **M0** N-MNIST loading, input sparsity measured (13.8% non-zero over a random sample; see D0009)
- [x] **M0** network defined, resource budget reconciled against the project brief
- [x] **M0** trained on N-MNIST (96.9-97.6%); per-layer rates logged and
      plotted. Conv layers fire at 6-11%, FC at 30%.
- [x] **M1** golden model: all-integer network at 96.75% vs 96.60% float
      (−0.15 pp); membranes fit int16 with 3 bits headroom; HDL reference
      traces emitted by `train/06_golden_check.py`
- [x] **M2** one LIF neuron in Verilog, bit-identical to the golden model in
      simulation (4,060 checks, 0 mismatches; `bash sim/run_lif_tb.sh`).
      Simulation only — not yet synthesised.
- [x] **M3** dense conv engine, bit-identical on c1/c2/c3 (1.13M comparisons,
      0 mismatches; `bash sim/run_conv_tb.sh c1 c2 c3`). Simulation only.
- [x] **M4** C1 engine on the ZedBoard: **BOARD PASS, 16 samples, 9,280 words bit-identical to the golden model** (2026-08-18). SD boot, bare metal, framed UART to the Mac (`python3 host/uart_client.py`). DDR works (block design needed the ZedBoard preset — D0015).
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

Every component ships with something that proves it works. The full set:

```
python3 train/00_lif_demo.py && python3 train/02_model_check.py   # M0
python3 train/06_golden_check.py                                   # M1 (full split; --limit is biased, D0009)
bash sim/run_lif_tb.sh                                             # M2 neuron
bash sim/run_conv_tb.sh c1 c2 c3 && bash sim/run_fc_tb.sh          # M3 dense engines
bash sim/run_axis_tb.sh c1                                         # M4 AXIS wrapper
bash sim/run_ed_tb.sh c1                                           # M6 harness (dense engine as DUT for now)
python3 -c "from golden.eventdriven import verify_event_driven as v; print(v('c1', k=4))"   # M6 python engine
python3 host/mock_server.py --selftest                             # Stage B host side vs golden mock
python3 measure/protocol.py --mock                                 # M5 protocol vs mock meter
```

Board-side (needs the ZedBoard on USB): after an SD boot,
`python3 host/uart_client.py` is the M4 hardware check (BOARD PASS). JTAG
alternatives: `bash host/mac/program.sh <bit> <elf>`, `bash host/mac/stage_b.sh`.

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
