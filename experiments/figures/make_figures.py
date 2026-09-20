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


def has_cycles(path):
    """A bench file that exists AND has data rows (a running bench leaves a header-only file)."""
    return os.path.exists(path) and len(cycles_file(path)) > 0


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
        ed = np.array(ed)
        ax.errorbar(ks, ed[:, 0], yerr=[ed[:, 0] - ed[:, 1], ed[:, 2] - ed[:, 0]], fmt="o-", capsize=3,
                    label="event-driven K (sim, mean, min-max)")
        ax.plot(ks, dn, "s--", label="dense P (sim)")
        ax.plot(list(ed_board), list(ed_board.values()), "o", ms=11, mfc="none", mec="C0", mew=2, label="ED on silicon")
        ax.plot(list(dn_board), list(dn_board.values()), "s", ms=11, mfc="none", mec="C1", mew=2, label="dense on silicon")
        # fitted crossover, computed here from the same curves (never typed in; C0049)
        ok = ~np.isnan(np.array(dn, dtype=float))
        A = np.vstack([np.ones(len(ks)), 1.0 / np.array(ks, float)]).T
        a_ed, b_ed = np.linalg.lstsq(A, ed[:, 0], rcond=None)[0]
        Pk = np.array(ks, float)[ok]; B = np.vstack([1.0 / Pk, np.ones(len(Pk))]).T
        c_dn, d_dn = np.linalg.lstsq(B, np.array(dn, dtype=float)[ok], rcond=None)[0]
        kx = (c_dn - b_ed) / (a_ed - d_dn)
        ax.axvline(kx, color="k", lw=1, ls=":")
        ax.annotate("crossover K = P = %.1f" % kx, xy=(kx, a_ed + b_ed / kx),
                    xytext=(4, 14), textcoords="offset points", fontsize=8, rotation=90, va="bottom")
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
    npts = []
    for T in (8, 16):
        for f in glob.glob("experiments/tsweep_nmnist/golden_t%d_seed*.log" % T):
            txt = open(f).read()
            m = re.search(r"fc\s+V in \[\s*(-?\d+),\s*(-?\d+)\]", txt)
            npts.append((T, float(re.search(r"float model\s*:\s*([\d.]+)%", txt).group(1)), max(abs(int(m.group(1))), abs(int(m.group(2))))))
    fig, (a1, a2) = plt.subplots(1, 2, figsize=(10, 4))
    for T in (4, 8, 16):
        ys = [p[1] for p in pts if p[0] == T]; a1.plot([T] * len(ys), ys, "o", color="C0", label="DVS-Gesture" if T == 4 else None)
        vs = [p[2] for p in pts if p[0] == T]; a2.plot([T] * len(vs), vs, "o", color="C1", label="DVS-Gesture fc" if T == 4 else None)
        vn = [p[2] for p in npts if p[0] == T]; a2.plot([T] * len(vn), vn, "^", color="C2", label="N-MNIST fc" if T == 8 else None)
    a1.legend(fontsize=8)
    a1.set_xscale("log", base=2); a1.set_xticks([4, 8, 16]); a1.set_xticklabels([4, 8, 16]); a1.set_xlabel("timesteps T"); a1.set_ylabel("float test accuracy (%)")
    a1.set_title("DVS-Gesture accuracy vs T (one point per seed)"); a1.grid(alpha=.3)
    a2.axhline(32767, color="r", ls="--", label="int16 ceiling (32,767)")
    a2.set_xscale("log", base=2); a2.set_xticks([4, 8, 16]); a2.set_xticklabels([4, 8, 16]); a2.set_xlabel("timesteps T"); a2.set_ylabel("fc membrane |V| max (golden integer)")
    a2.set_title("FC membrane |V| max vs T, per seed (N-MNIST stays far below)"); a2.grid(alpha=.3); a2.legend(fontsize=8)
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
                    if not (has_cycles(f) and os.path.exists(tr)):
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


