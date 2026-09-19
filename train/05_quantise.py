"""M1, component 2: quantise the trained weights to int8, power-of-two scales.

Run:  python3 train/05_quantise.py [--ckpt train/checkpoints/m1_beta0875_seed0.pt]

Scheme (docs/decisions.md D0008): each layer stores int8 weights w_q with a
per-layer scale 2^-k, so real_w ~= w_q * 2^-k. k is chosen as the largest
shift such that 127 * 2^-k still covers the layer's largest |weight| --
maximum precision with zero clipping.

Two facts fall out of this scheme and are printed as proof:

- The firing threshold (1.0 in real units) becomes exactly 2^k in integer
  units -- the power-of-two constant D0005 predicted the hardware would want.
- The 2x2 average pool's divide-by-4 folds into the FC layer's scale
  (k_fc_effective = k_fc + 2), so hardware pools by SUM, exactly.

The check: accuracy of the network with rounded-then-restored weights over the
full test set, next to the float baseline. This isolates the damage from
weight rounding alone; membranes stay float here and go fixed-point in the
golden model (component 3).

Output: golden/m1_weights_int8.npz -- int8 arrays + per-layer k + config.
"""

import argparse
import os
import sys

import numpy as np
import torch

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from data import build_loaders, encode  # noqa: E402
from model import ConvSNN  # noqa: E402

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT_PATH = os.path.join(REPO, "golden", "m1_weights_int8.npz")
HW_LAYERS = ("conv1", "conv2", "conv3", "fc")  # readout excluded: not hardware


def choose_k(w: np.ndarray) -> int:
    """Largest k with 127 * 2^-k >= max|w| (no clipping possible)."""
    m = float(np.abs(w).max())
    k = 0
    while 127.0 * 2.0 ** -(k + 1) >= m:
        k += 1
    return k


def quantise_layer(w: np.ndarray, k: int, clip: bool = False):
    """int8 weights at shift k. clip=False: k came from choose_k, nothing can
    clip. clip=True (C0045 --fixed_k): saturate at +-127 and return the
    fraction of weights that were clipped, so a fixed-threshold comparison
    across networks reports what it cost."""
    q = np.round(w * 2.0 ** k)
    if not clip:
        assert np.abs(q).max() <= 127, "clipping despite choose_k"
        return q.astype(np.int8), 0.0
    clipped = float((np.abs(q) > 127).mean())
    return np.clip(q, -127, 127).astype(np.int8), clipped


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--ckpt", default=os.path.join(
        REPO, "train", "checkpoints", "m1_beta0875_seed0.pt"))
    ap.add_argument("--device", default="auto")
    ap.add_argument("--fixed_k", default=None,
                    help="C0045: fixed shifts instead of choose_k, e.g. '6' for all layers or "
                         "'6,6,6,6' per conv1,conv2,conv3,fc; weights beyond +-127 are clipped and the "
                         "clipped fraction is reported and stored as <layer>_clip_frac")
    ap.add_argument("--out", default=OUT_PATH,
                    help="weights .npz to write (default: the N-MNIST golden file)")
    args = ap.parse_args()
    if args.device == "auto":
        args.device = "cuda" if torch.cuda.is_available() else "cpu"

    ckpt = torch.load(args.ckpt, map_location="cpu")
    cfg = ckpt["config"]
    assert cfg["binarise"], "golden model assumes binarised input (D0003)"

    net = ConvSNN(in_shape=tuple(cfg["in_shape"]), n_classes=cfg["n_classes"],
                  beta=cfg["beta"], n_steps=cfg["n_steps"])
    net.load_state_dict(ckpt["state_dict"])
    net.to(args.device).eval()

    print("checkpoint : %s  (trained test acc %.2f%%)"
          % (os.path.relpath(args.ckpt, REPO), 100 * ckpt["test_accuracy"]))

    # --- quantise ---------------------------------------------------------
    packed = {}
    fixed = None
    if args.fixed_k is not None:
        ks = [int(x) for x in args.fixed_k.split(",")]
        fixed = dict(zip(HW_LAYERS, ks * len(HW_LAYERS) if len(ks) == 1 else ks))
        assert len(fixed) == len(HW_LAYERS), "--fixed_k takes 1 or %d values" % len(HW_LAYERS)
        print("\nC0045 fixed shifts: %s (clipping allowed and reported)" % fixed)
    print("\nlayer  max|w|    k   scale     rms rounding err   clipped")
    for name in HW_LAYERS:
        w = getattr(net, name).weight.detach().cpu().numpy()
        k = choose_k(w) if fixed is None else fixed[name]
        q, clip_frac = quantise_layer(w, k, clip=fixed is not None)
        err = w - q.astype(np.float64) * 2.0 ** -k
        packed[name] = q
        packed[name + "_k"] = np.int64(k)
        packed[name + "_clip_frac"] = np.float64(clip_frac)
        print("%-6s %.4f   %2d   2^-%-2d    %.2e   %s"
              % (name, np.abs(w).max(), k, k, np.sqrt((err ** 2).mean()),
                 "--" if fixed is None else "%.3f %%" % (100 * clip_frac)))
        if name == "fc":
            print("       -> pool /4 folds in: FC effective shift k+2 = %d" % (k + 2))
        print("       -> integer threshold for this layer = 2^%d = %d" % (k, 2 ** k))

    # --- check: accuracy with rounded weights, everything else untouched --
    _, test_loader = build_loaders(batch_size=256,
                                   dataset=cfg.get("dataset", "nmnist"), pack_dir=cfg.get("pack_dir", ""))

    def accuracy():
        hits = n = 0
        with torch.no_grad():
            for x, y in test_loader:
                x, y = x.to(args.device), y.to(args.device)
                logits, _ = net(encode(x, binarise=True))
                hits += int((logits.argmax(1) == y).sum())
                n += y.numel()
        return hits / n

    base = accuracy()
    with torch.no_grad():
        for name in HW_LAYERS:
            k = int(packed[name + "_k"])
            deq = torch.from_numpy(
                packed[name].astype(np.float32) * 2.0 ** -k)
            getattr(net, name).weight.copy_(deq.to(args.device))
    quant = accuracy()

    print("\nfloat weights      : %.2f%%" % (100 * base))
    print("int8 weights       : %.2f%%" % (100 * quant))
    print("drop from rounding : %.2f pp   (M1 budget ~1 pp for the full"
          " fixed-point model)" % (100 * (base - quant)))

    np.savez(args.out, **packed,
             beta=cfg["beta"], n_steps=cfg["n_steps"],
             threshold=1.0, in_shape=np.array(cfg["in_shape"]),
             float_acc=base, int8_weight_acc=quant)
    print("\nweights -> %s" % os.path.relpath(args.out, REPO))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
