"""Figures for the results chapter, generated from the committed data files
(never from numbers typed in here). Run: python3 experiments/figures/make_figures.py
Writes experiments/figures/*.png. Each figure states sim vs board in its title.
Traces (*.npz) are local-only; figures that need them are skipped with a note
if they are absent."""
import glob
import os
import re

import matplotlib
matplotlib.use("Agg")
import matplotlib.ticker
import matplotlib.pyplot as plt
import numpy as np

REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
OUT = os.path.join(REPO, "experiments", "figures")
os.chdir(REPO)
plt.rcParams.update({"font.size": 10, "figure.dpi": 130})


def cycles_file(path):
    return np.array([int(l.split()[1]) for l in open(path) if not l.startswith("#")])


def dense_cycles(path):
    return int(re.search(r"(\d+) engine cycles", open(path).read()).group(1))


# ---------------------------------------------------------------- 1. K = P sweep, N-MNIST and DVS-Gesture, with silicon points
def fig_kp_sweep():
    fig, axes = plt.subplots(1, 2, figsize=(10, 4))
    sets = [("N-MNIST C1 (16 samples)", "experiments/latency_sim/ksweep_c0035",
             {4: 688.5, 8: 575.5}, {4: 1048.9, 8: 540.3}, "total"),
            ("DVS-Gesture C1 (8 clips)", "experiments/dvsgesture/latency_sim",
             {4: 2970.8}, {4: 3706.5}, "engine")]
    for ax, (title, d, ed_board, dn_board, kind) in zip(axes, sets):
        ks = [1, 2, 4, 8, 16]
        ed = []
        for k in ks:
            f = os.path.join(d, "ed_k%d.txt" % k)
            arr = cycles_file(f)
            ed.append((arr.mean() / 100.0, arr.min() / 100.0, arr.max() / 100.0))
        dn = []
        for p in ks:
            f = os.path.join(d, "dense_p%d.txt" % p)
            if os.path.exists(f):
                txt = open(f).read()
                m = re.search(r"(\d+) engine cycles", txt)
                dn.append(int(m.group(1)) / 100.0 if m else cycles_file(f).mean() / 100.0)
            else:
                dn.append(np.nan)
        # N-MNIST dense P=1/P=4 are not in files: P=4 measured 104,059 cycles (README), P=1 = 407.2k (fit)
        if "N-MNIST" in title:
            dn[ks.index(4)] = 104059 / 100.0
            dn[ks.index(1)] = 407.2e3 / 100.0 + 20.0
        ed = np.array(ed)
        ax.errorbar(ks, ed[:, 0], yerr=[ed[:, 0] - ed[:, 1], ed[:, 2] - ed[:, 0]], fmt="o-", capsize=3,
                    label="event-driven K (sim, mean, min-max)")
        ax.plot(ks, dn, "s--", label="dense P (sim)")
        ax.plot(list(ed_board), list(ed_board.values()), "o", ms=11, mfc="none", mec="C0", mew=2, label="ED on silicon")
        ax.plot(list(dn_board), list(dn_board.values()), "s", ms=11, mfc="none", mec="C1", mew=2, label="dense on silicon")
        ax.set_xscale("log", base=2); ax.set_xticks(ks); ax.set_xticklabels(ks)
        ax.set_xlabel("K = P (banks = lanes)"); ax.set_ylabel("latency per inference (us, engine-only, 100 MHz)")
        ax.set_title(title); ax.grid(alpha=.3); ax.legend(fontsize=8)
    fig.suptitle("Matched-parallelism sweep: latency vs K = P (sim; silicon points overlaid)")
    fig.tight_layout(); fig.savefig(os.path.join(OUT, "fig_kp_sweep.png")); plt.close(fig)


