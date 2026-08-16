"""Raw N-MNIST access via tonic. No torch import, on purpose.

This module is the only place tonic is used, and it must stay importable in an
environment that has neither torch nor a GPU: the dataset pack step
(train/04_pack_dataset.py) runs in a minimal venv on machines where installing
tonic's dependency tree alongside an existing torch would cause conflicts.
"""

import os

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.path.join(REPO, "data")
CACHE_DIR = os.path.join(REPO, "data", "cache")

T = 4  # timesteps -- the project default from the project brief


def _use_certifi_bundle() -> None:
    """Point Python at certifi's CA bundle if nothing else is configured.

    macOS python.org framework builds ship without linked CA certificates, so
    the dataset download fails with CERTIFICATE_VERIFY_FAILED. This still
    verifies certificates -- certifi is the Mozilla root store -- it just tells
    OpenSSL where the roots are.
    """
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
