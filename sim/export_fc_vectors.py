"""Export weights + golden traces for the FC-layer testbench.

Run:  python3 sim/export_fc_vectors.py

Writes sim/vectors/:
    fc_w.hex    N_OUT*N_POOL int8 lines, address = n*256 + j where
                j = (c*2 + py)*2 + px  -- numpy C-order of (64, 2, 2),
                which is exactly how golden pooled.reshape(b, -1) orders it
    fc_in.bin   c3 spike bits, address = (c*5 + y)*5 + x per timestep
    fc_s.bin    expected fc spikes (128/timestep)
    fc_v.hex    expected fc membranes (int16)
"""

import os

import numpy as np

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(REPO, "sim", "vectors")


def main() -> int:
    w = np.load(os.path.join(REPO, "golden", "m1_weights_int8.npz"))["fc"]
    z = np.load(os.path.join(REPO, "golden", "traces_m1.npz"))
    assert w.shape == (128, 256), w.shape

    os.makedirs(OUT, exist_ok=True)
    with open(os.path.join(OUT, "fc_w.hex"), "w") as fh:
        for v in w.ravel():
            fh.write("%02x\n" % (int(v) & 0xFF))

    with open(os.path.join(OUT, "fc_in.bin"), "w") as fh:
        for bit in (z["c3_S"] != 0).astype(np.uint8).ravel():
            fh.write("%d\n" % bit)

    with open(os.path.join(OUT, "fc_s.bin"), "w") as fh:
        for bit in (z["fc_S"] != 0).astype(np.uint8).ravel():
            fh.write("%d\n" % bit)

    with open(os.path.join(OUT, "fc_v.hex"), "w") as fh:
        for v in z["fc_V"].astype(np.int64).ravel():
            assert -32768 <= v <= 32767
            fh.write("%04x\n" % (int(v) & 0xFFFF))

    b, t = z["c3_S"].shape[:2]
    print("fc: %d samples x %d ts, %d in bits, 128 neurons"
          % (b, t, z["c3_S"][0, 0].size))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
