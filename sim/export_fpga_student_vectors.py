"""P1 close-out: quantise the DISTILLED FPGA-student encoder's conv weights
(D0008 scheme: int8, power-of-two scales, threshold 2^k) and emit r1-format
golden vectors from REAL event frames recorded in the simulator, so both
engines can be verified bit-identical against the actual year-two network.

Inputs:  robot/artifacts/fpga_student.pt   (copied from the GPU box)
         robot/artifacts/event_frames.npz  (recorded sim rollout frames)
Run:     python3 sim/export_fpga_student_vectors.py [--layer 1]
Emits:   the ed_r1_*/conv_r1_* file set (same names as the synthetic
         exporter, so run_conv_tb.sh r1 / run_ed_tb.sh r1 just work),
         computed with the C1 weights from the checkpoint.

Only C1 is exported for now (the engines are per-layer; C2/C3 follow the
same path once C1 closes). The LIF rule is imported from golden/network.py.
"""

import argparse
import os
import sys

import numpy as np

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(REPO, "sim", "vectors")
ART = os.path.join(REPO, "robot", "artifacts")
sys.path.insert(0, REPO)
from golden.network import lif_update  # noqa: E402
from sim.corner_exposure import report  # noqa: E402

C_IN, H_IN, W_IN = 2, 64, 64
C_OUT, H_OUT, W_OUT = 16, 32, 32
T = 4


def load_c1_weight(ck):
    """conv1 weight from either checkpoint layout:
    recreation  fpga_student.pt   -> ck["student"]["encoder.c1.weight"]
    IsaacGym port (rsl_rl runner) -> ck["depth_encoder_state_dict"]["base_backbone.enc.c1.weight"]"""
    if "depth_encoder_state_dict" in ck:
        return ck["depth_encoder_state_dict"]["base_backbone.enc.c1.weight"]
    sd = ck["student"] if "student" in ck else ck
    return sd["encoder.c1.weight"]


def load_frames(path: str, n: int) -> np.ndarray:
    """Event frames as (B, T, 2, 64, 64) 0/1.
    Old recorder (MuJoCo): frames (B, T, 2, H, W), T consecutive tick frames.
    IsaacGym recorder: frames (B, 2, H, W) one tick frame per sample plus a
    `window` field; "repeat" (the student's direct coding) repeats it T times."""
    z = np.load(path)
    fr = (z["frames"][:n] != 0).astype(np.uint8)
    if fr.ndim == 5:
        return fr
    window = str(z["window"]) if "window" in z.files else "repeat"
    assert window == "repeat", "consecutive windows must be recorded as (B, T, ...) frames"
    return np.repeat(fr[:, None], T, axis=1)


def choose_k(w: np.ndarray) -> int:
    """Largest shift with zero clipping (D0008)."""
    k = 0
    while 127.0 / (2 ** (k + 1)) >= np.abs(w).max() and k < 14:
        k += 1
    return k


def conv_s2(spikes, w):
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
    ap.add_argument("--ckpt", default=os.path.join(ART, "fpga_student.pt"))
    ap.add_argument("--frames", default=os.path.join(ART, "event_frames.npz"))
    ap.add_argument("--samples", type=int, default=8)
    ap.add_argument("--name", default="r1",
                    help="vector-set name: r1 (MuJoCo recreation frames) or i1 (IsaacGym port frames)")
    a = ap.parse_args()
    import torch
    ck = torch.load(a.ckpt, map_location="cpu", weights_only=False)
    w_f = load_c1_weight(ck).numpy()               # (16, 2, 3, 3) float
    k = choose_k(w_f)
    w_q = np.clip(np.round(w_f * (2 ** k)), -128, 127).astype(np.int64)
    thr = 2 ** k                                    # threshold 1.0 -> 2^k
    print("c1: max|w| %.4f  k=%d  threshold=%d  rms err %.5f"
          % (np.abs(w_f).max(), k, thr,
             float(np.sqrt(np.mean((w_q / 2**k - w_f) ** 2)))))

    frames = load_frames(a.frames, a.samples)      # (B, T, 2, 64, 64) 0/1
    B = frames.shape[0]
    assert frames.shape[1:] == (T, C_IN, H_IN, W_IN), frames.shape

    S = np.zeros((B, T, C_OUT, H_OUT, W_OUT), np.uint8)
    V = np.zeros((B, T, C_OUT, H_OUT, W_OUT), np.int64)
    for b in range(B):
        v = np.zeros((C_OUT, H_OUT, W_OUT), np.int64)
        for t in range(T):
            i = conv_s2(frames[b, t], w_q)
            v, s = lif_update(v, i, thr)
            V[b, t], S[b, t] = v, s
    assert V.max() < 32767 and V.min() > -32768, "membranes overflow int16"

    os.makedirs(OUT, exist_ok=True)
    with open(os.path.join(OUT, "conv_%s_w.hex" % a.name), "w") as fh:
        for oc in range(C_OUT):
            for ic in range(C_IN):
                for ky in range(3):
                    for kx in range(3):
                        fh.write("%02x\n" % (int(w_q[oc, ic, ky, kx]) & 0xFF))
    with open(os.path.join(OUT, "ed_%s_wt.hex" % a.name), "w") as fh:
        for ic in range(C_IN):
            for ky in range(3):
                for kx in range(3):
                    for oc in range(C_OUT):
                        fh.write("%02x\n" % (int(w_q[oc, ic, ky, kx]) & 0xFF))
    with open(os.path.join(OUT, "conv_%s_in.bin" % a.name), "w") as fh:
        for bit in frames.ravel():
            fh.write("%d\n" % bit)
    for name, arr in (("conv_%s_s.bin" % a.name, S), ("ed_%s_s.bin" % a.name, S)):
        with open(os.path.join(OUT, name), "w") as fh:
            for bit in arr.ravel():
                fh.write("%d\n" % bit)
    for name in ("conv_%s_v.hex" % a.name, "ed_%s_v.hex" % a.name):
        with open(os.path.join(OUT, name), "w") as fh:
            for x in V.ravel():
                fh.write("%04x\n" % (int(x) & 0xFFFF))
    with open(os.path.join(OUT, "ed_%s_spk.txt" % a.name), "w") as fh:
        for b in range(B):
            for t in range(T):
                idx = np.flatnonzero(frames[b, t].ravel())
                fh.write("%d\n" % len(idx))
                for x in idx:
                    fh.write("%d\n" % x)
    report(a.name, frames, OUT)                           # C0044 guard: corner blind spots
    with open(os.path.join(OUT, "%s_thresh.txt" % a.name), "w") as fh:
        fh.write("%d\n" % thr)                      # the bench runners read this for i1
    print("%s (real weights): %d samples, in rate %.4f, out rate %.4f, |V|max %d, THRESHOLD=%d"
          % (a.name, B, frames.mean(), S.mean(), np.abs(V).max(), thr))
    print("NOTE: run the engines with THRESH=%d." % thr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