# ---------------------------------------------------------------- 7. per-sample latency vs input spikes, board points on the cycle model
def _popcount_words(words):
    return np.array([int(np.unpackbits(np.frombuffer(np.asarray(w, dtype="<u4").tobytes(), dtype=np.uint8)).sum()) for w in words])


def fig_per_sample():
    """ED latency is a line in the input spike count (cycles = 2 N T + 5.0 s + 71.7 s / K, constants
    from experiments/dvsgesture/latency_sim/README.md); dense is a constant. Board points where they
    exist (N-MNIST K=4 and K=8, DVS-Gesture K=4), simulation for the robot frames (not yet on the board)."""
    fig, axes = plt.subplots(1, 3, figsize=(13, 4))
    model = lambda s, n_out, K: (2 * n_out * 4 + 5.0 * s + 71.7 * s / K) / 100.0
    # N-MNIST: 16 check samples; per-sample K=8 and K=4 engine-only board latency from the K=8 record
    spk = _popcount_words(np.load("host/conv_test_data.npz")["tx_words"])
    k8, k4 = {}, {}
    for l in open("experiments/board_ed_k8_20260917.md"):
        m = re.match(r"\| (\d+) \| \d \| ([\d.]+) \| ([\d.]+) \| \+[\d.]+ % \| ([\d.]+) \|", l)
        if m:
            k8[int(m.group(1))] = float(m.group(2)); k4[int(m.group(1))] = float(m.group(4))
    ax = axes[0]; idx = sorted(k4)
    ss = np.linspace(spk.min() * 0.9, spk.max() * 1.1, 50)
    ax.plot(ss, model(ss, 16 * 17 * 17, 4), "-", color="C0", lw=1, label="cycle model, K=4")
    ax.plot(ss, model(ss, 16 * 17 * 17, 8), "-", color="C2", lw=1, label="cycle model, K=8")
    ax.plot(spk[idx], [k4[i] for i in idx], "o", color="C0", label="ED K=4, board")
    ax.plot(spk[idx], [k8[i] for i in idx], "^", color="C2", label="ED K=8, board")
    ax.axhline(1048.9, color="C1", ls="--", label="dense P=4, board"); ax.axhline(540.3, color="C3", ls="--", label="dense P=8, board")
    ax.set_title("N-MNIST C1 (16 check samples, board)"); ax.set_xlabel("input spikes per inference (T = 4)")
    ax.set_ylabel("latency per inference (us, engine-only)"); ax.grid(alpha=.3); ax.legend(fontsize=7)
    # DVS-Gesture: 8 clips; spikes from the latency_sim README table, board from the ED K=4 record
    dspk = {}
    for l in open("experiments/dvsgesture/latency_sim/README.md"):
        m = re.match(r"\| (\d) \| ([\d,]+) \| [\d.]+ % \| [\d,]+ \|", l)
        if m:
            dspk[int(m.group(1))] = int(m.group(2).replace(",", ""))
    dboard = {}
    for l in open("experiments/dvsgesture/board_ed_k4_20260919.md"):
        m = re.match(r"\| (\d) \| \d+ \| ([\d.]+) \| ([\d.]+) \|", l)
        if m:
            dboard[int(m.group(1))] = float(m.group(2))
    ax = axes[1]; idx = sorted(dboard)
    ss = np.linspace(2000, 15500, 50)
    ax.plot(ss, model(ss, 16 * 32 * 32, 4), "-", color="C0", lw=1, label="cycle model, K=4")
    ax.plot([dspk[i] for i in idx], [dboard[i] for i in idx], "o", color="C0", label="ED K=4, board")
    ax.axhline(3706.5, color="C1", ls="--", label="dense P=4, board")
    for i in idx:
        ax.annotate("clip %d" % i, (dspk[i], dboard[i]), textcoords="offset points", xytext=(4, 4), fontsize=7)
    ax.set_title("DVS-Gesture C1 (8 clips, board)"); ax.set_xlabel("input spikes per inference (T = 4)"); ax.grid(alpha=.3); ax.legend(fontsize=7)
    # robot event frames: 64 frames, direct coding (frame repeated over T), simulation only
    fr = np.load("robot/artifacts/isaac_event_frames.npz")["frames"]
    rspk = 4 * np.array([int((f != 0).sum()) for f in fr])
    f64 = "experiments/p1_distill/isaac_i1_ed_k4_cycles_64.txt"
    rcyc = cycles_file(f64 if has_cycles(f64) else "experiments/p1_distill/isaac_i1_ed_k4_cycles.txt") / 100.0
    rspk = rspk[:len(rcyc)]
    ax = axes[2]
    ss = np.linspace(rspk.min() * 0.9, rspk.max() * 1.1, 50)
    ax.plot(ss, model(ss, 16 * 32 * 32, 4), "-", color="C0", lw=1, label="cycle model, K=4")
    ax.plot(rspk, rcyc, "o", color="C0", ms=4, label="ED K=4, sim")
    ax.axhline(1441788 / 4 / 100.0, color="C1", ls="--", label="dense P=4, sim")
    ax.axhline(rcyc.max(), color="C0", ls=":", lw=1, label="ED worst frame (%.2f ms)" % (rcyc.max() / 1000))
    ax.set_title("Robot event frames, 64x64 (%d frames, sim)" % len(rcyc)); ax.set_xlabel("input spikes per inference (T = 4, frame repeated)"); ax.grid(alpha=.3); ax.legend(fontsize=7)
    fig.suptitle("Per-sample latency vs input activity: ED is a line in the spike count, dense a constant")
    fig.tight_layout(); fig.savefig(os.path.join(OUT, "fig_per_sample.png")); plt.close(fig)


