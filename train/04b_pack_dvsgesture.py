"""One-time: pack DVS-Gesture into plain .npy tensors (C0012).

Run:  python3 train/04b_pack_dvsgesture.py [--split train|test|both]

Same idea as train/04_pack_dataset.py (N-MNIST): tonic is needed only here;
training reads flat arrays with numpy alone. DVS-Gesture (IBM, 2017) is
11 hand/arm gestures recorded on a 128x128 DVS, ~1,342 recordings of ~6 s,
29 subjects (subjects 1-23 train, 24-29 test -- tonic's split).

Geometry decision: the 128x128 sensor is downsampled 2x to 2x64x64, which
is EXACTLY the robot-era C1 geometry (D0024, `r1`) that both engines are
already verified against bit-identically. So DVS-Gesture on the FPGA costs
parameters and vectors only: C1 2->16 @ 32x32, C2 16->32 @ 16x16,
C3 32->64 @ 8x8, pool -> 1024 -> FC 128 -> readout 11.

Time: T = 4 bins over the whole recording, the project-wide default
(nmnist_raw.T). Coarse for a 6 s gesture, but it is the same T policy as
N-MNIST and the binarised encoding (D0003) only asks "any event in this
pixel-bin?". Counts are clipped to uint8 (255) and the clip fraction is
printed -- irrelevant to the binarised arm, recorded for honesty.

    data/packed_dvsgesture/{split}_frames.npy   uint8, (N, T, 2, 64, 64)
    data/packed_dvsgesture/{split}_labels.npy   uint8, (N,)
"""

import argparse
import os
import sys
import time

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from nmnist_raw import DATA_DIR, T, _use_certifi_bundle  # noqa: E402

PACK_DIR = os.path.join(DATA_DIR, "packed_dvsgesture")
SIDE = 64          # 128 -> 64: the r1 geometry


def _split(train: bool):
    import tonic
    import tonic.transforms as transforms
    sensor = tonic.datasets.DVSGesture.sensor_size          # (128, 128, 2)
    transform = transforms.Compose([
        transforms.Denoise(filter_time=10000),
        transforms.Downsample(spatial_factor=SIDE / sensor[0]),
        transforms.ToFrame(sensor_size=(SIDE, SIDE, 2), n_time_bins=T),
    ])
    return tonic.datasets.DVSGesture(save_to=DATA_DIR, transform=transform,
                                     train=train)


def pack(train: bool) -> None:
    split = "train" if train else "test"
    ds = _split(train)
    n = len(ds)
    frames = np.zeros((n, T, 2, SIDE, SIDE), dtype=np.uint8)
    labels = np.zeros(n, dtype=np.uint8)
    clipped = total = 0
    t0 = time.time()
    for i in range(n):
        f, y = ds[i]
        f = np.asarray(f)
        clipped += int((f > 255).sum()); total += f.size
        frames[i] = np.minimum(f, 255)
        labels[i] = y
        if i % 200 == 0:
            print("  %s %5d/%d  (%.0fs)" % (split, i, n, time.time() - t0),
                  flush=True)
    os.makedirs(PACK_DIR, exist_ok=True)
    np.save(os.path.join(PACK_DIR, "%s_frames.npy" % split), frames)
    np.save(os.path.join(PACK_DIR, "%s_labels.npy" % split), labels)
    nz = (frames > 0).mean()
    print("packed %s: %d samples, %d classes, %.0f MB, input density %.4f, "
          "uint8-clipped %.6f%% of pixel-bins, %.0fs"
          % (split, n, len(np.unique(labels)), frames.nbytes / 1e6, nz,
             100.0 * clipped / max(total, 1), time.time() - t0), flush=True)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--split", choices=("train", "test", "both"), default="both")
    args = ap.parse_args()
    _use_certifi_bundle()
    if args.split in ("test", "both"):
        pack(train=False)
    if args.split in ("train", "both"):
        pack(train=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