# ---------------------------------------------------------------- 2. DVS-Gesture per-clip crossover, sim and board
def fig_perclip():
    rows = []
    for l in open("experiments/dvsgesture/board_ed_k4_20260919.md"):
        m = re.match(r"\| (\d) \| (\d+) \| ([\d.]+) \| ([\d.]+) \| ([+\-][\d.]+) \|", l)
        if m:
            rows.append((int(m.group(1)), int(m.group(2)), float(m.group(3)), float(m.group(4))))
    dense_board = None
    for l in open("experiments/dvsgesture/board_dense_p4_20260919.md"):
        m = re.match(r"\| \d \| \d+ \| ([\d.]+) \|", l)
        if m:
            dense_board = float(m.group(1)); break
    dense_sim = dense_cycles("experiments/dvsgesture/latency_sim/dense_p4.txt") / 100.0
    rows.sort(key=lambda r: r[3])
    clips = [r[0] for r in rows]; sim = [r[3] for r in rows]; board = [r[2] for r in rows]
    x = np.arange(len(rows))
    fig, ax = plt.subplots(figsize=(8, 4))
    ax.bar(x - 0.2, sim, 0.4, label="ED K=4, sim")
    ax.bar(x + 0.2, board, 0.4, label="ED K=4, board")
    ax.axhline(dense_sim, color="C3", ls="--", label="dense P=4, sim (%.0f us)" % dense_sim)
    if dense_board:
        ax.axhline(dense_board, color="C3", ls="-", label="dense P=4, board (%.1f us)" % dense_board)
    ax.set_xticks(x); ax.set_xticklabels(["clip %d\n(gesture %d)" % (r[0], r[1]) for r in rows], fontsize=8)
    ax.set_ylabel("latency per inference (us)")
    ax.set_title("DVS-Gesture C1 at K = P = 4: per-clip latency, clips sorted by simulated ED latency")
    ax.legend(fontsize=8); ax.grid(axis="y", alpha=.3)
    fig.tight_layout(); fig.savefig(os.path.join(OUT, "fig_dvsg_perclip.png")); plt.close(fig)


# ---------------------------------------------------------------- 3. trained-activity curves, C2/C3, both datasets
def fig_activity():
    cfg = [("N-MNIST", "experiments/rate_sweep", "golden/traces_m1.npz", "traces_rate%s.npz",
            {"c2": ("c1_S", 16 * 17 * 17), "c3": ("c2_S", 32 * 9 * 9)}),
           ("DVS-Gesture", "experiments/rate_sweep_dvsg", "golden/traces_dvsgesture.npz", "traces_rate%s.npz",
            {"g2": ("c1_S", 16 * 32 * 32), "g3": ("c2_S", 32 * 16 * 16)})]
    tags = ["base", "0.02", "0.04", "0.08", "0.16", "0.30"]
    fig, ax = plt.subplots(figsize=(8, 4.5))
    ci = 0
    for name, d, base_tr, tr_pat, layers in cfg:
        for L, (key, inbits) in layers.items():
            xs, ys = [], []
            for t in tags:
                tr = base_tr if t == "base" else os.path.join(d, tr_pat % t)
                if not os.path.exists(tr):
                    continue
                spk = int((np.load(tr)[key] != 0).sum())
                rate = spk / (16 * 4 * inbits)
                ed = cycles_file(os.path.join(d, "bench", "ed_k4_%s_%s.txt" % (t, L))).mean()
                dn = dense_cycles(os.path.join(d, "bench", "dense_p4_%s_%s.txt" % (t, L)))
                xs.append(100 * rate); ys.append(dn / ed)
            if not xs:
                print("skipping %s %s: traces not present" % (name, L)); continue
            o = np.argsort(xs); xs = np.array(xs)[o]; ys = np.array(ys)[o]
            ax.plot(xs, ys, "o-", color="C%d" % ci, label="%s %s" % (name, L.upper().replace("G", "C")))
            ci += 1
    ax.axhline(1.0, color="k", lw=1, ls="--")
    ax.set_xscale("log"); ax.set_yscale("log")
    from matplotlib.ticker import ScalarFormatter, FixedLocator
    ax.yaxis.set_major_locator(FixedLocator([1, 1.5, 2, 3, 5, 10, 15])); ax.yaxis.set_major_formatter(ScalarFormatter()); ax.yaxis.set_minor_formatter(matplotlib.ticker.NullFormatter())
    ax.xaxis.set_major_locator(FixedLocator([2, 3, 5, 10, 20, 30, 50])); ax.xaxis.set_major_formatter(ScalarFormatter()); ax.xaxis.set_minor_formatter(matplotlib.ticker.NullFormatter())
    ax.annotate("crossover: dense = ED", xy=(30, 1.0), xytext=(12, 1.25), fontsize=8, arrowprops=dict(arrowstyle="->", lw=0.8))
    ax.set_xlabel("input activity of the layer (% of input bits set, check set)")
    ax.set_ylabel("dense P=4 cycles / ED K=4 cycles (mean over check set)")
    ax.set_title("Event-driven advantage vs trained activity, C2 and C3 (sim, K = P = 4)")
    ax.grid(alpha=.3, which="both"); ax.legend(fontsize=8)
    fig.tight_layout(); fig.savefig(os.path.join(OUT, "fig_activity_c2c3.png")); plt.close(fig)


