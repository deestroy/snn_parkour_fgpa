"""Batched, GPU-resident port of the recreation's frame-difference event
simulator (robot/isaac/from_recreation/event_sim.py), same arithmetic:

    intensity = 1 - depth / far          (inverse depth: near = bright)
    logI      = log(intensity + eps)
    dL        = logI - ref               (ref = reference log-intensity)
    n         = min(floor(|dL| / C), max_events)      events this tick
    ref      += sign(dL) * n * C         (residual below C carries over)
    frame     = [n if dL > 0, n if dL < 0] / max_events      (2, H, W)

The reference is per environment. `reset_mask` marks environments whose
episode just started: their reference is re-seeded from the current frame
and they emit no events this tick (the numpy original returns zeros on its
first call after reset()). test_port.py checks this file against the numpy
original on random depth sequences, including resets.
"""
import torch


class EventSimulatorTorch:
    def __init__(self, far: float, threshold_c: float = 0.10,
                 max_events_per_px: int = 8, log_eps: float = 1e-3):
        self.far = float(far)
        self.c = float(threshold_c)
        self.max_n = float(max_events_per_px)
        self.eps = float(log_eps)
        self.ref = None                      # (B, H, W) reference log-intensity

    def reset_all(self):
        self.ref = None

    @torch.no_grad()
    def step(self, depth: torch.Tensor, reset_mask: torch.Tensor = None) -> torch.Tensor:
        """depth (B, H, W) metres -> events (B, 2, H, W) float in [0, 1]."""
        logI = torch.log(1.0 - depth / self.far + self.eps)
        if self.ref is None:
            self.ref = logI.clone()
            return torch.zeros(depth.shape[0], 2, *depth.shape[1:], dtype=torch.float32,
                               device=depth.device)
        if reset_mask is not None and bool(reset_mask.any()):
            self.ref[reset_mask] = logI[reset_mask]        # re-seed: no events this tick
        dL = logI - self.ref
        n = torch.clamp(torch.floor(dL.abs() / self.c), max=self.max_n)
        pos = torch.where(dL > 0, n, torch.zeros_like(n))
        neg = torch.where(dL < 0, n, torch.zeros_like(n))
        self.ref = self.ref + torch.sign(dL) * n * self.c
        return (torch.stack([pos, neg], dim=1) / self.max_n).float()
