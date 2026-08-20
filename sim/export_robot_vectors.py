"""P1 risk retirement: golden vectors for the ROBOT-ERA C1 geometry
(2x64x64 -> 16x32x32, D0024) with a synthetic network, so both engines can
be verified bit-identical at the year-two shape before the trained network
exists. Weights are random int8 (seeded), inputs Bernoulli at a trained-
like rate. The LIF rule is IMPORTED from golden/network.py (lif_update),
not re-implemented, so this exporter cannot drift from the source of truth;
only the conv (stride-2 3x3 pad-1, geometry-agnostic) is computed here.

Emits the exact file set run_conv_tb.sh / run_ed_tb.sh consume, under the
layer name "r1":
    conv_r1_w.hex, conv_r1_in.bin, conv_r1_s.bin, conv_r1_v.hex
    ed_r1_wt.hex, ed_r1_spk.txt, ed_r1_s.bin, ed_r1_v.hex

Run:  python3 sim/export_robot_vectors.py [--samples 8] [--density 0.08]
"""

import argparse
import os
import sys

import numpy as np

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(REPO, "sim", "vectors")
sys.path.insert(0, REPO)
from golden.network import lif_update  # noqa: E402  the one true rule

C_IN, H_IN, W_IN = 2, 64, 64
C_OUT, H_OUT, W_OUT = 16, 32, 32
T = 4
THRESHOLD = 64


def conv_s2(spikes: np.ndarray, w: np.ndarray) -> np.ndarray:
    """Integer 3x3 stride-2 pad-1 conv of a binary map.
    spikes (CI,H,W) uint8, w (CO,CI,3,3) int64 -> (CO,HO,WO) int64."""
    out = np.zeros((C_OUT, H_OUT, W_OUT), np.int64)
    for ky in range(3):
        for kx in range(3):
            iy = 2 * np.arange(H_OUT) + ky - 1
            ix = 2 * np.arange(W_OUT) + kx - 1
            my, mx = (iy >= 0) & (iy < H_IN), (ix >= 0) & (ix < W_IN)
            sub = spikes[:, iy[my][:, None], ix[mx][None, :]].astype(np.int64)
            contrib = np.tensordot(w[:, :, ky, kx], sub, axes=(1, 0))
            out[np.ix_(range(C_OUT), np.where(my)[0], np.where(mx)[0])] += contrib
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--samples", type=int, default=8)
    ap.add_argument("--density", type=float, default=0.08)
    ap.add_argument("--seed", type=int, default=42)
    a = ap.parse_args()
    rng = np.random.default_rng(a.seed)
    w = rng.integers(-32, 33, size=(C_OUT, C_IN, 3, 3)).astype(np.int64)
    frames = (rng.random((a.samples, T, C_IN, H_IN, W_IN)) < a.density).astype(np.uint8)

    B = a.samples
    S = np.zeros((B, T, C_OUT, H_OUT, W_OUT), np.uint8)
    V = np.zeros((B, T, C_OUT, H_OUT, W_OUT), np.int64)
    for b in range(B):
        v = np.zeros((C_OUT, H_OUT, W_OUT), np.int64)
        for t in range(T):
            i = conv_s2(frames[b, t], w)
            v, s = lif_update(v, i, THRESHOLD)
            V[b, t], S[b, t] = v, s

    os.makedirs(OUT, exist_ok=True)
    # dense-engine files (wrom order: ((oc*C_IN + ic)*3 + ky)*3 + kx)
    with open(os.path.join(OUT, "conv_r1_w.hex"), "w") as fh:
        for oc in range(C_OUT):
            for ic in range(C_IN):
                for ky in range(3):
                    for kx in range(3):
                        fh.write("%02x\n" % (int(w[oc, ic, ky, kx]) & 0xFF))
    with open(os.path.join(OUT, "conv_r1_in.bin"), "w") as fh:
        for bit in frames.ravel():
            fh.write("%d\n" % bit)
    with open(os.path.join(OUT, "conv_r1_s.bin"), "w") as fh:
        for bit in S.ravel():
            fh.write("%d\n" % bit)
    with open(os.path.join(OUT, "conv_r1_v.hex"), "w") as fh:
        for x in V.ravel():
            fh.write("%04x\n" % (int(x) & 0xFFFF))
    # event-driven files (W_T order: ((ic*3 + ky)*3 + kx)*C_OUT + oc)
    with open(os.path.join(OUT, "ed_r1_wt.hex"), "w") as fh:
        for ic in range(C_IN):
            for ky in range(3):
                for kx in range(3):
                    for oc in range(C_OUT):
                        fh.write("%02x\n" % (int(w[oc, ic, ky, kx]) & 0xFF))
    with open(os.path.join(OUT, "ed_r1_spk.txt"), "w") as fh:
        for b in range(B):
            for t in range(T):
                idx = np.flatnonzero(frames[b, t].ravel())
                fh.write("%d\n" % len(idx))
                for x in idx:
                    fh.write("%d\n" % x)
    with open(os.path.join(OUT, "ed_r1_s.bin"), "w") as fh:
        for bit in S.ravel():
            fh.write("%d\n" % bit)
    with open(os.path.join(OUT, "ed_r1_v.hex"), "w") as fh:
        for x in V.ravel():
            fh.write("%04x\n" % (int(x) & 0xFFFF))

    assert V.max() < 32767 and V.min() > -32768, "membranes overflow int16"
    print("r1: %d samples, input rate %.4f, output rate %.4f, |V|max %d"
          % (B, frames.mean(), S.mean(), np.abs(V).max()))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
