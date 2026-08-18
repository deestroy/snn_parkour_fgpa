"""Event-driven conv layer in software: the M6 architecture, in Python first.

This is D0016–D0018 written as code so the design can be checked against the
golden model BEFORE any Verilog exists. It computes exactly what
golden/network.py computes for one conv layer, but in the event-driven order:

    for each input spike (address list, D0016):
        for each output position it touches (computed, D0018):
            for each output channel:
                I[oc, oy, ox] += W_T[ic, ky, kx, oc]      <- scatter, transposed W
    then one sweep over all neurons:  (V, s) = lif_update(V, I); I = 0

Because integer addition is associative, the accumulated current per neuron is
identical to the dense engine's dot product, so V and s must be bit-identical
to golden. verify_event_driven() asserts exactly that on the M1 traces.

Bank mapping (D0017): bank = oc mod K, offset = ((oc // K) * H_OUT + oy) * W_OUT
+ ox. K=1 collapses to a flat address. The SAME function will drive the Verilog
exporter and testbench, so it is defined once here.
"""

import os
from typing import Dict, List, Tuple

import numpy as np

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

LEAK_SHIFT = 3

# conv geometry: (C_IN, H_IN, W_IN, C_OUT, H_OUT, W_OUT, threshold, weight key)
GEOM = {
    "c1": (2, 34, 34, 16, 17, 17, 64, "conv1"),
    "c2": (16, 17, 17, 32, 9, 9, 64, "conv2"),
    "c3": (32, 9, 9, 64, 5, 5, 64, "conv3"),
}


# ---------------------------------------------------------------- mappings
def transpose_weights(w: np.ndarray) -> np.ndarray:
    """(C_OUT, C_IN, 3, 3) -> W_T (C_IN, 3, 3, C_OUT). One input tap's
    weights for all output channels are contiguous. Pure re-ordering."""
    return np.ascontiguousarray(w.transpose(1, 2, 3, 0))


def bank_of(oc: int, k: int) -> int:
    return oc % k