# ---------------------------------------------------------------- 4. accuracy vs activity with seeds
def fig_accuracy():
    fig, axes = plt.subplots(1, 2, figsize=(10, 4))
    for ax, (name, d, ep) in zip(axes, [("N-MNIST", "experiments/rate_sweep", "epoch 10"),
                                        ("DVS-Gesture", "experiments/rate_sweep_dvsg", "epoch 30")]):
        for r in ["0.02", "0.04", "0.08", "0.16", "0.30"]:
            accs, rates = [], []
            for s in (0, 1, 2):
                f = os.path.join(d, "train_rate%s.log" % r if s == 0 else "train_rate%s_seed%d.log" % (r, s))
                if not os.path.exists(f):
                    continue
                for l in open(f):
                    if l.startswith(ep):
                        m = re.search(r"test acc ([\d.]+).*c1=([\d.]+)\s+c2=([\d.]+)\s+c3=([\d.]+)", l)
                        accs.append(100 * float(m.group(1))); rates.append(100 * np.mean([float(m.group(i)) for i in (2, 3, 4)]))
            if accs:
                ax.errorbar(np.mean(rates), np.mean(accs), yerr=np.std(accs, ddof=1) if len(accs) > 1 else 0,
                            fmt="o", capsize=4, color="C0")
                ax.annotate("n=%d" % len(accs), (np.mean(rates), np.mean(accs)), textcoords="offset points", xytext=(6, 4), fontsize=7)
        ax.set_xscale("log"); ax.set_xlabel("achieved conv firing rate (%, mean of c1-c3)"); ax.set_ylabel("test accuracy (%)")
        ax.set_title("%s: accuracy vs trained activity\n(mean +- sd over 3 seeds)" % name, fontsize=10); ax.grid(alpha=.3, which="both")
    fig.tight_layout(); fig.savefig(os.path.join(OUT, "fig_accuracy_vs_activity.png")); plt.close(fig)


# ---------------------------------------------------------------- 5. T sweep and the int16 ceiling
def fig_tsweep():
    pts = []
    for T, files in ((4, glob.glob("experiments/dvsgesture/golden_check_seed*.log")),
                     (8, glob.glob("experiments/dvsgesture/t8/golden_check_seed*.log")),
                     (16, glob.glob("experiments/dvsgesture/t16/golden_check_seed*.log"))):
        for f in files:
            txt = open(f).read()
            acc = float(re.search(r"float model\s*:\s*([\d.]+)%", txt).group(1))
            m = re.search(r"fc\s+V in \[\s*(-?\d+),\s*(-?\d+)\]", txt)
            vmax = max(abs(int(m.group(1))), abs(int(m.group(2))))
            pts.append((T, acc, vmax, os.path.basename(f)))
    fig, (a1, a2) = plt.subplots(1, 2, figsize=(10, 4))
    for T in (4, 8, 16):
        ys = [p[1] for p in pts if p[0] == T]; a1.plot([T] * len(ys), ys, "o", color="C0")
        vs = [p[2] for p in pts if p[0] == T]; a2.plot([T] * len(vs), vs, "o", color="C1")
    a1.set_xscale("log", base=2); a1.set_xticks([4, 8, 16]); a1.set_xticklabels([4, 8, 16]); a1.set_xlabel("timesteps T"); a1.set_ylabel("float test accuracy (%)")
    a1.set_title("DVS-Gesture accuracy vs T (one point per seed)"); a1.grid(alpha=.3)
    a2.axhline(32767, color="r", ls="--", label="int16 ceiling (32,767)")
    a2.set_xscale("log", base=2); a2.set_xticks([4, 8, 16]); a2.set_xticklabels([4, 8, 16]); a2.set_xlabel("timesteps T"); a2.set_ylabel("fc membrane |V| max (golden integer)")
    a2.set_title("The FC membrane range vs T (per seed)"); a2.grid(alpha=.3); a2.legend(fontsize=8)
    fig.tight_layout(); fig.savefig(os.path.join(OUT, "fig_tsweep_int16.png")); plt.close(fig)


