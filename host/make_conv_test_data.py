"""Pack golden C1 traffic into a board-friendly .npz. Runs on the dev Mac.

Run:  python3 host/make_conv_test_data.py              # N-MNIST C1 (DATASET=0)
      python3 host/make_conv_test_data.py --dataset g1 # DVS-Gesture C1 (DATASET=1)

Produces host/conv_test_data.npz containing, for 16 samples:
    tx_words  (16, 292)  uint32 -- 4 timesteps x 73 packed input words
    rx_words  (16, 580)  uint32 -- 4 timesteps x 145 expected output words
    labels    (16,)      the digit labels, for humane error messages

The packing is the same LSB-first rule as axis_conv.v and the sim exporter
(imported from it, so it cannot drift). The board needs numpy and pynq only.
"""

import os
import sys

import numpy as np

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(REPO, "sim"))
from export_axis_vectors import pack_words  # noqa: E402  the ONE packer


def main_g1() -> int:
    """DVS-Gesture C1 (DATASET=1, C0012): the 8 check samples are the word
    streams the baked AXIS harness passed bit-identically on 2026-09-18
    (sim/vectors/axis_g1_*.hex, written by sim/export_axis_vectors.py
    --layer g1 from the first 8 test clips), 1,024 words in / 2,048 out."""
    vec = os.path.join(REPO, "sim", "vectors")
    tx = np.loadtxt(os.path.join(vec, "axis_g1_in.hex"),
                    converters={0: lambda x: int(x, 16)}, dtype=np.int64)
    rx = np.loadtxt(os.path.join(vec, "axis_g1_out.hex"),
                    converters={0: lambda x: int(x, 16)}, dtype=np.int64)
    T, WI, WO = 4, (2 * 64 * 64 + 31) // 32, (16 * 32 * 32 + 31) // 32   # 256 / 512 per timestep
    n = tx.size // (T * WI)
    assert tx.size == n * T * WI and rx.size == n * T * WO, (tx.size, rx.size)
    labels = np.load(os.path.join(REPO, "data", "packed_dvsgesture", "test_labels.npy"))[:n]
    out = os.path.join(REPO, "host", "conv_test_data_g1.npz")
    np.savez_compressed(out, tx_words=tx.reshape(n, T * WI).astype(np.uint32),
                        rx_words=rx.reshape(n, T * WO).astype(np.uint32),
                        labels=labels.astype(np.uint8))
    print("wrote %s: tx %s, rx %s, labels %s" % (os.path.relpath(out, REPO),
                                                 (n, T * WI), (n, T * WO), labels.tolist()))
    return 0


def main() -> int:
    if "--dataset" in sys.argv and sys.argv[sys.argv.index("--dataset") + 1] == "g1":
        return main_g1()
    z = np.load(os.path.join(REPO, "golden", "traces_m1.npz"))
    spikes_in = (z["in"] != 0).astype(np.uint8)     # (16, 4, 2, 34, 34)
    spikes_out = (z["c1_S"] != 0).astype(np.uint8)  # (16, 4, 16, 17, 17)
    b, t = spikes_in.shape[:2]

    tx = np.stack([
        np.concatenate([pack_words(spikes_in[s, ts].ravel())
                        for ts in range(t)])
        for s in range(b)])
    rx = np.stack([
        np.concatenate([pack_words(spikes_out[s, ts].ravel())
                        for ts in range(t)])
        for s in range(b)])

    out = os.path.join(REPO, "host", "conv_test_data.npz")
    np.savez_compressed(out, tx_words=tx.astype(np.uint32),
                        rx_words=rx.astype(np.uint32), labels=z["labels"])
    print("wrote %s: tx %s, rx %s" % (os.path.relpath(out, REPO),
                                      tx.shape, rx.shape))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
