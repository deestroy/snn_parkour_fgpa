"""N-MNIST loaders, with disk caching and the D0003 encoding switch.

Two things here are worth knowing.

**Caching.** N-MNIST on disk is 60,000 files of raw events. Decoding them and
binning them into frames costs far more than the forward pass does, and doing
it every epoch would mean measuring tonic's speed rather than the network's.
`DiskCachedDataset` writes the binned frames out once; later epochs read those.

**Encoding (docs/decisions.md D0003).** The cache always stores raw event
counts. Binarisation happens on the tensor in the training loop, so a single
cache serves both arms of the experiment.
"""

import os
import sys

import torch
from torch.utils.data import DataLoader, Subset

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from nmnist_raw import DATA_DIR, T, _split, _use_certifi_bundle  # noqa: F401,E402

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# Mean number of events in a non-zero pixel-timestep, measured over N-MNIST in
# train/01_nmnist_peek.py. The counts arm divides by this so that both arms
# present the same average input magnitude to an untrained network. Without it
# the counts arm would start ~3x denser and we would be measuring input scale,
# not the information difference the experiment is about.
MEAN_NONZERO_COUNT = 3.06


class PackedNMNIST(torch.utils.data.Dataset):
    """Reads the flat .npy pair written by train/04_pack_dataset.py.

    Exists so training environments need numpy+torch and nothing else --
    tonic and its heavy dependency tree stay confined to the pack step.
    """

    def __init__(self, split: str):
        pack = os.path.join(DATA_DIR, "packed")
        self.frames = torch.from_numpy(
            __import__("numpy").load(os.path.join(pack, split + "_frames.npy")))
        self.labels = torch.from_numpy(
            __import__("numpy").load(os.path.join(pack, split + "_labels.npy")))

    def __len__(self):
        return self.frames.shape[0]

    def __getitem__(self, i):
        return self.frames[i], int(self.labels[i])


def _packed_available() -> bool:
    pack = os.path.join(DATA_DIR, "packed")
    return all(os.path.exists(os.path.join(pack, f))
               for f in ("train_frames.npy", "train_labels.npy",
                         "test_frames.npy", "test_labels.npy"))


def _collate_packed(batch):
    xs = torch.stack([b[0] for b in batch])          # (B, T, 2, 34, 34)
    ys = torch.tensor([b[1] for b in batch])
    return xs.permute(1, 0, 2, 3, 4).contiguous(), ys  # -> (T, B, ...)


def build_loaders(batch_size: int = 128, limit: int = 0, cache: bool = True,
                  workers: int = 0):
    """:param limit: if > 0, use only this many samples per split. Keeps smoke
        runs to seconds instead of hours on CPU.
    :return: (train_loader, test_loader), each yielding
        (x, y) with x shaped (T, batch, 2, 34, 34) of raw event counts.

    Prefers the packed .npy dataset when present (no tonic needed); falls back
    to tonic + DiskCachedDataset otherwise."""
    if _packed_available():
        make = lambda is_train: PackedNMNIST("train" if is_train else "test")
        collate = _collate_packed
    else:
        import tonic
        _use_certifi_bundle()
        make = lambda is_train: _split(is_train, cache)
        collate = tonic.collation.PadTensors(batch_first=False)  # -> (T, B, ..)

    loaders = []
    for is_train in (True, False):
        ds = make(is_train)
        if limit:
            ds = Subset(ds, range(min(limit, len(ds))))
        loaders.append(DataLoader(ds, batch_size=batch_size,
                                  shuffle=is_train, collate_fn=collate,
                                  num_workers=workers, drop_last=is_train))
    return loaders[0], loaders[1]


def encode(x: torch.Tensor, binarise: bool) -> torch.Tensor:
    """Turn cached event counts into network input. See D0003."""
    x = x.float()
    if binarise:
        return (x > 0).float()
    return x / MEAN_NONZERO_COUNT