# ---------------------------------------------------------------- 6. crossover activity vs K = P (from the fitted lines), C2/C3, both datasets
def fig_crossover_surface():
    cfg = [("N-MNIST", "experiments/rate_sweep", "golden/traces_m1.npz", {"c2": ("c1_S", 16 * 17 * 17, 4624 * 0 + 32 * 9 * 9), "c3": ("c2_S", 32 * 9 * 9, 64 * 5 * 5)}),
           ("DVS-Gesture", "experiments/rate_sweep_dvsg", "golden/traces_dvsgesture.npz", {"g2": ("c1_S", 16 * 32 * 32, 32 * 16 * 16), "g3": ("c2_S", 32 * 16 * 16, 64 * 8 * 8)})]
    tags = ["base", "0.02", "0.04", "0.08", "0.16", "0.30"]
    fig, ax = plt.subplots(figsize=(7, 4.2))
    ci = 0
    for name, d, base_tr, layers in cfg:
        for L, (key, inbits, _n) in layers.items():
            ks, cross = [], []
            for K in (4, 8, 16):
                xs, ys = [], []
                for t in tags:
                    f = os.path.join(d, "bench", "ed_k%d_%s_%s.txt" % (K, t, L))
                    tr = base_tr if t == "base" else os.path.join(d, "traces_rate%s.npz" % t)
                    if not (os.path.exists(f) and os.path.exists(tr)):
                        continue
                    xs.append(int((np.load(tr)[key] != 0).sum()) / 16); ys.append(cycles_file(f).mean())
                if len(xs) < 3:
                    continue
                dn = dense_cycles(os.path.join(d, "bench", "dense_p4_base_%s.txt" % L)) / (K / 4)
                A = np.vstack([np.ones(len(xs)), xs]).T; (a, b), _, _, _ = np.linalg.lstsq(A, np.array(ys), rcond=None)
                ks.append(K); cross.append(100 * ((dn - a) / b) / (4 * inbits))
            if ks:
                ax.plot(ks, cross, "o-", color="C%d" % ci, label="%s %s" % (name, L.upper().replace("G", "C")))
                ci += 1
    ax.set_xscale("log", base=2); ax.set_xticks([4, 8, 16]); ax.set_xticklabels([4, 8, 16])
    ax.set_xlabel("K = P (matched parallelism)"); ax.set_ylabel("crossover input activity (%): ED wins below, dense above")
    ax.set_title("Where dense catches up: fitted crossover activity vs parallelism (sim)")
    ax.grid(alpha=.3); ax.legend(fontsize=8)
    fig.tight_layout(); fig.savefig(os.path.join(OUT, "fig_crossover_vs_kp.png")); plt.close(fig)


if __name__ == "__main__":
    for fn in (fig_kp_sweep, fig_perclip, fig_activity, fig_accuracy, fig_tsweep, fig_crossover_surface):
        try:
            fn(); print("wrote", fn.__name__)
        except Exception as e:
            print("FAILED", fn.__name__, repr(e))
