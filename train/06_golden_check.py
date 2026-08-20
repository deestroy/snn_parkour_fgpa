"""M1, component 3's check: does the golden model hold accuracy, and do the
membranes fit in 16 bits?

Run:  python3 train/06_golden_check.py            # full 10k test set
      python3 train/06_golden_check.py --limit 1000

Three outputs:

1. Accuracy of the all-integer network on the N-MNIST test set, next to the
   float baseline. The M1 gate is a drop of about 1 pp or less.
2. The observed membrane range per layer, as "bits needed". The project brief budgets
   16 bits of membrane state per neuron; this is where that claim gets checked
   against data instead of assumed.
3. Per-layer spike/membrane/current traces for 16 SEEDED-RANDOM test
   samples spanning the classes (C0039; was: the first 16 = all digit 0),
   written to golden/traces_m1.npz. These are the waveforms every HDL
   testbench from M2 onward replays and compares against. Not committed to
   git: integer arithmetic is deterministic, so they regenerate exactly from
   the committed weights and the packed dataset.
"""

import argparse
import os
import sys

import numpy as np
import torch

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from golden.network import GoldenNetwork  # noqa: E402

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TRACES = os.path.join(REPO, "golden", "traces_m1.npz")
N_TRACE_SAMPLES = 16
TRACE_SEED = 20260820   # C0039: seeded random draw across ALL classes --
                        # N-MNIST is class-ordered (D0009), so "the first
                        # 16" were all digit 0. Fixed seed = reproducible.


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--ckpt", default=os.path.join(
        REPO, "train", "checkpoints", "m1_beta0875_seed0.pt"))
    args = ap.parse_args()

    frames = np.load(os.path.join(REPO, "data", "packed", "test_frames.npy"))
    labels = np.load(os.path.join(REPO, "data", "packed", "test_labels.npy"))
    if args.limit:
        frames, labels = frames[:args.limit], labels[:args.limit]

    ckpt = torch.load(args.ckpt, map_location="cpu")
    readout_w = ckpt["state_dict"]["readout.weight"].numpy()
    float_acc = float(ckpt["test_accuracy"])

    net = GoldenNetwork(readout_w=readout_w)
    print("golden model over %d test samples (integer datapath, float readout)"
          % len(labels))

    hits = 0
    batch = 500
    for i in range(0, len(labels), batch):
        pred = net.classify(frames[i:i + batch])
        hits += int((pred == labels[i:i + batch]).sum())
        print("  %5d/%d  acc so far %.2f%%"
              % (min(i + batch, len(labels)), len(labels),
                 100.0 * hits / min(i + batch, len(labels))), flush=True)
    acc = hits / len(labels)

    print("\nfloat model   : %.2f%%" % (100 * float_acc))
    print("golden integer: %.2f%%" % (100 * acc))
    print("drop          : %.2f pp   (M1 gate: ~1 pp)"
          % (100 * (float_acc - acc)))

    print("\nmembrane ranges over the run (hardware budget: int16, +-32767):")
    ok16 = True
    for name, (lo, hi) in net.v_extremes.items():
        bits = int(np.ceil(np.log2(max(hi, -lo, 1) + 1))) + 1
        fits = -32768 <= lo and hi <= 32767
        ok16 &= fits
        print("  %-3s V in [%7d, %6d]  -> %2d bits  %s"
              % (name, lo, hi, bits, "fits int16" if fits else "DOES NOT FIT"))

    rng = __import__("numpy").random.default_rng(TRACE_SEED)
    pick = __import__("numpy").sort(rng.choice(len(frames), N_TRACE_SAMPLES, replace=False))
    print("\ntrace samples (C0039, seed %d): idx %s labels %s"
          % (TRACE_SEED, pick.tolist(), labels[pick].tolist()))
    counts, trace = net.forward(frames[pick], record=True)
    packed = {k: np.stack(v, axis=1) for k, v in trace.items()}  # (B, T, ...)
    packed["fc_counts"] = counts
    packed["labels"] = labels[pick]
    np.savez_compressed(TRACES, **packed)
    sz = os.path.getsize(TRACES) / 1e6
    print("\ntraces for %d samples -> %s  (%.1f MB)"
          % (N_TRACE_SAMPLES, os.path.relpath(TRACES, REPO), sz))

    gate = (float_acc - acc) <= 0.015 and ok16
    print("\n%s" % ("PASS: golden model holds accuracy and fits the membrane"
                    " budget." if gate else "FAIL: see above."))
    return 0 if gate else 1


if __name__ == "__main__":
    raise SystemExit(main())
