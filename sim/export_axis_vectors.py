"""Export packed 32-bit word streams for the AXIS wrapper testbench.

Run:  python3 sim/export_axis_vectors.py [--layer c1]

Packing is LSB-first: flat bit index = word*32 + bit, so bit 0 of the first
word is flat address 0. This line must agree with axis_conv.v and with
host/conv_test.py; the testbench exists to prove that it does.

Writes sim/vectors/axis_<L>_in.hex  (nsamples*T*WORDS_IN words)
       sim/vectors/axis_<L>_out.hex (nsamples*T*WORDS_OUT words)
"""

import argparse
import os

import numpy as np

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(REPO, "sim", "vectors")

SRC = {"c1": ("in", "c1_S"), "c2": ("c1_S", "c2_S"), "c3": ("c2_S", "c3_S")}


def pack_words(bits: np.ndarray) -> np.ndarray:
    """(N,) 0/1 -> (ceil(N/32),) uint32, LSB-first."""
    n_words = (len(bits) + 31) // 32
    padded = np.zeros(n_words * 32, dtype=np.uint8)
    padded[:len(bits)] = bits
    b = np.packbits(padded.reshape(-1, 4, 8), axis=-1, bitorder="little")
    return b.reshape(-1, 4).astype(np.uint32) @ (256 ** np.arange(4)).astype(np.uint32)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--layer", default="c1", choices=sorted(SRC))
    args = ap.parse_args()
    in_key, out_key = SRC[args.layer]

    z = np.load(os.path.join(REPO, "golden", "traces_m1.npz"))
    spikes_in = (z[in_key] != 0).astype(np.uint8)   # (B, T, C, H, W)
    spikes_out = (z[out_key] != 0).astype(np.uint8)
    b, t = spikes_in.shape[:2]

    with open(os.path.join(OUT, "axis_%s_in.hex" % args.layer), "w") as fh:
        for s in range(b):
            for ts in range(t):
                for w in pack_words(spikes_in[s, ts].ravel()):
                    fh.write("%08x\n" % w)

    with open(os.path.join(OUT, "axis_%s_out.hex" % args.layer), "w") as fh:
        for s in range(b):
            for ts in range(t):
                for w in pack_words(spikes_out[s, ts].ravel()):
                    fh.write("%08x\n" % w)

    wi = (spikes_in[0, 0].size + 31) // 32
    wo = (spikes_out[0, 0].size + 31) // 32
    print("%s: %d samples x %d ts, %d words in / %d words out per ts"
          % (args.layer, b, t, wi, wo))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
