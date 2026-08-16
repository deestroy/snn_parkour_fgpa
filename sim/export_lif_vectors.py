"""Export golden LIF traces as hex vectors for the Verilog testbench.

Run:  python3 sim/export_lif_vectors.py

For each layer, selects (sample, neuron) pairs from golden/traces_m1.npz --
half of them the most active neurons (a neuron that never spikes never
exercises the reset path), half uniform random for coverage -- and writes
sim/vectors/lif_<layer>.hex.

File format, one 48-bit hex word per line, four consecutive lines per vector
(timesteps 0..3 of one neuron in one sample):

    [47:32] current I[n]     (int16, two's complement)
    [31:16] expected V[n]    (int16, two's complement)
    [15:0]  expected s[n]    (0 or 1)

The testbench resets the neuron before each 4-line group, exactly as the
golden model starts each sample at V = 0.
"""

import os

import numpy as np

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TRACES = os.path.join(REPO, "golden", "traces_m1.npz")
OUT_DIR = os.path.join(REPO, "sim", "vectors")
N_PER_LAYER = 256
T = 4


def select_pairs(spikes: np.ndarray, rng) -> np.ndarray:
    """(B, T, ...) spike array -> (N, 2) array of (sample, flat neuron)."""
    b = spikes.shape[0]
    flat = spikes.reshape(b, T, -1)          # (B, T, N)
    per_pair = flat.sum(axis=1).ravel()      # spikes per (sample, neuron)
    order = np.argsort(per_pair)[::-1]
    half = N_PER_LAYER // 2
    busiest = order[:half]
    rest = rng.choice(len(per_pair), half, replace=False)
    chosen = np.unique(np.concatenate([busiest, rest]))
    n = flat.shape[2]
    return np.stack([chosen // n, chosen % n], axis=1)


def to_u16(x: int) -> int:
    return int(x) & 0xFFFF


def main() -> int:
    z = np.load(TRACES)
    rng = np.random.default_rng(0)
    os.makedirs(OUT_DIR, exist_ok=True)

    for layer in ("c1", "c2", "c3", "fc"):
        cur = z[layer + "_I"]
        mem = z[layer + "_V"]
        spk = z[layer + "_S"]
        b = cur.shape[0]
        curf = cur.reshape(b, T, -1)
        memf = mem.reshape(b, T, -1)
        spkf = spk.reshape(b, T, -1)

        # int16 must faithfully hold every exported value (D0010's width)
        assert abs(int(cur.min())) < 32768 and int(cur.max()) < 32768
        assert abs(int(mem.min())) < 32768 and int(mem.max()) < 32768

        pairs = select_pairs(spkf.astype(np.int64), rng)
        path = os.path.join(OUT_DIR, "lif_%s.hex" % layer)
        n_spiking = 0
        with open(path, "w") as fh:
            for s_idx, n_idx in pairs:
                n_spiking += int(spkf[s_idx, :, n_idx].any())
                for t in range(T):
                    word = (to_u16(curf[s_idx, t, n_idx]) << 32) \
                         | (to_u16(memf[s_idx, t, n_idx]) << 16) \
                         | int(spkf[s_idx, t, n_idx])
                    fh.write("%012x\n" % word)
        print("%s: %d vectors (%d contain spikes) -> %s"
              % (layer, len(pairs), n_spiking,
                 os.path.relpath(path, REPO)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
