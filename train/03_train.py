"""M0, component 4: train the network and log per-layer firing rates.

Run:  python3 train/03_train.py --limit 512 --epochs 1     # smoke test
      python3 train/03_train.py --epochs 10                # real run
      python3 train/03_train.py --epochs 10 --counts       # D0003 other arm

How an SNN is trained. A spike is a step function: its derivative is zero
everywhere except at the threshold, where it is infinite. Backpropagation
through that gives nothing. snnTorch substitutes a smooth curve (arctan) for
the step during the BACKWARD pass only -- a "surrogate gradient". The forward
pass stays a hard 1-bit spike, which is what the hardware implements. Only the
gradient is approximated.

What this script is actually for. Accuracy here is a sanity check, not a
result: N-MNIST is easy and the number will look fine either way. The output
that matters is the per-layer firing rate, logged every epoch to CSV, because
firing rate is the independent variable of the whole thesis and we need to know
what range a trained network actually occupies before designing hardware for it.
"""

import argparse
import csv
import os
import sys
import time

import torch
import torch.nn as nn

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from data import build_loaders, encode  # noqa: E402
from model import ConvSNN, T_DEFAULT  # noqa: E402

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT_DIR = os.path.join(REPO, "experiments")
LAYERS = ("c1", "c2", "c3", "fc")


def run_epoch(net, loader, binarise, optimiser=None):
    """One pass over a loader. Returns (loss, accuracy, {layer: firing rate}).
    Pass optimiser=None to evaluate without updating weights."""
    training = optimiser is not None
    net.train() if training else net.eval()
    criterion = nn.CrossEntropyLoss()
    device = next(net.parameters()).device

    tot_loss = tot_correct = tot_n = 0
    rate_sums = {k: 0.0 for k in LAYERS}
    n_batches = 0

    for x, y in loader:
        x, y = x.to(device), y.to(device)
        x = encode(x, binarise)
        with torch.set_grad_enabled(training):
            logits, rates = net(x)
            loss = criterion(logits, y)
        if training:
            optimiser.zero_grad()
            loss.backward()
            optimiser.step()

        tot_loss += float(loss) * y.numel()
        tot_correct += int((logits.argmax(1) == y).sum())
        tot_n += y.numel()
        for k in LAYERS:
            rate_sums[k] += float(rates[k])
        n_batches += 1

    return (tot_loss / max(tot_n, 1),
            tot_correct / max(tot_n, 1),
            {k: v / max(n_batches, 1) for k, v in rate_sums.items()})


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--epochs", type=int, default=10)
    ap.add_argument("--batch", type=int, default=128)
    ap.add_argument("--lr", type=float, default=2e-3)
    ap.add_argument("--limit", type=int, default=0,
                    help="samples per split; 0 = all. Use a few hundred for a"
                         " smoke test -- full N-MNIST on CPU is slow.")
    ap.add_argument("--counts", action="store_true",
                    help="feed raw event counts instead of binarised spikes"
                         " (the other arm of docs/decisions.md D0003)")
    ap.add_argument("--workers", type=int, default=0)
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--device", default="auto",
                    help="cpu, cuda, or auto (cuda covers ROCm too)")
    args = ap.parse_args()

    if args.device == "auto":
        args.device = "cuda" if torch.cuda.is_available() else "cpu"

    binarise = not args.counts
    tag = "binarised" if binarise else "counts"
    torch.manual_seed(args.seed)

    print("encoding : %s   (D0003)" % tag)
    print("loading N-MNIST (first epoch also builds the frame cache)...")
    train_loader, test_loader = build_loaders(batch_size=args.batch,
                                              limit=args.limit,
                                              workers=args.workers)
    net = ConvSNN(in_shape=(2, 34, 34), n_classes=10,
                  n_steps=T_DEFAULT).to(args.device)
    optimiser = torch.optim.Adam(net.parameters(), lr=args.lr)
    print("device: %s   train batches: %d   test batches: %d\n"
          % (args.device, len(train_loader), len(test_loader)))

    os.makedirs(OUT_DIR, exist_ok=True)
    csv_path = os.path.join(OUT_DIR, "m0_firing_rates_%s.csv" % tag)
    history = []

    with open(csv_path, "w", newline="") as fh:
        writer = csv.writer(fh)
        writer.writerow(["epoch", "split", "loss", "accuracy"] + list(LAYERS))

        for epoch in range(1, args.epochs + 1):
            t0 = time.time()
            tr_loss, tr_acc, tr_rates = run_epoch(net, train_loader, binarise,
                                                  optimiser)
            te_loss, te_acc, te_rates = run_epoch(net, test_loader, binarise)
            dt = time.time() - t0

            writer.writerow(["%d" % epoch, "train", "%.4f" % tr_loss,
                             "%.4f" % tr_acc]
                            + ["%.5f" % tr_rates[k] for k in LAYERS])
            writer.writerow(["%d" % epoch, "test", "%.4f" % te_loss,
                             "%.4f" % te_acc]
                            + ["%.5f" % te_rates[k] for k in LAYERS])
            fh.flush()
            history.append((epoch, te_acc, te_rates))

            print("epoch %2d  %5.1fs  train acc %.3f  test acc %.3f  |  "
                  "rates %s"
                  % (epoch, dt, tr_acc, te_acc,
                     "  ".join("%s=%.3f" % (k, te_rates[k]) for k in LAYERS)))

            if all(te_rates[k] == 0.0 for k in LAYERS):
                print("\nFAIL: network went completely silent. Training cannot"
                      " recover from this; see docs/decisions.md D0005.")
                return 1

    print("\nper-epoch log -> %s" % os.path.relpath(csv_path, REPO))
    _save_plot(history, tag)

    final = history[-1][2]
    print("\n--- final per-layer firing rates (%s) ---" % tag)
    for k in LAYERS:
        print("  %-3s %6.2f%% of neurons fire per timestep" % (k, 100 * final[k]))
    print("\nfinal test accuracy: %.2f%%" % (100 * history[-1][1]))
    print("\nThis is a measurement, not a target. Do not tune it.")
    return 0


def _save_plot(history, tag) -> None:
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    epochs = [h[0] for h in history]
    fig, ax = plt.subplots(1, 2, figsize=(10, 4))
    for k in LAYERS:
        ax[0].plot(epochs, [100 * h[2][k] for h in history], marker="o", label=k)
    ax[0].set_xlabel("epoch"); ax[0].set_ylabel("neurons firing per timestep (%)")
    ax[0].set_title("Per-layer firing rate (%s)" % tag)
    ax[0].legend(); ax[0].grid(alpha=0.3)

    ax[1].plot(epochs, [100 * h[1] for h in history], marker="o", color="k")
    ax[1].set_xlabel("epoch"); ax[1].set_ylabel("test accuracy (%)")
    ax[1].set_title("Accuracy"); ax[1].grid(alpha=0.3)

    fig.tight_layout()
    path = os.path.join(OUT_DIR, "m0_firing_rates_%s.png" % tag)
    fig.savefig(path, dpi=120)
    print("plot -> %s" % os.path.relpath(path, REPO))


if __name__ == "__main__":
    raise SystemExit(main())
