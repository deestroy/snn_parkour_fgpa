"""The FPGA-sized spiking encoder (year-two P1): the 4-layer conv SNN that
the ZedBoard engines implement, as a drop-in replacement for the 11.19M
spiking ResNet-18 student encoder.

Semantics are the HARDWARE's, exactly (the fixed-point golden model and both
RTL engines are bit-identical to this rule after quantisation):

    pending[t] = 1 if V[t-1] >  theta        (strict >, from the STORED V)
    V[t]       = beta*V[t-1] + I[t] - pending[t]*theta
    s[t]       = 1 if V[t]   >  theta
    beta = 0.875 (a shift in hardware), reset by subtraction DELAYED one step

(snnTorch Leaky defaults; project decision D0002.) Training uses an ATan
surrogate for the spike gradient, like the rest of this codebase.

Stack (input 2 x 64 x 64 event frames, T=4 direct coding, same as the
ResNet student): c1 2->16 s2 (32x32), c2 16->32 s2 (16x16), c3 32->64 s2
(8x8), 2x2 sum pool (4x4), FC 1024 -> latent+2. ~54k parameters, ~200x
smaller than the paper's encoder. Batch norm is NOT used (nothing in the
fixed-point pipeline can absorb it at inference; weights must quantise to
int8 with power-of-two scales, so the network trains the way it will run).
"""

import math

import torch
import torch.nn as nn


class _AtanSpike(torch.autograd.Function):
    @staticmethod
    def forward(ctx, v_minus_theta, alpha=2.0):
        ctx.save_for_backward(v_minus_theta)
        ctx.alpha = alpha
        return (v_minus_theta > 0).float()          # strict >

    @staticmethod
    def backward(ctx, grad_out):
        (x,) = ctx.saved_tensors
        a = ctx.alpha
        return grad_out * (a / 2) / (1 + (math.pi / 2 * a * x) ** 2), None


def _spike(v, theta):
    return _AtanSpike.apply(v - theta)


class LIFState:
    """Per-layer state for one rollout of T steps."""
    def __init__(self):
        self.v = None
        self.pending = None


class FPGAEncoder(nn.Module):
    """(T, B, 2, 64, 64) -> latent (B, event_latent), heading (B, 2).
    Same interface as SpikingResNet18Encoder."""

    THETA = 1.0
    BETA = 0.875

    def __init__(self, cfg, in_ch: int = 2):
        super().__init__()
        self.c1 = nn.Conv2d(in_ch, 16, 3, 2, 1, bias=False)
        self.c2 = nn.Conv2d(16, 32, 3, 2, 1, bias=False)
        self.c3 = nn.Conv2d(32, 64, 3, 2, 1, bias=False)
        self.pool = nn.AvgPool2d(2)                  # x4 = sum pool; the /4
                                                     # folds into FC scale at
                                                     # quantisation (D0004)
        self.head = nn.Linear(64 * 4 * 4, cfg.event_latent + 2)
        self.head_latent_dim = cfg.event_latent
        for m in (self.c1, self.c2, self.c3):
            nn.init.kaiming_normal_(m.weight, nonlinearity="relu")
            m.weight.data.mul_(4.0)                  # INIT_GAIN (D0005): LIF
                                                     # nets start silent otherwise

    def _lif(self, st: LIFState, i_t: torch.Tensor) -> torch.Tensor:
        if st.v is None:
            st.v = torch.zeros_like(i_t)
            st.pending = torch.zeros_like(i_t)
        v = self.BETA * st.v + i_t - st.pending * self.THETA
        s = _spike(v, self.THETA)
        st.pending = (v > self.THETA).float().detach()  # next step's subtraction
        st.v = v
        return s

    def forward(self, x_seq):
        T = x_seq.shape[0]
        s1, s2, s3 = LIFState(), LIFState(), LIFState()
        acc = 0
        for t in range(T):
            x = self._lif(s1, self.c1(x_seq[t]))
            x = self._lif(s2, self.c2(x))
            x = self._lif(s3, self.c3(x))
            x = self.pool(x) * 4.0                   # sum pool
            acc = acc + self.head(x.flatten(1))
        out = acc / T                                # rate-decoded head, as the
                                                     # ResNet student's mean output
        return out[:, :self.head_latent_dim], out[:, self.head_latent_dim:]
