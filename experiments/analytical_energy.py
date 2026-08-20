"""C0022(a): the ES-Parkour-style ANALYTICAL energy for OUR network, by
their method — operation counts x 45 nm per-op constants (MAC 4.6 pJ,
AC 0.9 pJ) — so the measured figure, when the meter exists, audits the
published methodology on a network where ground truth is available.

SNN ops (ACs): one accumulate per (spike x fan-out weight touched).
ANN-equivalent (MACs): every weight fires every timestep-equivalent pass.
Counted from the golden traces (16-sample set; full-split rates differ
slightly and are noted).

Run: python3 experiments/analytical_energy.py
"""
import os
import sys

import numpy as np

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, REPO)

E_MAC, E_AC = 4.6e-12, 0.9e-12   # J, 45 nm (Horowitz), as ES-Parkour uses

z = np.load(os.path.join(REPO, "golden", "traces_m1.npz"))
B = z["in"].shape[0]; T = z["in"].shape[1]

def conv_fanout(H_OUT, W_OUT, C_OUT, spikes):
    """ACs for a stride-2 3x3 conv layer: each input spike at (ic,iy,ix)
    touches its reachable output block x C_OUT weights. Count exactly."""
    total = 0
    Bs, Ts, C, H, W = spikes.shape
    for b in range(Bs):
        for t in range(Ts):
            idx = np.argwhere(spikes[b, t] != 0)
            for (ic, iy, ix) in idx:
                oy0 = 0 if iy == 0 else iy >> 1
                oy1 = min((iy + 1) >> 1, H_OUT - 1)
                ox0 = 0 if ix == 0 else ix >> 1
                ox1 = min((ix + 1) >> 1, W_OUT - 1)
                total += (oy1 - oy0 + 1) * (ox1 - ox0 + 1) * C_OUT
    return total

layers = []
sin = (z["in"] != 0)
layers.append(("c1", conv_fanout(17, 17, 16, sin), 288 * 17 * 17))
s1 = (z["c1_S"] != 0).transpose(1, 0, 2, 3, 4) if z["c1_S"].shape[0] == T else (z["c1_S"] != 0)
# trace arrays are (T, B, ...) lists stacked; normalise to (B, T, ...)
def bt(a):
    a = np.asarray(a) != 0
    return a if a.shape[0] == B else a.transpose(1, 0, *range(2, a.ndim))
layers = [("c1", conv_fanout(17, 17, 16, bt(z["in"])), 288 * 17 * 17),
          ("c2", conv_fanout(9, 9, 32, bt(z["c1_S"])), 4608 * 9 * 9),
          ("c3", conv_fanout(5, 5, 64, bt(z["c2_S"])), 18432 * 5 * 5)]
# FC: pooled spikes x 128 outputs; pooled = sum-pool of c3 spikes (counts!)
c3 = bt(z["c3_S"]).astype(np.int64)
pooled_counts = c3[:, :, :, 0:4:2, 0:4:2] + c3[:, :, :, 0:4:2, 1:4:2] \
              + c3[:, :, :, 1:4:2, 0:4:2] + c3[:, :, :, 1:4:2, 1:4:2]
layers.append(("fc", int(pooled_counts.sum()) * 128, 256 * 128))

print("%-4s %14s %14s %10s %10s %8s" % ("layer", "SNN ACs/sample", "ANN MACs/sample", "SNN uJ", "ANN uJ", "ratio"))
tot_ac = tot_mac = 0
for name, acs, macs_per_pass in layers:
    acs_s = acs / B
    macs_s = macs_per_pass * T          # ANN equivalent at same T passes
    tot_ac += acs_s; tot_mac += macs_s
    print("%-4s %14.0f %14.0f %10.4f %10.4f %7.2f%%" % (
        name, acs_s, macs_s, acs_s * E_AC * 1e6, macs_s * E_MAC * 1e6,
        100 * acs_s * E_AC / (macs_s * E_MAC)))
print("%-4s %14.0f %14.0f %10.4f %10.4f %7.2f%%" % (
    "SUM", tot_ac, tot_mac, tot_ac * E_AC * 1e6, tot_mac * E_MAC * 1e6,
    100 * tot_ac * E_AC / (tot_mac * E_MAC)))
print("\nES-Parkour-method analytical energy, THIS network: %.4f uJ/inference"
      % (tot_ac * E_AC * 1e6))
print("ANN-equivalent analytical: %.4f uJ  ->  claimed saving %.1f %%"
      % (tot_mac * E_MAC * 1e6, 100 * (1 - tot_ac * E_AC / (tot_mac * E_MAC))))
print("\nThese numbers exclude memory, clocks, static power and the host —")
print("that exclusion is precisely what the measured figure will audit.")
