"""The FPGA-sized spiking encoder behind extreme-parkour's `base_backbone`
interface, fed by simulated events instead of depth pixels.

extreme-parkour's vision distillation (rsl_rl OnPolicyRunner.learn_vision)
calls `depth_encoder(depth_image, proprio)` once per camera tick (every
`depth.update_interval` control steps = 10 Hz) and holds the latent between
ticks. `depth_encoder` is their RecurrentDepthBackbone: base_backbone ->
combination MLP with proprio -> GRU -> (latent 32, yaw 2). We replace ONLY
base_backbone, so their GRU, student actor, DAgger loop, checkpoints and
logging are untouched -- the FPGA accelerates the conv encoder and the host
runs the rest, which is the deployment split anyway.

Input: their depth image is normalised as (d - near)/(far - near) - 0.5 with
near = 0, far = far_clip, so depth = (x + 0.5) * far and the recreation's
intensity 1 - depth/far is simply 0.5 - x. The image is resized to 64x64 by
the env config the launcher sets (their 58x87 backbone is not used).

Window: `window="repeat"` feeds the current event frame for all T spiking
timesteps (direct coding, what the recreation's student was trained with);
`"consecutive"` feeds the last T tick frames (what the recreation's vector
recorder actually exported -- see the port notes). Frames are binarised
(any event -> 1) by default, because that is what the hardware receives
(D0003); the recreation trained on counts/8 and exported binarised, another
train/deploy mismatch this port closes.

Episode starts: environments whose episode_length_buf is at or below the
camera interval are treated as freshly reset -- event reference re-seeded,
history zeroed -- mirroring the recreation's env.reset(). Their GRU state is
not reset on episode boundaries (stock behaviour), and we leave that alone.
"""
import torch
import torch.nn as nn

from event_sim_torch import EventSimulatorTorch
from fpga_encoder import FPGAEncoder


class _Cfg:
    def __init__(self, event_latent):
        self.event_latent = event_latent


class FPGAEventBackbone(nn.Module):
    def __init__(self, env, latent_dim: int = 32, T: int = 4, window: str = "repeat",
                 binarise: bool = True, threshold_c: float = 0.10,
                 max_events_per_px: int = 8):
        super().__init__()
        assert window in ("repeat", "consecutive")
        self.env = env
        self.T = T
        self.window = window
        self.binarise = binarise
        self.far = float(env.cfg.depth.far_clip - env.cfg.depth.near_clip)
        self.tick = int(env.cfg.depth.update_interval)
        self.sim = EventSimulatorTorch(far=self.far, threshold_c=threshold_c,
                                       max_events_per_px=max_events_per_px)
        self.enc = FPGAEncoder(_Cfg(latent_dim))      # head: 1024 -> latent + 2
        self.latent_dim = latent_dim
        self.hist = None                              # (T, B, 2, H, W) tick frames
        self.n_calls = 0
        self.last_rate = 0.0                          # mean event-bit rate, for logs

    def _episode_start_mask(self):
        return self.env.episode_length_buf <= self.tick

    @torch.no_grad()
    def _events(self, depth_norm: torch.Tensor) -> torch.Tensor:
        """their normalised image (B, H, W) -> event frame (B, 2, H, W)."""
        depth = (depth_norm + 0.5) * self.far           # metres, [0, far]
        reset = self._episode_start_mask()
        ev = self.sim.step(depth, reset_mask=reset)
        ev[reset] = 0.0
        if self.binarise:
            ev = (ev > 0).float()
        return ev

    def forward(self, depth_image: torch.Tensor) -> torch.Tensor:
        """(B, H, W) normalised depth -> (B, latent_dim); called once per tick."""
        ev = self._events(depth_image)
        B = ev.shape[0]
        if self.window == "repeat":
            x_seq = ev.unsqueeze(0).expand(self.T, *ev.shape)
        else:
            if self.hist is None or self.hist.shape[1] != B:
                self.hist = torch.zeros(self.T, *ev.shape, device=ev.device)
            reset = self._episode_start_mask()
            self.hist[:, reset] = 0.0
            self.hist = torch.cat([self.hist[1:], ev.unsqueeze(0)], dim=0)
            x_seq = self.hist
        self.last_rate = float(ev.mean())
        self.n_calls += 1
        latent, _heading = self.enc(x_seq)            # the +2 head is unused here:
        return latent                                 # yaw comes from their GRU path