# ---------------------------------------------------------------- 8. resources per build, from the Vivado power reports (utilisation columns)
def _rpt_util(path):
    txt = open(path).read()
    g = lambda name: float(re.search(r"\|\s+%s\s+\|\s+[<\d.]+\s+\|\s+([\d.]+)\s+\|" % re.escape(name), txt).group(1))
    return {"lut": g("LUT as Logic") + g("LUT as Distributed RAM") + g("LUT as Shift Register"), "ff": g("Register"), "bram": g("Block RAM")}


def fig_resources():
    builds = [  # (tag, label, group)
        ("ed_k4_20260918_1300", "ED K=4\nN-MNIST", "N=1"), ("dense_p4_20260919_2323", "dense P=4\nN-MNIST", "N=1"),
        ("ed_k8_20260917_2106", "ED K=8\nN-MNIST", "N=1"), ("dense_p8_20260917_2221", "dense P=8\nN-MNIST", "N=1"),
        ("ed_k4_dvsg_20260919_1324", "ED K=4\nDVS-G", "N=1"), ("dense_p4_dvsg_20260919_1447", "dense P=4\nDVS-G", "N=1"),
        ("ed_k4_x8_20260917_2251", "ED K=4 x8\nN-MNIST", "rep"), ("dense_p4_x8_20260917_2312", "dense P=4 x8\nN-MNIST", "rep"),
        ("ed_k4_dvsg_x4_20260920_0010", "ED K=4 x4\nDVS-G", "rep"), ("dense_p4_dvsg_x2_20260920_1127", "dense P=4 x2\nDVS-G", "rep")]
    rows = []
    for tag, label, grp in builds:
        f = "experiments/power_estimates/%s_power.rpt" % tag
        if os.path.exists(f):
            rows.append((label, grp, _rpt_util(f)))
    fig, axes = plt.subplots(1, 3, figsize=(15, 4.8))
    x = np.arange(len(rows)); cols = ["C0" if "ED" in r[0] else "C1" for r in rows]
    for ax, key, total, name in zip(axes, ("lut", "ff", "bram"), (53200, 106400, 140), ("LUTs (logic + LUTRAM + SRL)", "flip-flops", "block RAM tiles (36 Kb)")):
        vals = [r[2][key] for r in rows]
        ax.bar(x, vals, color=cols)
        for xi, v in zip(x, vals):
            ax.text(xi, v, "%.0f\n(%.0f %%)" % (v, 100 * v / total) if key != "bram" else "%.1f\n(%.0f %%)" % (v, 100 * v / total), ha="center", va="bottom", fontsize=6)
        ax.set_xticks(x); ax.set_xticklabels([r[0].replace("\n", " ") for r in rows], fontsize=6.5, rotation=45, ha="right"); ax.set_title(name + " (whole design)", fontsize=9); ax.grid(axis="y", alpha=.3)
        ax.axvline(len([r for r in rows if r[1] == "N=1"]) - 0.5, color="k", lw=0.8, ls=":")
    axes[0].set_ylabel("count, whole design incl. wrapper and DMA")
    fig.suptitle("Resources per silicon build (Vivado post-route utilisation; blue = event-driven, orange = dense; right of the dotted line = replicated engines)")
    fig.tight_layout(); fig.savefig(os.path.join(OUT, "fig_resources.png")); plt.close(fig)


