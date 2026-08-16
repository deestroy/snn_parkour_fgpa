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

import torch
from torch.utils.data import DataLoader, Subset

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.path.join(REPO, "data")
CACHE_DIR = os.path.join(REPO, "data", "cache")

# Mean number of events in a non-zero pixel-timestep, measured over N-MNIST in
# train/01_nmnist_peek.py. The counts arm divides by this so that both arms
# present the same average input magnitude to an untrained network. Without it
# the counts arm would start ~3x denser and we would be measuring input scale,
# not the information difference the experiment is about.
MEAN_NONZERO_COUNT = 3.06

T = 4


def _use_certifi_bundle() -> None:
    if os.environ.get("SSL_CERT_FILE"):
        return
    try:
        import certifi
    except ImportError:
        return
    os.environ["SSL_CERT_FILE"] = certifi.where()


def _split(train: bool, cache: bool):
    import tonic
    import tonic.transforms as transforms

    sensor_size = tonic.datasets.NMNIST.sensor_size
    transform = transforms.Compose([
        transforms.Denoise(filter_time=10000),
        transforms.ToFrame(sensor_size=sensor_size, n_time_bins=T),
    ])
    ds = tonic.datasets.NMNIST(save_to=DATA_DIR, transform=transform,
                               train=train)
    if cache:
        path = os.path.join(CACHE_DIR, "train" if train else "test")
        ds = tonic.DiskCachedDataset(ds, cache_path=path)
    return ds


def build_loaders(batch_size: int = 128, limit: int = 0, cache: bool = True,
                  workers: int = 0):
    """:param limit: if > 0, use only this many samples per split. Keeps smoke
        runs to seconds instead of hours on CPU.
    :return: (train_loader, test_loader), each yielding
        (x, y) with x shaped (T, batch, 2, 34, 34) of raw event counts."""
    import tonic

    _use_certifi_bundle()
    collate = tonic.collation.PadTensors(batch_first=False)  # -> (T, B, ...)

    loaders = []
    for is_train in (True, False):
        ds = _split(is_train, cache)
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
