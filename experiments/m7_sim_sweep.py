"""M7 rehearsal in SIMULATION: latency (cycles per inference) of the dense
and event-driven C1 engines versus input firing rate.

For each input density p: synthetic Bernoulli(p) inputs + golden outputs
(sim/export_axis_sweep.py), then the AXIS testbench with no gaps for
ENGINE=0 (dense), ENGINE=1 K=1 and K=4, per-sample cycle counts recorded.
Every run is also a bit-identity check against the golden model.

This is a PREDICTED latency curve at 100 MHz. It is not energy, and it is
not the board. It exists so that the shape of the M7 experiment is known
before the meter arrives, and so the board runs have a model to be checked
against (the ED K=4 sim figure matched the board within 3 % on 2026-08-19).

Run:  python3 experiments/m7_sim_sweep.py [--quick]
Writes experiments/m7_sim/sweep.csv and experiments/m7_sim/m7_sim_crossover.png
"""

import argparse
import csv
import os
import re
import subprocess
import sys

import numpy as np

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(REPO, "experiments", "m7_sim")
DENSITIES = [0.005, 0.01, 0.02, 0.05, 0.10, 0.20, 0.30, 0.50, 0.70, 1.00]
ENGINES = [("dense", {"ENGINE": "0"}), ("ed_k1", {"ENGINE": "1", "K": "1"}),
           ("ed_k4", {"ENGINE": "1", "K": "4"})]


def run(cmd, env=None):
    e = dict(os.environ); e.update(env or {})
    r = subprocess.run(cmd, cwd=REPO, env=e, shell=True, capture_output=True, text=True)
    return r.returncode, r.stdout + r.stderr


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--quick", action="store_true", help="3 densities, for a smoke test")
    a = ap.parse_args()
    dens = [0.01, 0.10, 0.50] if a.quick else DENSITIES
    os.makedirs(OUT, exist_ok=True)
    rows = []
    for p in dens:
        pre = os.path.join(OUT, "p%04d" % int(round(p * 1000)))
        rc, out = run("python3 sim/export_axis_sweep.py --density %g --out-prefix %s" % (p, pre))
        m = re.search(r"input rate ([\d.]+) \(([\d.]+) spikes/sample\), C1 output rate ([\d.]+)", out)
        if rc or not m:
            print("export failed at p=%g\n%s" % (p, out)); return 1
        in_rate, spikes, out_rate = float(m.group(1)), float(m.group(2)), float(m.group(3))
        for name, env in ENGINES:
            cyc = pre + "_%s_cycles.txt" % name
            e = dict(env); e.update({"NOGAP": "1", "AXIS_IN": pre + "_in.hex",
                                     "AXIS_OUT": pre + "_out.hex", "CYCLES": cyc})
            rc, out = run("bash sim/run_axis_tb.sh c1", e)
            ok = "TB_PASS" in out
            d = np.loadtxt(cyc, ndmin=2) if os.path.exists(cyc) else np.zeros((0, 3))
            tot = d[:, 1].mean() if d.size else float("nan")
            busy = d[:, 2].mean() if d.size else float("nan")
            rows.append([p, in_rate, spikes, out_rate, name, tot, busy, "PASS" if ok else "FAIL"])
            print("p=%.3f in=%.4f (%.0f spk) out=%.4f  %-6s total %8.0f cyc  engine %8.0f  %s"
                  % (p, in_rate, spikes, out_rate, name, tot, busy, "PASS" if ok else "FAIL"), flush=True)
    with open(os.path.join(OUT, "sweep.csv"), "w", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(["density", "input_rate", "spikes_per_sample", "c1_output_rate", "engine",
                    "cycles_total_mean", "cycles_engine_mean", "check"])
        w.writerows(rows)
    plot(rows)
    return 0


def plot(rows):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    fig, ax = plt.subplots(figsize=(7, 4.5))
    for name, label, mk in (("dense", "dense (clock-driven)", "s"),
                            ("ed_k1", "event-driven, K=1", "o"),
                            ("ed_k4", "event-driven, K=4", "^")):
        pts = sorted((r[1], r[5] / 1e5) for r in rows if r[4] == name)
        ax.plot([x for x, _ in pts], [y for _, y in pts], marker=mk, label=label)
    ax.axvline(0.06, color="grey", ls=":", lw=1)
    ax.text(0.062, ax.get_ylim()[1] * 0.95, "trained C1\ninput rate", fontsize=8, color="grey", va="top")
    ax.set_xscale("log")
    ax.set_xlabel("C1 input firing rate (fraction of input bits = 1)")
    ax.set_ylabel("latency per inference, ms  (simulation, 100 MHz)")
    ax.set_title("SIMULATED latency vs firing rate, C1 on the XC7Z020 -- not energy, not the board")
    ax.grid(True, which="both", alpha=0.3)
    ax.legend()
    fig.tight_layout()
    fig.savefig(os.path.join(OUT, "m7_sim_crossover.png"), dpi=150)
    print("wrote", os.path.join(OUT, "m7_sim_crossover.png"))


if __name__ == "__main__":
    raise SystemExit(main())
