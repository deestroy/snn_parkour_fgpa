"""Export weights + golden traces for the dense conv-layer testbench.

Run:  python3 sim/export_conv_vectors.py [--layer c1]

Writes, per layer (default c1), into sim/vectors/:

    conv_<L>_w.hex    weight ROM image: one int8 (2 hex digits, two's
                      complement) per line, address = ((oc*C_IN+ic)*3+ky)*3+kx
    conv_<L>_in.bin   input spike bits, one per line, address =
                      (((sample*T+t)*C_IN+ic)*H_IN+iy)*W_IN+ix
    conv_<L>_s.bin    expected output spikes, same layout over out dims
    conv_<L>_v.hex    expected membranes, int16 hex, same layout as _s

The address formulas here and the counter nesting in conv_layer.v must agree
exactly -- that agreement is part of what the testbench verifies.
"""

import argparse
import os

import numpy as np

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(REPO, "sim", "vectors")

SHAPES = {  # layer: (weights key, C_IN, H_IN, W_IN, C_OUT, H_OUT, W_OUT)
    "c1": ("conv1", 2, 34, 34, 16, 17, 17),
    "c2": ("conv2", 16, 17, 17, 32, 9, 9),
    "c3": ("conv3", 32, 9, 9, 64, 5, 5),
}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--layer", default="c1", choices=sorted(SHAPES))
    args = ap.parse_args()
    wkey, c_in, h_in, w_in, c_out, h_out, w_out = SHAPES[args.layer]

    weights = np.load(os.path.join(REPO, "golden", "m1_weights_int8.npz"))[wkey]
    traces = np.load(os.path.join(REPO, "golden", "traces_m1.npz"))

    # Input spikes: for c1 the binarised frames; for c2/c3 the previous
    # layer's spike trace. Output: this layer's spike + membrane traces.
    src = {"c1": "in", "c2": "c1_S", "c3": "c2_S"}[args.layer]
    spikes_in = traces[src]              # (B, T, C_IN, H_IN, W_IN), 0/1
    exp_s = traces[args.layer + "_S"]    # (B, T, C_OUT, H_OUT, W_OUT)
    exp_v = traces[args.layer + "_V"]    # same, int32

    assert spikes_in.shape[2:] == (c_in, h_in, w_in), spikes_in.shape
    assert exp_s.shape[2:] == (c_out, h_out, w_out), exp_s.shape

    os.makedirs(OUT, exist_ok=True)
    p = lambda n: os.path.join(OUT, "conv_%s_%s" % (args.layer, n))

    with open(p("w.hex"), "w") as fh:
        for w in weights.ravel():  # (oc, ic, ky, kx) C-order = the formula
            fh.write("%02x\n" % (int(w) & 0xFF))

    with open(p("in.bin"), "w") as fh:
        for bit in (spikes_in != 0).astype(np.uint8).ravel():
            fh.write("%d\n" % bit)

    with open(p("s.bin"), "w") as fh:
        for bit in (exp_s != 0).astype(np.uint8).ravel():
            fh.write("%d\n" % bit)

    with open(p("v.hex"), "w") as fh:
        for v in exp_v.astype(np.int64).ravel():
            assert -32768 <= v <= 32767
            fh.write("%04x\n" % (int(v) & 0xFFFF))

    b, t = spikes_in.shape[:2]
    print("%s: %d samples x %d timesteps  in=%d bits/ts  out=%d neurons"
          % (args.layer, b, t, c_in * h_in * w_in, c_out * h_out * w_out))
    print("wrote %s_{w.hex,in.bin,s.bin,v.hex}" % p("")[:-1])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
