"""Corner-exposure report for a check set (C0044 follow-up).

A check set can be bit-identical and still exercise nothing at a boundary
neuron: the N-MNIST set never put a spike in output neuron 0's receptive
field, which hid the sweep's I[0] bug. This helper counts, for each of the
four output-corner positions of a 3x3 / stride-2 / pad-1 layer, how many
(sample, timestep) frames have at least one input spike inside that
corner's receptive field. Zero at any corner = that set is blind there.

    from sim.corner_exposure import report
    report("c1", frames, out_dir)      # frames (B, T, C, H, W), 0/1

Prints one line and writes ed_<layer>_exposure.txt next to the vectors.
Self-test: python3 sim/corner_exposure.py --selftest
"""
import os
import sys

import numpy as np

CORNERS = ("TL", "TR", "BL", "BR")


def _field(o: int, n_in: int) -> slice:
    """Input index range seen by output index o (k=3, stride 2, pad 1)."""
    return slice(max(2 * o - 1, 0), min(2 * o + 1, n_in - 1) + 1)


def corner_exposure(frames: np.ndarray) -> dict:
    """frames (B, T, C, H, W) binary -> {corner: frames-with-a-spike, "total": B*T}."""
    assert frames.ndim == 5, frames.shape
    b, t, _, h, w = frames.shape
    ho, wo = (h + 1) // 2, (w + 1) // 2
    rows = {"T": _field(0, h), "B": _field(ho - 1, h)}
    cols = {"L": _field(0, w), "R": _field(wo - 1, w)}
    out = {"total": b * t}
    for c in CORNERS:
        sub = frames[:, :, :, rows[c[0]], cols[c[1]]]
        out[c] = int(sub.reshape(b * t, -1).any(axis=1).sum())
    return out


def report(layer: str, frames: np.ndarray, out_dir: str) -> dict:
    e = corner_exposure(frames)
    blind = [c for c in CORNERS if e[c] == 0]
    line = "%s corner exposure (frames with a spike in the corner neuron's field, of %d): %s%s" % (
        layer, e["total"], "  ".join("%s %d" % (c, e[c]) for c in CORNERS),
        ("   BLIND at %s -- a neuron-0-class bug there is invisible to this set" % ",".join(blind))
        if blind else "")
    print(line)
    with open(os.path.join(out_dir, "ed_%s_exposure.txt" % layer), "w") as fh:
        fh.write(line + "\n")
    return e


def _selftest() -> int:
    b, t, c, h, w = 2, 3, 2, 34, 34          # c1 geometry: 17x17 out, BR field = rows/cols 31..33
    f = np.zeros((b, t, c, h, w), np.uint8)
    assert corner_exposure(f) == {"total": 6, "TL": 0, "TR": 0, "BL": 0, "BR": 0}
    f[0, 0, 1, 1, 0] = 1                       # inside TL (rows 0-1, cols 0-1), one frame
    f[1, 2, 0, 33, 31] = 1                     # inside BR (rows 31-33, cols 31-33)
    f[1, 2, 0, 0, 33] = 1                      # TR, same frame as the BR hit
    f[0, 1, 0, 2, 0] = 1                       # row 2 is outside TL (field is rows 0-1): no hit
    e = corner_exposure(f)
    assert e == {"total": 6, "TL": 1, "TR": 1, "BL": 0, "BR": 1}, e
    # 64x64 -> 32x32 out: BR field is rows/cols 61..63, TL rows/cols 0..1
    g = np.zeros((1, 1, 2, 64, 64), np.uint8); g[0, 0, 0, 61, 63] = 1
    assert corner_exposure(g)["BR"] == 1 and corner_exposure(g)["TR"] == 0
    g[:] = 0; g[0, 0, 0, 60, 63] = 1           # row 60 is outside the BR field
    assert corner_exposure(g)["BR"] == 0
    print("CORNER EXPOSURE SELFTEST PASS")
    return 0


if __name__ == "__main__":
    sys.exit(_selftest() if "--selftest" in sys.argv else 1)
