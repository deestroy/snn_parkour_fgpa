"""The golden model: the full network in pure integer arithmetic.

This file is the source of truth for every piece of hardware in the project.
No torch, no floats anywhere in the datapath -- every operation here is one the
FPGA can reproduce exactly, and integer arithmetic has no rounding modes or
platform quirks, so the outputs are bit-identical on any machine.

Semantics (fixed by decisions D0002, D0007, D0008):

    weights   int8, real value = w * 2^-k, k per layer (k=6 for all four)
    input     binary spikes (0/1)
    current   I = sum(w * s)                    integer dot product
    leak      V - (V >> 3)                      arithmetic shift = beta 0.875
    update    V' = leak(V) + I - pending*thr    pending = (V > thr), D0002's
    spike     s = (V' > thr)                    delayed reset, strict >
    thr       2^k = 64 (conv layers), 2^(k+2) = 256 (FC: pool /4 folded in)
    pool      2x2 SUM of spikes (values 0..4), exact substitute for avg

The readout (128 -> 10) is not hardware: the FPGA emits FC spike counts and
the host applies the float readout. Kept in float here, applied once to the
spike counts, which is exactly what training's summed logits computed.
"""

import os
from typing import Dict, List, Tuple

import numpy as np

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
WEIGHTS = os.path.join(REPO, "golden", "m1_weights_int8.npz")

LEAK_SHIFT = 3  # beta = 1 - 2^-3 = 0.875


def lif_update(v: np.ndarray, current: np.ndarray, thr: int
               ) -> Tuple[np.ndarray, np.ndarray]:
    """One integer LIF step for an array of neurons. Returns (v', spikes).

    numpy's >> on signed ints is an arithmetic shift (rounds toward -inf),
    which is exactly what a Verilog >>> does. The pending reset is computed
    from the STORED membrane, so the subtraction lands one step late (D0002).
    """
    pending = v > thr
    v = (v - (v >> LEAK_SHIFT)) + current - pending * thr
    return v, (v > thr)


def _im2col(x: np.ndarray, hw_out: int) -> np.ndarray:
    """(B, C, H, W) -> (B, hw_out*hw_out, C*9) patches for 3x3/stride2/pad1."""
    b, c, h, w = x.shape
    xp = np.zeros((b, c, h + 2, w + 2), dtype=x.dtype)
    xp[:, :, 1:h + 1, 1:w + 1] = x
    cols = np.empty((b, hw_out * hw_out, c * 9), dtype=x.dtype)
    i = 0
    for oy in range(hw_out):
        for ox in range(hw_out):
            patch = xp[:, :, 2 * oy:2 * oy + 3, 2 * ox:2 * ox + 3]
            cols[:, i, :] = patch.reshape(b, -1)
            i += 1
    return cols


def conv_int(spikes: np.ndarray, w_q: np.ndarray, hw_out: int) -> np.ndarray:
    """Integer 3x3 stride-2 pad-1 convolution. Returns (B, C_out, H_out, W_out)
    int32 currents. Integer adds are associative, so this matmul formulation is
    bit-identical to the hardware's sequential accumulate."""
    b = spikes.shape[0]
    c_out = w_q.shape[0]
    cols = _im2col(spikes.astype(np.int32), hw_out)
    flat_w = w_q.reshape(c_out, -1).astype(np.int32)
    out = cols @ flat_w.T  # (B, hw_out^2, C_out)
    return out.transpose(0, 2, 1).reshape(b, c_out, hw_out, hw_out)


def sum_pool_2x2(spikes: np.ndarray) -> np.ndarray:
    """2x2 sum pool, floor division of the grid (5x5 -> 2x2 drops row/col 4),
    matching torch's AvgPool2d(2) coverage. Output values 0..4."""
    b, c, h, w = spikes.shape
    h2, w2 = h // 2, w // 2
    x = spikes[:, :, :h2 * 2, :w2 * 2].astype(np.int32)
    return (x.reshape(b, c, h2, 2, w2, 2).sum(axis=(3, 5)))


class GoldenNetwork:
    """Integer-exact reference for the ConvSNN encoder + float readout."""

    def __init__(self, weights_path: str = WEIGHTS,
                 readout_w: np.ndarray = None):
        z = np.load(weights_path)
        self.w = {n: z[n] for n in ("conv1", "conv2", "conv3", "fc")}
        self.k = {n: int(z[n + "_k"]) for n in self.w}
        assert int(z["n_steps"]) >= 1
        self.n_steps = int(z["n_steps"])
        # conv thresholds are 2^k; FC folds the pool's /4 into the shift
        self.thr = {"c1": 2 ** self.k["conv1"], "c2": 2 ** self.k["conv2"],
                    "c3": 2 ** self.k["conv3"], "fc": 2 ** (self.k["fc"] + 2)}
        self.readout_w = readout_w  # float (10, 128) or None

    def forward(self, frames: np.ndarray, record: bool = False
                ) -> Tuple[np.ndarray, Dict[str, List[np.ndarray]]]:
        """:param frames: (B, T, 2, 34, 34) event counts (any int dtype).
        :param record: keep per-timestep currents, membranes and spikes.
        :return: (fc spike counts (B, 128) int32, trace dict)."""
        b = frames.shape[0]
        spikes_in = (frames > 0).astype(np.int8)  # binarise (D0003)

        v = {"c1": np.zeros((b, 16, 17, 17), np.int32),
             "c2": np.zeros((b, 32, 9, 9), np.int32),
             "c3": np.zeros((b, 64, 5, 5), np.int32),
             "fc": np.zeros((b, 128), np.int32)}
        counts = np.zeros((b, 128), np.int32)
        trace: Dict[str, List[np.ndarray]] = {}
        self.v_extremes = {n: (0, 0) for n in v}

        for t in range(self.n_steps):
            i1 = conv_int(spikes_in[:, t], self.w["conv1"], 17)
            v["c1"], s1 = lif_update(v["c1"], i1, self.thr["c1"])
            i2 = conv_int(s1.astype(np.int8), self.w["conv2"], 9)
            v["c2"], s2 = lif_update(v["c2"], i2, self.thr["c2"])
            i3 = conv_int(s2.astype(np.int8), self.w["conv3"], 5)
            v["c3"], s3 = lif_update(v["c3"], i3, self.thr["c3"])
            pooled = sum_pool_2x2(s3).reshape(b, -1)  # (B, 256), values 0..4
            i4 = pooled @ self.w["fc"].astype(np.int32).T
            v["fc"], s4 = lif_update(v["fc"], i4, self.thr["fc"])
            counts += s4

            for name, vv in v.items():
                lo, hi = self.v_extremes[name]
                self.v_extremes[name] = (min(lo, int(vv.min())),
                                         max(hi, int(vv.max())))
            if record:
                for key, val in (("in", spikes_in[:, t]),
                                 ("c1_I", i1), ("c1_V", v["c1"]), ("c1_S", s1),
                                 ("c2_I", i2), ("c2_V", v["c2"]), ("c2_S", s2),
                                 ("c3_I", i3), ("c3_V", v["c3"]), ("c3_S", s3),
                                 ("pool", pooled),
                                 ("fc_I", i4), ("fc_V", v["fc"]), ("fc_S", s4)):
                    trace.setdefault(key, []).append(val.copy())

        return counts, trace

    def classify(self, frames: np.ndarray) -> np.ndarray:
        """(B,) predicted labels. Requires readout_w."""
        counts, _ = self.forward(frames)
        logits = counts.astype(np.float32) @ self.readout_w.T
        return logits.argmax(1)
