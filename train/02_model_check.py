"""M0, component 3: check the network before training it.

Run:  python3 train/02_model_check.py

Four things are verified, none of which require a trained network:

1. Shapes. The forward pass runs and produces (batch, n_classes) logits.
2. Resource budget. Parameter and membrane-state counts against the PYNQ-Z2's
   612.5 KB of block RAM. This is the check that catches the class of error in
   docs/decisions.md D0004 -- a layer table that does not close arithmetically.
3. State is actually reset between samples. An SNN carries membrane potential
   across timesteps; if it also carries it across samples, results depend on
   batch order and every downstream measurement is quietly wrong.
4. Firing rates are being collected and are in [0, 1].

An untrained network's firing rates are meaningless as science -- weights are
random. What they establish is that the plumbing reports them at all.
"""

import os
import sys

import torch

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from model import ConvSNN, T_DEFAULT  # noqa: E402

BRAM_KB = 4900 * 1024 / 8 / 1024  # PYNQ-Z2: 4900 Kb of block RAM
WEIGHT_BITS = 8
MEMBRANE_BITS = 16


def report(name: str, net: ConvSNN) -> float:
    print("\n=== %s ===" % name)
    print("input %s, T=%d, pool_before_fc=%s"
          % (net.in_shape, net.n_steps, net.pool_before_fc))

    params = net.param_budget()
    total_p = sum(n for _, n in params)
    for layer, n in params:
        print("  %-3s %9d params  (%.1f%% of weights)"
              % (layer, n, 100.0 * n / total_p))
    print("  %-3s %9d params" % ("SUM", total_p))

    neurons = net.neuron_count()
    total_n = sum(n for _, n in neurons)
    print("  neurons: %s = %d"
          % (" + ".join("%s %d" % (l, n) for l, n in neurons), total_n))

    w_kb = total_p * WEIGHT_BITS / 8 / 1024
    m_kb = total_n * MEMBRANE_BITS / 8 / 1024
    print("  weights   %7.1f KB at %d-bit" % (w_kb, WEIGHT_BITS))
    print("  membrane  %7.1f KB at %d-bit" % (m_kb, MEMBRANE_BITS))
    print("  on-chip   %7.1f KB  = %.1f%% of %.1f KB block RAM"
          % (w_kb + m_kb, 100.0 * (w_kb + m_kb) / BRAM_KB, BRAM_KB))
    return w_kb + m_kb


def check_forward(net: ConvSNN, batch: int = 3) -> bool:
    x = (torch.rand(net.n_steps, batch, *net.in_shape) < 0.17).float()
    logits, rates = net(x)
    ok = logits.shape == (batch, net.readout.out_features)
    print("  forward   logits %s  expected %s -> %s"
          % (tuple(logits.shape), (batch, net.readout.out_features),
             "OK" if ok else "FAIL"))
    print("  rates     %s"
          % "  ".join("%s=%.3f" % (k, float(v)) for k, v in rates.items()))
    in_range = all(0.0 <= float(v) <= 1.0 for v in rates.values())
    if not in_range:
        print("  FAIL: a firing rate is outside [0, 1]")

    # A silent layer is the classic SNN failure: no spikes leave it, so every
    # layer downstream sees zero current and the network cannot learn. With
    # PyTorch's default init this network is silent from C2 onward, which is
    # why INIT_GAIN exists (docs/decisions.md D0005). Catch it here rather
    # than after an hour of training that goes nowhere.
    silent = [k for k, v in rates.items() if float(v) == 0.0]
    if silent:
        print("  FAIL: layer(s) %s emitted no spikes at all - the network is"
              " silent downstream. Check INIT_GAIN." % ", ".join(silent))

    return ok and in_range and not silent


def check_state_reset(net: ConvSNN) -> bool:
    """Same input twice must give the same answer. If membrane state leaked
    between calls it would not, and every firing rate we ever measure would
    depend on what happened to run before it."""
    net.eval()
    x = (torch.rand(net.n_steps, 2, *net.in_shape) < 0.17).float()
    with torch.no_grad():
        a, ra = net(x)
        b, rb = net(x)
    same = torch.equal(a, b) and all(
        torch.equal(ra[k], rb[k]) for k in ra)
    print("  reset     identical input -> identical output: %s"
          % ("OK" if same else "FAIL - state is leaking between samples"))
    return same


def main() -> int:
    torch.manual_seed(0)
    ok = True

    nmnist = ConvSNN(in_shape=(2, 34, 34), n_classes=10, n_steps=T_DEFAULT)
    report("N-MNIST variant (34x34) - what M0 trains", nmnist)
    ok &= check_forward(nmnist)
    ok &= check_state_reset(nmnist)

    target = ConvSNN(in_shape=(2, 48, 64), n_classes=10, n_steps=T_DEFAULT)
    total_kb = report("Target variant (48x64) - what the FPGA implements", target)
    ok &= check_forward(target)

    print("\n--- the project brief cross-check on the target variant ---")
    for label, got, want in (
        ("FC input features", target.flat_dim, 768),
        ("total params", sum(n for _, n in target.param_budget()), 121632),
        ("neurons", sum(n for _, n in target.neuron_count()), 21632),
    ):
        flag = "OK" if got == want else "MISMATCH"
        print("  %-18s got %-8d expect %-8d %s" % (label, got, want, flag))
        ok &= got == want
    print("  %-18s got %-8.1f expect %-8s %s"
          % ("on-chip KB", total_kb, "161.0",
             "OK" if abs(total_kb - 161.0) < 1.0 else "MISMATCH"))
    ok &= abs(total_kb - 161.0) < 1.0

    print("\n%s" % ("PASS: shapes, budget, reset and rate logging all check out."
                    if ok else "FAIL: see above."))
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