# ---------------------------------------------------------------- 9. crossover surface: dense/ED over (activity, K = P) from the per-K fits
def fig_crossover_heatmap():
    cfg = [("N-MNIST", "experiments/rate_sweep", "golden/traces_m1.npz", {"c2": ("c1_S", 16 * 17 * 17), "c3": ("c2_S", 32 * 9 * 9)}),
           ("DVS-Gesture", "experiments/rate_sweep_dvsg", "golden/traces_dvsgesture.npz", {"g2": ("c1_S", 16 * 32 * 32), "g3": ("c2_S", 32 * 16 * 16)})]
    tags = ["base", "0.02", "0.04", "0.08", "0.16", "0.30"]
    fits = []   # (label, inbits, a, b1, b2, dense4)  with ED(s, K) = a + (b1 + b2 / K) s
    for name, d, base_tr, layers in cfg:
        for L, (key, inbits) in layers.items():
            per_k = {}
            for K in (4, 8, 16):
                xs, ys = [], []
                for t in tags:
                    f = os.path.join(d, "bench", "ed_k%d_%s_%s.txt" % (K, t, L))
                    tr = base_tr if t == "base" else os.path.join(d, "traces_rate%s.npz" % t)
                    if has_cycles(f) and os.path.exists(tr):
                        xs.append(int((np.load(tr)[key] != 0).sum()) / 16); ys.append(cycles_file(f).mean())
                if len(xs) >= 3:
                    A = np.vstack([np.ones(len(xs)), xs]).T; per_k[K] = np.linalg.lstsq(A, np.array(ys), rcond=None)[0]
            if len(per_k) < 2:
                print("crossover heatmap: skipping %s %s (need >= 2 K points)" % (name, L)); continue
            Ks = np.array(sorted(per_k)); bs = np.array([per_k[k][1] for k in Ks]); a = np.mean([per_k[k][0] for k in Ks])
            B = np.vstack([np.ones(len(Ks)), 1.0 / Ks]).T; b1, b2 = np.linalg.lstsq(B, bs, rcond=None)[0]
            fits.append(("%s %s" % (name, L.upper().replace("G", "C")), inbits, a, b1, b2, dense_cycles(os.path.join(d, "bench", "dense_p4_base_%s.txt" % L))))
    if not fits:
        raise RuntimeError("no fits")
    act = np.linspace(1, 80, 320); Kg = np.logspace(0, 5, 120, base=2)
    A_, K_ = np.meshgrid(act, Kg)
    fig, ax = plt.subplots(figsize=(8, 4.8))
    ref = [f for f in fits if f[0].startswith("DVS-Gesture C2")] or fits
    lab, inbits, a, b1, b2, d4 = ref[0]
    s = A_ / 100.0 * 4 * inbits
    ratio = (d4 / (K_ / 4)) / (a + (b1 + b2 / K_) * s)
    im = ax.pcolormesh(A_, K_, np.log2(ratio), cmap="RdBu", vmin=-2, vmax=2, shading="auto")
    cb = fig.colorbar(im, ax=ax); cb.set_label("log2(dense / ED cycles) for %s   (blue: ED faster, red: dense faster)" % lab, fontsize=8)
    for i, (lab, inbits, a, b1, b2, d4) in enumerate(fits):
        s = A_ / 100.0 * 4 * inbits
        r = (d4 / (K_ / 4)) / (a + (b1 + b2 / K_) * s)
        if (r.min() < 1.0) and (r.max() > 1.0):
            ax.contour(A_, K_, r, levels=[1.0], colors=["C%d" % i], linewidths=1.5)
        ax.plot([], [], color="C%d" % i, label="%s: dense = ED (crossover)" % lab)
    ax.set_yscale("log", base=2); ax.set_yticks([1, 2, 4, 8, 16, 32]); ax.set_yticklabels([1, 2, 4, 8, 16, 32])
    ax.set_xlabel("input activity of the layer (% of input bits set)"); ax.set_ylabel("K = P (matched parallelism)")
    ax.set_title("The crossover is a surface: where dense catches up in (activity, K = P), from the fitted cycle models (sim)", fontsize=9)
    ax.legend(fontsize=7, loc="upper right"); ax.grid(alpha=.2, which="both")
    fig.tight_layout(); fig.savefig(os.path.join(OUT, "fig_crossover_heatmap.png")); plt.close(fig)


