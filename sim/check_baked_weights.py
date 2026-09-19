"""Provenance check: every baked weight table in hdl/ equals the conv1 of the
TRACKED weight file it claims to come from. Added 2026-09-19 after an
untracked scratch hex (sim/vectors/conv_c1_w.hex) was found holding a
different network's weights and nearly reached a baked file.

    python3 sim/check_baked_weights.py        -> exit 0 iff all four match
"""
import os, re, sys
import numpy as np

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

def table(path, pat):
    return [int(v, 16) for v in re.findall(pat, open(path).read())]

def conv_order(w):   # wrom order: oc, ic, ky, kx
    return [int(w[oc, ic, ky, kx]) & 0xFF for oc in range(w.shape[0]) for ic in range(w.shape[1])
            for ky in range(3) for kx in range(3)]

def scatter_order(w):  # W_T order: ic, ky, kx, oc
    return [int(v) & 0xFF for v in np.ascontiguousarray(w.transpose(1, 2, 3, 0)).ravel()]

def main():
    ok = True
    for name, npz in (("c1", "m1_weights_int8.npz"), ("g1", "dvsgesture_weights_int8.npz")):
        w = np.load(os.path.join(REPO, "golden", npz))["conv1"].astype(int)
        checks = [
            ("hdl/dense/conv_layer_p_%s.v" % name, r"wrom_all\[\d+\] = 8'h([0-9a-f]{2});", conv_order(w)),
            ("hdl/eventdriven/ed_scatter_%s.v" % name, r"wt\[\s*\d+\] = 8'h([0-9a-f]{2});", scatter_order(w)),
        ]
        for rel, pat, want in checks:
            got = table(os.path.join(REPO, rel), pat)
            same = got == want
            ok &= same
            print("%-36s vs golden/%-28s %s (%d entries)" % (rel, npz, "MATCH" if same else "MISMATCH", len(got)))
    print("BAKED WEIGHTS %s" % ("PASS" if ok else "FAIL"))
    return 0 if ok else 1

if __name__ == "__main__":
    sys.exit(main())
