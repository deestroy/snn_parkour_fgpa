"""M0, component 1: one LIF neuron, built twice, checked against itself.

Run:  python3 train/00_lif_demo.py

Why this exists. The golden-model rule says every hardware module must match a
Python reference bit-for-bit. That discipline is worthless unless we practise
it from the smallest unit upward. So: drive snnTorch's Leaky neuron and our own
hand-written loop (golden/lif.py) with the same current, and assert they agree
exactly. If this fails, we have misunderstood the neuron model -- which is much
cheaper to discover now than in a waveform viewer in M2.

It also prints the spike raster and saves a plot, so you can see what a leaky
integrate-and-fire neuron actually does.
"""

import os
import sys

import numpy as np
import torch
import snntorch as snn

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from golden.lif import lif_step  # noqa: E402

T = 40           # timesteps to simulate
BETA = 0.9       # membrane keeps 90% of itself each step
THRESHOLD = 1.0
OUT_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                       "experiments")


def snntorch_lif(current_f32: np.ndarray):
    """Same neuron, using the library. Returns (spikes, membrane) as float32."""
    lif = snn.Leaky(beta=BETA, threshold=THRESHOLD)  # defaults: reset by
    mem = torch.zeros(1)                             # subtraction, delayed
    spk_out, mem_out = [], []
    with torch.no_grad():
        for n in range(current_f32.shape[0]):
            cur = torch.tensor([current_f32[n]], dtype=torch.float32)
            spk, mem = lif(cur, mem)
            spk_out.append(spk.item())
            mem_out.append(mem.item())
    return (np.array(spk_out, dtype=np.float32),
            np.array(mem_out, dtype=np.float32))


def make_current() -> np.ndarray:
    """A step of constant current, then silence. Enough to make it fire, then
    show the leak draining the membrane back toward rest."""
    current = np.zeros(T, dtype=np.float32)
    current[5:25] = np.float32(0.25)
    return current


def raster(spikes: np.ndarray) -> str:
    return "".join("|" if s else "." for s in spikes)


def main() -> int:
    current = make_current()

    spk_ref, mem_ref = lif_step(current, BETA, THRESHOLD,
                                reset_delay=True, fire_on_equal=False)
    spk_lib, mem_lib = snntorch_lif(current)

    print("input current : " + "".join("#" if c > 0 else "." for c in current))
    print("golden spikes : " + raster(spk_ref))
    print("snnTorch      : " + raster(spk_lib))
    print("spike count   : golden=%d  snnTorch=%d"
          % (int(spk_ref.sum()), int(spk_lib.sum())))
    print("firing rate   : %.1f%% of timesteps" % (100.0 * spk_ref.mean()))

    max_mem_err = float(np.max(np.abs(mem_ref.astype(np.float64)
                                      - mem_lib.astype(np.float64))))
    print("max |V| difference : %r" % max_mem_err)

    spikes_match = np.array_equal(spk_ref, spk_lib)
    mem_match = np.array_equal(mem_ref, mem_lib)
    print("spikes bit-identical   : %s" % spikes_match)
    print("membrane bit-identical : %s" % mem_match)

    _save_plot(current, spk_ref, mem_ref)

    if not (spikes_match and mem_match):
        print("\nFAIL: the two implementations disagree. Do not build on this.")
        return 1
    print("\nPASS: one neuron, two implementations, identical output.")
    return 0


def _save_plot(current, spikes, membrane) -> None:
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    os.makedirs(OUT_DIR, exist_ok=True)
    fig, ax = plt.subplots(3, 1, figsize=(8, 5), sharex=True)
    ax[0].step(range(T), current, where="post")
    ax[0].set_ylabel("input I")
    ax[1].plot(range(T), membrane)
    ax[1].axhline(THRESHOLD, linestyle="--", linewidth=1)
    ax[1].set_ylabel("membrane V")
    ax[2].eventplot(np.nonzero(spikes)[0], lineoffsets=0, linelengths=0.8)
    ax[2].set_ylabel("spikes")
    ax[2].set_xlabel("timestep")
    ax[0].set_title("One LIF neuron (beta=%.2f, threshold=%.1f)"
                    % (BETA, THRESHOLD))
    fig.tight_layout()
    path = os.path.join(OUT_DIR, "m0_lif_demo.png")
    fig.savefig(path, dpi=120)
    print("plot saved -> %s" % os.path.relpath(path, os.getcwd()))


if __name__ == "__main__":
    raise SystemExit(main())
