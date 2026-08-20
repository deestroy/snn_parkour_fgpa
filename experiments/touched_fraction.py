"""C0031: what fraction of neurons receive ANY input per timestep, and what
fraction hold nonzero membrane after the update — per layer, full test
split (D0009: never a class-ordered subset). This settles C0006 (the sweep
skip) with data: a skip saves work only on untouched neurons whose V has
also decayed to zero.

Run:  python3 experiments/touched_fraction.py --data data/packed/test_frames.npy
Writes experiments/touched_fraction.md
"""
import argparse
import os
import sys

import numpy as np

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, REPO)
from golden.network import GoldenNetwork  # noqa: E402

LAYERS = ["c1", "c2", "c3", "fc"]


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--data", default=os.path.join(REPO, "data", "packed", "test_frames.npy"))
    ap.add_argument("--batch", type=int, default=256)
    ap.add_argument("--limit", type=int, default=0, help="0 = full split (the rule)")
    a = ap.parse_args()
    frames = np.load(a.data, mmap_mode="r")
    n = frames.shape[0] if not a.limit else min(a.limit, frames.shape[0])
    g = GoldenNetwork()
    touched = {L: 0.0 for L in LAYERS}   # sum of frac(I != 0) over (sample,t)
    alive = {L: 0.0 for L in LAYERS}     # sum of frac(V != 0) after update
    spik = {L: 0.0 for L in LAYERS}
    cnt = 0
    for i in range(0, n, a.batch):
        b = np.asarray(frames[i:i + a.batch]) != 0
        _, tr = g.forward(b.astype(np.uint8), record=True)
        T = len(tr["c1_I"])
        for L in LAYERS:
            for t in range(T):
                I = tr[L + "_I"][t]; V = tr[L + "_V"][t]; S = tr[L + "_S"][t]
                touched[L] += float((I != 0).mean()) * len(b)
                alive[L] += float((V != 0).mean()) * len(b)
                spik[L] += float((S != 0).mean()) * len(b)
        cnt += len(b) * T
        print("  %d/%d" % (min(i + a.batch, n), n), flush=True)
    lines = ["# C0031 — touched-neuron fraction, full test split (%d samples x %d timesteps)\n" % (n, T),
             "| layer | frac neurons with I != 0 (touched) | frac V != 0 after update | firing rate |",
             "|---|---|---|---|"]
    for L in LAYERS:
        lines.append("| %s | %.4f | %.4f | %.4f |" % (L, touched[L] / cnt * T / T / (n * T) * (n * T),  # keep simple below
                                                      0, 0))
    # simpler, correct accounting:
    lines = ["# C0031 — touched-neuron fraction, full test split (%d samples, T=%d)\n" % (n, T),
             "Skippable in the sweep = neurons with I == 0 AND V == 0: at most",
             "(1 - max(touched, alive)) of the sweep, per layer.\n",
             "| layer | touched (I != 0) | alive (V != 0) | firing rate | sweep skippable (upper bound) |",
             "|---|---|---|---|---|"]
    denom = n * T
    for L in LAYERS:
        to, al, sp = touched[L] / denom, alive[L] / denom, spik[L] / denom
        lines.append("| %s | %.4f | %.4f | %.4f | %.4f |" % (L, to, al, sp, 1 - max(to, al)))
    out = "\n".join(lines) + "\n"
    open(os.path.join(REPO, "experiments", "touched_fraction.md"), "w").write(out)
    print(out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
