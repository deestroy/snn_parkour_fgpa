"""M7 rehearsal, simulation side: synthetic C1 inputs at a chosen spike
density, golden outputs to match, in the AXIS testbench's word format.

The event-driven engine's cost scales with INPUT spikes to the layer (the
scatter) plus a fixed sweep; the dense engine's cost is constant. C1's input
is the data itself (binarised N-MNIST), so to sweep C1's input activity we
generate Bernoulli(p) input frames and let the golden model produce the
matching outputs. Both engines are then run on identical streams and their
cycles compared -- a predicted latency crossover, before any meter.

Run:  python3 sim/export_axis_sweep.py --density 0.10 --out-prefix sim/vectors/sweep_p010
Writes <prefix>_in.hex, <prefix>_out.hex (16 samples x T=4), prints the
realised input and output firing rates.
"""

import argparse
import os
import sys

import numpy as np

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, REPO)
sys.path.insert(0, os.path.join(REPO, "sim"))
from golden.network import GoldenNetwork          # noqa: E402
from export_axis_vectors import pack_words        # noqa: E402

T, C_IN, H_IN, W_IN = 4, 2, 34, 34


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--density", type=float, required=True, help="P(input bit = 1)")
    ap.add_argument("--samples", type=int, default=16)
    ap.add_argument("--seed", type=int, default=1)
    ap.add_argument("--out-prefix", required=True)
    a = ap.parse_args()
    rng = np.random.default_rng(a.seed)
    frames = (rng.random((a.samples, T, C_IN, H_IN, W_IN)) < a.density).astype(np.uint8)
    # N-MNIST frames are zero-padded by 1 on each side (34x34 for a 32x32
    # sensor); keep that so the geometry matches the trained layer exactly
    frames[:, :, :, 0, :] = 0; frames[:, :, :, -1, :] = 0
    frames[:, :, :, :, 0] = 0; frames[:, :, :, :, -1] = 0
    g = GoldenNetwork()
    _, trace = g.forward(frames, record=True)
    c1 = np.stack([trace["c1_S"][t] for t in range(T)], axis=1)   # (B,T,Co,Ho,Wo)
    with open(a.out_prefix + "_in.hex", "w") as fi, open(a.out_prefix + "_out.hex", "w") as fo:
        for s in range(a.samples):
            for t in range(T):
                for w in pack_words(frames[s, t].ravel()): fi.write("%08x\n" % w)
                for w in pack_words(c1[s, t].ravel().astype(np.uint8)): fo.write("%08x\n" % w)
    print("density %.4f: input rate %.4f (%.0f spikes/sample), C1 output rate %.4f"
          % (a.density, frames.mean(), frames.sum() / a.samples, c1.mean()))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