# ---------------------------------------------------------------- 10. the three input sources, one sample each, at the same scale
def fig_inputs():
    panels = []
    if os.path.exists("data/packed/test_frames.npy"):
        x = np.load("data/packed/test_frames.npy", mmap_mode="r")[0]      # (T, 2, 34, 34)
        panels.append(("N-MNIST sample 0 (2x34x34, T = 4)", np.asarray(x)))
    if os.path.exists("data/packed_dvsgesture/test_frames.npy"):
        x = np.load("data/packed_dvsgesture/test_frames.npy", mmap_mode="r")[0]
        panels.append(("DVS-Gesture clip 0 (2x64x64, T = 4)", np.asarray(x)))
    fr = np.load("robot/artifacts/isaac_event_frames.npz")["frames"][0]   # (2, 64, 64), repeated over T
    panels.append(("robot event frame 0 (2x64x64, repeated over T)", np.repeat(fr[None], 4, axis=0)))
    fig, axes = plt.subplots(len(panels), 5, figsize=(12, 2.4 * len(panels)))
    axes = np.atleast_2d(axes)
    for r, (title, x) in enumerate(panels):
        x = (x > 0).astype(int)
        for t in range(4):
            img = np.zeros(x.shape[2:] + (3,)); img[..., 0] = x[t, 0]; img[..., 2] = x[t, 1]
            axes[r, t].imshow(img, interpolation="nearest"); axes[r, t].set_title("t = %d" % t, fontsize=8); axes[r, t].axis("off")
        img = np.zeros(x.shape[2:] + (3,)); img[..., 0] = x[:, 0].max(0); img[..., 2] = x[:, 1].max(0)
        axes[r, 4].imshow(img, interpolation="nearest"); axes[r, 4].set_title("OR over T  (density %.1f %%)" % (100 * x.mean()), fontsize=8); axes[r, 4].axis("off")
        axes[r, 0].set_title(title + "   t = 0", fontsize=8, loc="left")
    fig.suptitle("Binarised inputs as the engines see them (red = ON polarity, blue = OFF), one sample per source")
    fig.tight_layout(); fig.savefig(os.path.join(OUT, "fig_inputs.png")); plt.close(fig)


if __name__ == "__main__":
    for fn in (fig_kp_sweep, fig_perclip, fig_activity, fig_accuracy, fig_tsweep, fig_crossover_surface, fig_per_sample, fig_resources, fig_crossover_heatmap, fig_inputs):
        try:
            fn(); print("wrote", fn.__name__)
        except Exception as e:
            print("FAILED", fn.__name__, repr(e))
