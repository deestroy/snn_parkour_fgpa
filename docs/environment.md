# Environment, hosts and the network definition (moved out of README.md on 2026-09-19)

Kept verbatim from the README as of 2026-08-19; the NVIDIA box that arrived on
2026-09-17 is described in docs/decisions.md (2026-09-17 entry) and robot/isaac/README.md.

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