def offset_of(oc: int, oy: int, ox: int, k: int, h_out: int, w_out: int) -> int:
    return ((oc // k) * h_out + oy) * w_out + ox


def flat_neuron(oc: int, oy: int, ox: int, h_out: int, w_out: int) -> int:
    """The golden/dense flat index, for cross-checking bank+offset."""
    return (oc * h_out + oy) * w_out + ox


def output_positions(iy: int, ix: int, h_out: int, w_out: int
                     ) -> List[Tuple[int, int, int, int]]:
    """For an input pixel (iy, ix), the (oy, ox, ky, kx) tuples of every
    output position whose 3x3/stride-2/pad-1 window contains it.
    iy = 2*oy + ky - 1  =>  ky = iy - 2*oy + 1 in {0,1,2}."""
    out = []
    for oy in range((iy - 1 + 1) // 2, (iy + 1) // 2 + 1):
        ky = iy - 2 * oy + 1
        if not (0 <= ky <= 2) or not (0 <= oy < h_out):
            continue
        for ox in range((ix - 1 + 1) // 2, (ix + 1) // 2 + 1):
            kx = ix - 2 * ox + 1
            if not (0 <= kx <= 2) or not (0 <= ox < w_out):
                continue
            out.append((oy, ox, ky, kx))
    return out


# ------------------------------------------------------------- the engine
# A subtlety worth stating before the code: the leak and the pending-reset
# are functions of V[n-1] ALONE. If scatter accumulated I[n] into the same
# word as V, the sweep could not recover V[n-1] and both would be corrupted.
# So the engine keeps TWO words per neuron -- the membrane V and an input
# accumulator I -- exactly as the dense engine keeps V in RAM and I in a
# register. Scatter targets I; the sweep computes lif_update(V, I), writes V,
# zeroes I. That doubles the per-neuron BRAM (2 x 16 bits) and is recorded
# as D0019.

class EventDrivenConv:
    def __init__(self, layer: str, w_q: np.ndarray, k: int = 1):
        (self.c_in, self.h_in, self.w_in, self.c_out, self.h_out,
         self.w_out, self.thr, _) = GEOM[layer]
        self.k = k
        self.w_t = transpose_weights(w_q).astype(np.int32)
        n_per_bank = (self.c_out // k) * self.h_out * self.w_out
        self.v = np.zeros((k, n_per_bank), np.int32)   # membrane V[n-1]
        self.i = np.zeros((k, n_per_bank), np.int32)   # accumulated I[n]
        self.stats = {"spikes_in": 0, "rmw": 0, "sweep": 0}
        self._pos = {}
        for iy in range(self.h_in):
            for ix in range(self.w_in):
                self._pos[(iy, ix)] = output_positions(iy, ix, self.h_out, self.w_out)

    def clear(self):
        self.v[:] = 0
        self.i[:] = 0

    def scatter(self, spike_addrs: np.ndarray):
        hw = self.h_in * self.w_in
        for a in spike_addrs:
            ic, r = divmod(int(a), hw)
            iy, ix = divmod(r, self.w_in)
            self.stats["spikes_in"] += 1
            for (oy, ox, ky, kx) in self._pos[(iy, ix)]:
                w_row = self.w_t[ic, ky, kx]
                for oc in range(self.c_out):
                    b = bank_of(oc, self.k)
                    o = offset_of(oc, oy, ox, self.k, self.h_out, self.w_out)
                    self.i[b, o] += w_row[oc]
                    self.stats["rmw"] += 1

    def sweep(self) -> Tuple[np.ndarray, np.ndarray]:
        """Returns (spikes, membranes) as flat arrays in golden order."""
        thr = self.thr
        n = self.c_out * self.h_out * self.w_out
        spikes = np.zeros(n, np.int8)
        mems = np.zeros(n, np.int32)
        for oc in range(self.c_out):
            b = bank_of(oc, self.k)
            for oy in range(self.h_out):
                for ox in range(self.w_out):
                    o = offset_of(oc, oy, ox, self.k, self.h_out, self.w_out)
                    self.stats["sweep"] += 1
                    v = int(self.v[b, o]); cur = int(self.i[b, o])
                    pending = v > thr
                    v = (v - (v >> LEAK_SHIFT)) + cur - (thr if pending else 0)
                    s = v > thr
                    self.v[b, o] = v
                    self.i[b, o] = 0
                    f = flat_neuron(oc, oy, ox, self.h_out, self.w_out)
                    spikes[f] = 1 if s else 0
                    mems[f] = v
        return spikes, mems


# ---------------------------------------------------------- verification
def verify_event_driven(layer: str = "c1", k: int = 1, n_samples: int = 16
                        ) -> Dict[str, object]:
    """Replay golden traces through the event-driven engine; demand equality
    of every spike and membrane, every timestep. Returns stats."""
    z = np.load(os.path.join(REPO, "golden", "traces_m1.npz"))
    w = np.load(os.path.join(REPO, "golden", "m1_weights_int8.npz"))
    c_in, h_in, w_in, c_out, h_out, w_out, thr, wkey = GEOM[layer]
    src = {"c1": "in", "c2": "c1_S", "c3": "c2_S"}[layer]
    spikes_in = (z[src] != 0)                  # (B, T, C_IN, H_IN, W_IN)
    exp_s = (z[layer + "_S"] != 0)             # (B, T, C_OUT, H_OUT, W_OUT)
    exp_v = z[layer + "_V"]

    eng = EventDrivenConv(layer, w[wkey], k=k)
    checked = mismatches = 0
    b, t = spikes_in.shape[:2]
    for s in range(min(b, n_samples)):
        eng.clear()
        for ts in range(t):
            addrs = np.flatnonzero(spikes_in[s, ts].ravel())
            eng.scatter(addrs)
            got_s, got_v = eng.sweep()
            es = exp_s[s, ts].ravel().astype(np.int8)
            ev = exp_v[s, ts].ravel().astype(np.int32)
            mismatches += int((got_s != es).sum()) + int((got_v != ev).sum())
            checked += 2 * es.size
    return {"layer": layer, "k": k, "checked": checked,
            "mismatches": mismatches, **eng.stats}
