"""Export transposed weights and spike address lists for the event-driven
conv testbench (M6). Imports the mapping functions from golden/eventdriven.py
so exporter, Python engine and (later) Verilog testbench agree by construction.

Run:  python3 sim/export_ed_vectors.py [--layer c1] [--k 1]

Writes sim/vectors/:
    ed_<L>_wt.hex     transposed weights W_T[ic,ky,kx,oc], int8 per line,
                      address = ((ic*3+ky)*3+kx)*C_OUT + oc  (D0018 layout).
                      At K>1 the SAME file is read by K bank ROMs, each taking
                      every K-th entry (oc mod K == bank) -- the split is by
                      address, no separate files needed.
    ed_<L>_spk.txt    per (sample, timestep): one line "count" then that many
                      lines of flat input addresses -- the D0016 address list.
    ed_<L>_s.bin      expected output spikes, flat golden order, per timestep
    ed_<L>_v.hex      expected membranes, int16 hex, same order
"""

import argparse
import os
import sys

import numpy as np

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, REPO)
from golden.eventdriven import GEOM, transpose_weights  # noqa: E402

OUT = os.path.join(REPO, "sim", "vectors")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--layer", default="c1", choices=sorted(GEOM))
    ap.add_argument("--k", type=int, default=1)
    args = ap.parse_args()
    c_in, h_in, w_in, c_out, h_out, w_out, thr, wkey = GEOM[args.layer]
    assert c_out % args.k == 0

    w = np.load(os.path.join(REPO, "golden", "m1_weights_int8.npz"))[wkey]
    z = np.load(os.path.join(REPO, "golden", "traces_m1.npz"))
    src = {"c1": "in", "c2": "c1_S", "c3": "c2_S"}[args.layer]
    spikes_in = (z[src] != 0)
    exp_s = (z[args.layer + "_S"] != 0)
    exp_v = z[args.layer + "_V"]
    b, t = spikes_in.shape[:2]

    os.makedirs(OUT, exist_ok=True)
    p = lambda n: os.path.join(OUT, "ed_%s_%s" % (args.layer, n))

    wt = transpose_weights(w)  # (C_IN, 3, 3, C_OUT)
    with open(p("wt.hex"), "w") as fh:
        for v in wt.ravel():
            fh.write("%02x\n" % (int(v) & 0xFF))

    n_spk = 0
    with open(p("spk.txt"), "w") as fh:
        for s in range(b):
            for ts in range(t):
                addrs = np.flatnonzero(spikes_in[s, ts].ravel())
                fh.write("%d\n" % len(addrs))
                for a in addrs:
                    fh.write("%d\n" % a)
                n_spk += len(addrs)

    with open(p("s.bin"), "w") as fh:
        for bit in exp_s.astype(np.uint8).ravel():
            fh.write("%d\n" % bit)
    with open(p("v.hex"), "w") as fh:
        for v in exp_v.astype(np.int64).ravel():
            assert -32768 <= v <= 32767
            fh.write("%04x\n" % (int(v) & 0xFFFF))

    print("%s: %d samples x %d ts, %d input spikes total (%.1f/ts), W_T %s"
          % (args.layer, b, t, n_spk, n_spk / (b * t), wt.shape))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
