"""C0012: golden vectors for the DVS-Gesture C1 layer, from the REAL
quantised network (golden/dvsgesture_weights_int8.npz, D0008 scheme) and
REAL packed test frames (data/packed_dvsgesture/test_frames.npy).

Geometry is the robot-era r1 layer (2x64x64 -> 16x32x32, D0024), so the
same engines run unchanged; only weights, threshold (2^k = 128 for this
network's conv1) and inputs differ. The LIF rule is imported from
golden/network.py; the stride-2 3x3 pad-1 conv is computed here.

Emits the "g1" file set consumed by run_conv_p_tb.sh g1 / run_ed_tb.sh g1:
    conv_g1_w.hex, conv_g1_in.bin, conv_g1_s.bin, conv_g1_v.hex
    ed_g1_wt.hex,  ed_g1_spk.txt,  ed_g1_s.bin,   ed_g1_v.hex
Run:  python3 sim/export_dvsgesture_vectors.py [--samples 8]
"""

import argparse
import os
import sys

import numpy as np

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(REPO, "sim", "vectors")
WEIGHTS = os.path.join(REPO, "golden", "dvsgesture_weights_int8.npz")
FRAMES = os.path.join(REPO, "data", "packed_dvsgesture", "test_frames.npy")
sys.path.insert(0, REPO)
from golden.network import lif_update  # noqa: E402
from sim.export_robot_vectors import conv_s2, C_IN, H_IN, W_IN, C_OUT, H_OUT, W_OUT, T  # noqa: E402


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--samples", type=int, default=8)
    a = ap.parse_args()
    z = np.load(WEIGHTS)
    w = z["conv1"].astype(np.int64)            # (16, 2, 3, 3) int8 values
    k = int(z["conv1_k"]); thr = 2 ** k        # 128 for this network
    frames = (np.load(FRAMES)[:a.samples] > 0).astype(np.uint8)   # binarise (D0003)
    assert frames.shape[1:] == (T, C_IN, H_IN, W_IN), frames.shape
    assert w.shape == (C_OUT, C_IN, 3, 3)

    B = frames.shape[0]
    S = np.zeros((B, T, C_OUT, H_OUT, W_OUT), np.uint8)
    V = np.zeros((B, T, C_OUT, H_OUT, W_OUT), np.int64)
    for b in range(B):
        v = np.zeros((C_OUT, H_OUT, W_OUT), np.int64)
        for t in range(T):
            v, s = lif_update(v, conv_s2(frames[b, t], w), thr)
            V[b, t], S[b, t] = v, s

    os.makedirs(OUT, exist_ok=True)
    with open(os.path.join(OUT, "conv_g1_w.hex"), "w") as fh:
        for oc in range(C_OUT):
            for ic in range(C_IN):
                for ky in range(3):
                    for kx in range(3):
                        fh.write("%02x\n" % (int(w[oc, ic, ky, kx]) & 0xFF))
    with open(os.path.join(OUT, "conv_g1_in.bin"), "w") as fh:
        for bit in frames.ravel(): fh.write("%d\n" % bit)
    with open(os.path.join(OUT, "conv_g1_s.bin"), "w") as fh:
        for bit in S.ravel(): fh.write("%d\n" % bit)
    with open(os.path.join(OUT, "conv_g1_v.hex"), "w") as fh:
        for x in V.ravel(): fh.write("%04x\n" % (int(x) & 0xFFFF))
    with open(os.path.join(OUT, "ed_g1_wt.hex"), "w") as fh:
        for ic in range(C_IN):
            for ky in range(3):
                for kx in range(3):
                    for oc in range(C_OUT):
                        fh.write("%02x\n" % (int(w[oc, ic, ky, kx]) & 0xFF))
    with open(os.path.join(OUT, "ed_g1_spk.txt"), "w") as fh:
        for b in range(B):
            for t in range(T):
                idx = np.flatnonzero(frames[b, t].ravel())
                fh.write("%d\n" % len(idx))
                for x in idx: fh.write("%d\n" % x)
    with open(os.path.join(OUT, "ed_g1_s.bin"), "w") as fh:
        for bit in S.ravel(): fh.write("%d\n" % bit)
    with open(os.path.join(OUT, "ed_g1_v.hex"), "w") as fh:
        for x in V.ravel(): fh.write("%04x\n" % (int(x) & 0xFFFF))

    assert V.max() < 32767 and V.min() > -32768, "membranes overflow int16"
    print("g1 (DVS-Gesture, real weights): %d samples, in rate %.4f, out rate %.4f, "
          "|V|max %d, THRESHOLD=%d" % (B, frames.mean(), S.mean(), np.abs(V).max(), thr))
    print("NOTE: run the engines with THRESH=%d." % thr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
