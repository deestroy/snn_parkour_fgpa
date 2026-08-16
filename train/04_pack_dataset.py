"""One-time: pack N-MNIST into plain .npy tensors.

Run:  python3 train/04_pack_dataset.py [--split train|test|both]

Why. tonic drags in heavy dependencies (librosa, numba) that we do not want in
every environment that trains -- on the GPU box they would have downgraded
numpy under an unrelated project. Binning events into frames is also pure
preprocessing: it happens once, identically, regardless of where training runs.
So this script is the only place tonic is required. Its output is two flat
arrays per split:

    data/packed/{split}_frames.npy   uint8, (N, T, 2, 34, 34), event counts
    data/packed/{split}_labels.npy   uint8, (N,)

uint8 is lossless here: the measured maximum count per pixel-timestep is 10
(train/01_nmnist_peek.py). The packed pair is ~640 MB for the train split,
loads with a single np.load, and needs nothing but numpy to read.
"""

import argparse
import os
import sys
import time

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from nmnist_raw import _split, _use_certifi_bundle, T  # noqa: E402

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PACK_DIR = os.path.join(REPO, "data", "packed")


def pack(train: bool) -> None:
    split = "train" if train else "test"
    ds = _split(train, cache=False)
    n = len(ds)

    frames = np.zeros((n, T, 2, 34, 34), dtype=np.uint8)
    labels = np.zeros(n, dtype=np.uint8)

    t0 = time.time()
    for i in range(n):
        f, y = ds[i]
        f = np.asarray(f)
        if f.max() > 255:  # would silently wrap in uint8; refuse instead
            raise ValueError("count %d exceeds uint8 at sample %d" % (f.max(), i))
        frames[i] = f
        labels[i] = y
        if i % 5000 == 0:
            print("  %s %6d/%d  (%.0fs)" % (split, i, n, time.time() - t0),
                  flush=True)

    os.makedirs(PACK_DIR, exist_ok=True)
    np.save(os.path.join(PACK_DIR, "%s_frames.npy" % split), frames)
    np.save(os.path.join(PACK_DIR, "%s_labels.npy" % split), labels)
    print("packed %s: %d samples, %.0f MB, %.0fs"
          % (split, n, frames.nbytes / 1e6, time.time() - t0), flush=True)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--split", choices=("train", "test", "both"),
                    default="both")
    args = ap.parse_args()

    _use_certifi_bundle()
    if args.split in ("test", "both"):
        pack(train=False)
    if args.split in ("train", "both"):
        pack(train=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
