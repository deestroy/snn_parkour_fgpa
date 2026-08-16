"""The target convolutional SNN, with per-layer firing-rate logging.

Architecture follows the project brief, including the 2x2 pool that the layer table
omits (see docs/decisions.md D0004):

    input (2, H, W)
      -> C1 2->16,  3x3 stride 2  -> LIF
      -> C2 16->32, 3x3 stride 2  -> LIF
      -> C3 32->64, 3x3 stride 2  -> LIF
      -> 2x2 average pool                 [reduces 3072 -> 768 at 48x64]
      -> FC -> 128                -> LIF  [the encoder output]
      -> readout Linear -> n_classes      [training scaffolding, NOT hardware]

Two things differ from an ordinary CNN and both matter.

First, `snn.Leaky` layers carry state (the membrane potential) from one
timestep to the next, so the forward pass is a loop over T timesteps rather
than a single sweep. Each layer must be reset at the start of every sample.

Second, every LIF layer records the fraction of its neurons that fired. That
fraction is the independent variable of the whole thesis, so it is collected by
the model itself rather than bolted on later.

The readout layer is not part of the hardware. The FPGA implements the encoder
(everything up to and including the 128-unit LIF); the readout exists only so
the encoder can be trained on a classification task.

Self-check:  python3 train/02_model_check.py
"""

from typing import Dict, List, Tuple

import torch
import torch.nn as nn
import snntorch as snn

# Project-wide neuron settings. Fixed by docs/decisions.md D0002: snnTorch's
# defaults, meaning reset-by-subtraction applied one timestep late, and firing
# on strict V > threshold. Passed explicitly everywhere so the choice is
# visible in the code rather than inherited silently from a library default.
RESET_DELAY = True
BETA = 0.9
THRESHOLD = 1.0
T_DEFAULT = 4

# PyTorch's default Kaiming-uniform init leaves this network silent: measured
# on binarised N-MNIST, C1's input current peaks at 0.9458 against a threshold
# of 1.0, so C1 barely fires and every layer after it receives exactly zero.
# No spikes means no forward signal. Scaling the initial weights fixes it.
# Measured starting firing rates by gain, averaged over 32 samples:
#
#     gain    c1      c2      c3      fc
#     x1    0.0088  0.0000  0.0000  0.0000   <- silent
#     x2    0.0474  0.0082  0.0000  0.0000   <- still silent past C2
#     x4    0.1716  0.1936  0.1876  0.1516   <- alive at every layer
#     x8    0.2163  0.3454  0.3470  0.3498   <- denser than we want
#
# Note this is one knob, not two: multiplying every weight by g and multiplying
# the threshold by g produce an identical network, because the LIF update and
# the reset-by-subtraction are both linear in that scale. So the hardware can
# pin the threshold to a convenient fixed-point constant (M1) and let the
# weights carry the scale. See docs/decisions.md D0005.
INIT_GAIN = 4.0


class ConvSNN(nn.Module):
    def __init__(
        self,
        in_shape: Tuple[int, int, int] = (2, 34, 34),
        n_classes: int = 10,
        feat_dim: int = 128,
        beta: float = BETA,
        threshold: float = THRESHOLD,
        n_steps: int = T_DEFAULT,
        pool_before_fc: bool = True,
        init_gain: float = INIT_GAIN,
    ) -> None:
        super().__init__()
        self.in_shape = in_shape
        self.n_steps = n_steps
        self.pool_before_fc = pool_before_fc

        c_in, h, w = in_shape
        self.conv1 = nn.Conv2d(c_in, 16, 3, stride=2, padding=1, bias=False)
        self.conv2 = nn.Conv2d(16, 32, 3, stride=2, padding=1, bias=False)
        self.conv3 = nn.Conv2d(32, 64, 3, stride=2, padding=1, bias=False)
        self.pool = nn.AvgPool2d(2) if pool_before_fc else nn.Identity()

        self.flat_dim = self._infer_flat_dim()
        self.fc = nn.Linear(self.flat_dim, feat_dim, bias=False)
        self.readout = nn.Linear(feat_dim, n_classes, bias=False)

        # Bias is off on every hardware layer on purpose: a bias would be a
        # per-neuron constant added every timestep, which is extra on-chip
        # storage and an extra add in the LIF update for no accuracy we need.
        mk = lambda: snn.Leaky(beta=beta, threshold=threshold,
                               reset_delay=RESET_DELAY)
        self.lif1, self.lif2 = mk(), mk()
        self.lif3, self.lif4 = mk(), mk()

        if init_gain != 1.0:
            with torch.no_grad():
                for layer in (self.conv1, self.conv2, self.conv3, self.fc):
                    layer.weight.mul_(init_gain)

    def _infer_flat_dim(self) -> int:
        with torch.no_grad():
            x = torch.zeros(1, *self.in_shape)
            x = self.pool(self.conv3(self.conv2(self.conv1(x))))
            return int(x.numel())

    def forward(self, x: torch.Tensor
                ) -> Tuple[torch.Tensor, Dict[str, torch.Tensor]]:
        """:param x: (T, batch, C, H, W) -- time is the FIRST dimension.
        :return: (logits, firing_rates) where firing_rates maps layer name to a
            scalar tensor: the fraction of that layer's neurons that fired,
            averaged over timesteps and batch."""
        mem = [lif.init_leaky() for lif in
               (self.lif1, self.lif2, self.lif3, self.lif4)]
        spike_sums: Dict[str, float] = {}
        logit_sum = 0.0

        for t in range(x.shape[0]):
            s1, mem[0] = self.lif1(self.conv1(x[t]), mem[0])
            s2, mem[1] = self.lif2(self.conv2(s1), mem[1])
            s3, mem[2] = self.lif3(self.conv3(s2), mem[2])
            flat = self.pool(s3).flatten(1)
            s4, mem[3] = self.lif4(self.fc(flat), mem[3])

            # Summing logits over timesteps means the readout sees the encoder's
            # total activity across the whole sample, which is what a rate code
            # is. No spiking neuron here -- the readout is not hardware.
            logit_sum = logit_sum + self.readout(s4)

            for name, s in (("c1", s1), ("c2", s2), ("c3", s3), ("fc", s4)):
                spike_sums[name] = spike_sums.get(name, 0.0) + s.mean()

        rates = {k: v / x.shape[0] for k, v in spike_sums.items()}
        return logit_sum, rates

    def param_budget(self) -> List[Tuple[str, int]]:
        """(layer, parameter count) for the layers that become hardware.
        The readout is excluded because it does not go on the FPGA."""
        return [
            ("C1", self.conv1.weight.numel()),
            ("C2", self.conv2.weight.numel()),
            ("C3", self.conv3.weight.numel()),
            ("FC", self.fc.weight.numel()),
        ]

    def neuron_count(self) -> List[Tuple[str, int]]:
        """(layer, neuron count) -- each needs 16 bits of membrane state."""
        with torch.no_grad():
            x = torch.zeros(1, *self.in_shape)
            a = self.conv1(x); b = self.conv2(a); c = self.conv3(b)
        return [("C1", a.numel()), ("C2", b.numel()), ("C3", c.numel()),
                ("FC", self.fc.out_features)]
