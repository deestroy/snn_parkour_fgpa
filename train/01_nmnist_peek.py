"""M0, component 2: get N-MNIST loading, and look at it.

Run:  python3 train/01_nmnist_peek.py            # test split, ~200 MB
      python3 train/01_nmnist_peek.py --train    # train split, ~1 GB

N-MNIST is MNIST filmed with an event camera. A sample is not an image, it is a
list of events (x, y, timestamp, polarity) -- polarity being +1 "pixel got
brighter" / -1 "pixel got darker", which is why the network has 2 input
channels. tonic's ToFrame transform bins those events into T frames of event
counts, shape (T, 2, 34, 34), which is the form the network eats.

The check this script performs is not "did it download". It is: what fraction
of input pixels are non-zero per timestep? That number is the firing rate of
the input layer, and the firing rate is the independent variable of the whole
thesis. If it is not sparse, the event-driven design has nothing to exploit and
we want to know on day one.
"""

import argparse
import os
import sys

import numpy as np

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.path.join(REPO, "data")
OUT_DIR = os.path.join(REPO, "experiments")

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from nmnist_raw import T, _split, _use_certifi_bundle  # noqa: E402


def build_dataset(train: bool):
    # Transform details (Denoise + ToFrame) live in nmnist_raw._split so that
    # the peek, the trainer's fallback path and the pack step can never drift
    # apart. Denoise drops isolated thermal-noise events; leaving them in
    # would inflate the sparsity number this script measures.
    import tonic
    return _split(train, cache=False), tonic.datasets.NMNIST.sensor_size


def measure_sparsity(ds, n_samples: int):
    """Fraction of the (T, 2, 34, 34) input tensor that is non-zero."""
    fracs, counts, labels = [], [], []
    for i in range(min(n_samples, len(ds))):
        frames, label = ds[i]
        frames = np.asarray(frames)
        fracs.append(float((frames != 0).mean()))
        counts.append(int(frames.sum()))
        labels.append(int(label))
    return np.array(fracs), np.array(counts), labels, frames


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--train", action="store_true",
                    help="use the train split (~1 GB) instead of test")
    ap.add_argument("--n", type=int, default=64,
                    help="how many samples to measure sparsity over")
    args = ap.parse_args()

    try:
        import tonic  # noqa: F401
    except ImportError:
        print("tonic is not installed.  python3 -m pip install tonic")
        return 1

    _use_certifi_bundle()

    split = "train" if args.train else "test"
    print("loading N-MNIST [%s] into %s" % (split, os.path.relpath(DATA_DIR, REPO)))
    print("(first run downloads; this takes a while and is cached)\n")

    ds, sensor_size = build_dataset(args.train)
    print("samples        : %d" % len(ds))
    print("sensor size    : %s  (H, W, polarity channels)" % (sensor_size,))

    fracs, counts, labels, last = measure_sparsity(ds, args.n)
    print("frame tensor   : %s  (T, channels, H, W)" % (last.shape,))
    print("dtype          : %s" % last.dtype)

    print("\n--- input layer activity over %d samples ---" % len(fracs))
    print("non-zero input pixels : %.2f%% mean  (min %.2f%%, max %.2f%%)"
          % (100 * fracs.mean(), 100 * fracs.min(), 100 * fracs.max()))
    print("events per sample     : %d mean" % counts.mean())
    print("input tensor size     : %d values (T=%d)" % (last.size, T))

    _save_plot(last, labels[-1])

    if fracs.mean() > 0.5:
        print("\nWARNING: input is dense. Re-check the transform before"
              " drawing any conclusion about event-driven hardware.")
    print("\nPASS: N-MNIST loads and yields (T, 2, 34, 34) frame tensors.")
    return 0


def _save_plot(frames, label) -> None:
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    os.makedirs(OUT_DIR, exist_ok=True)
    fig, ax = plt.subplots(2, T, figsize=(2.0 * T, 4.4))
    for t in range(T):
        for c in range(2):
            ax[c][t].imshow(frames[t, c], cmap="gray")
            ax[c][t].set_xticks([]); ax[c][t].set_yticks([])
            if c == 0:
                ax[c][t].set_title("t=%d" % t, fontsize=10)
        ax[0][0].set_ylabel("ON\n(brighter)", fontsize=9)
        ax[1][0].set_ylabel("OFF\n(darker)", fontsize=9)
    fig.suptitle("N-MNIST sample, label=%d, binned into T=%d timesteps"
                 % (label, T))
    fig.tight_layout()
    path = os.path.join(OUT_DIR, "m0_nmnist_sample.png")
    fig.savefig(path, dpi=120)
    print("plot saved -> %s" % os.path.relpath(path, REPO))


if __name__ == "__main__":
    raise SystemExit(main())
