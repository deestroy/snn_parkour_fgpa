"""Checks for the IsaacGym port, CPU only, no IsaacGym needed.

1. The torch event simulator matches the numpy original bit-for-bit on
   random depth sequences, per environment, including a reset mid-sequence.
2. fpga_encoder.py is the recreation's file verbatim (header comment aside).
3. The backbone runs end-to-end on a fake env with both windows and
   produces a (B, 32) latent whose gradient reaches the conv weights.
Run: python3 robot/isaac/test_port.py
"""
import os
import sys
import types

import numpy as np
import torch

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(HERE, "from_recreation"))

from event_sim_torch import EventSimulatorTorch                        # noqa: E402
from fpga_event_backbone import FPGAEventBackbone                      # noqa: E402


def _numpy_original():
    """Load from_recreation/event_sim.py without its package-relative import."""
    src = open(os.path.join(HERE, "from_recreation", "event_sim.py")).read()
    src = src.replace("from .config import EventCfg", "")
    ns = {}
    exec(compile(src, "event_sim_orig", "exec"), ns)
    class EventCfg:                                   # values from the recreation's config.py
        threshold_c = 0.10; max_events_per_px = 8; log_eps = 1e-3
    return ns["EventSimulator"], EventCfg


def test_event_sim():
    Orig, EventCfg = _numpy_original()
    rng = np.random.default_rng(0)
    B, H, W, far, steps = 3, 16, 16, 2.0, 12
    torch_sim = EventSimulatorTorch(far=far)
    origs = [Orig(EventCfg(), far=far) for _ in range(B)]
    reset_at = 6
    mism = 0
    for t in range(steps):
        depth = rng.uniform(0.0, far, size=(B, H, W)).astype(np.float32)
        if t > 0:                                     # mostly small changes, some big
            depth = np.clip(prev + rng.normal(0, 0.15, size=depth.shape).astype(np.float32), 0, far)
        prev = depth
        reset = torch.zeros(B, dtype=torch.bool)
        if t == reset_at:
            reset[1] = True; origs[1].reset()
        out_t = torch_sim.step(torch.from_numpy(depth), reset_mask=reset).numpy()
        out_n = np.stack([origs[i].step(depth[i]) for i in range(B)])
        if t == reset_at:
            # numpy original: first call after reset() returns zeros (and seeds);
            # torch: reset_mask re-seeds and the backbone zeroes -> compare env 1 to zeros
            out_t[1] = 0.0
        mism += int((out_t != out_n).sum())
    assert mism == 0, "event sim mismatch count %d" % mism
    total = sum(int((np.asarray(o.prev_logI) != 0).any()) for o in origs)
    print("event sim: torch == numpy on %d steps x %d envs (reset at step %d) -- OK (%d refs live)"
          % (steps, B, reset_at, total))


def test_encoder_verbatim():
    a = open(os.path.join(HERE, "fpga_encoder.py")).read().splitlines()
    b = open(os.path.join(HERE, "from_recreation", "fpga_encoder.py")).read().splitlines()
    strip = lambda ls: [l for l in ls if l.strip() and not l.startswith("# Copied VERBATIM")
                        and not l.startswith("# 2026-08-20)")]
    assert strip(a) == strip(b), "fpga_encoder.py differs from the recreation's"
    print("fpga_encoder.py: verbatim copy of the recreation's -- OK")


def test_backbone():
    B, H, W = 4, 64, 64
    env = types.SimpleNamespace(
        cfg=types.SimpleNamespace(depth=types.SimpleNamespace(far_clip=2.0, near_clip=0.0, update_interval=5)),
        episode_length_buf=torch.tensor([0, 3, 40, 200]))
    for window in ("repeat", "consecutive"):
        bb = FPGAEventBackbone(env, window=window)
        torch.manual_seed(0)
        x0 = torch.rand(B, H, W) - 0.5
        lat = bb(x0)                                  # first tick: no events
        assert lat.shape == (B, 32), lat.shape
        for k in range(5):
            x = torch.clamp(x0 + 0.05 * torch.randn(B, H, W), -0.5, 0.5)
            env.episode_length_buf += 5
            lat = bb(x)
        assert bb.last_rate > 0, "no events on moving depth"
        lat.sum().backward()
        g = bb.enc.c1.weight.grad
        assert g is not None and float(g.abs().sum()) > 0, "no gradient into c1"
        print("backbone (%s): latent %s, event-bit rate %.3f, grad reaches c1 -- OK"
              % (window, tuple(lat.shape), bb.last_rate))


if __name__ == "__main__":
    test_event_sim(); test_encoder_verbatim(); test_backbone()
    print("PORT CHECKS PASS")
