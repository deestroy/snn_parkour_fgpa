"""Block diagrams for the thesis (Chapters 1, 2, 4, 5).

Run: python3 experiments/figures/make_diagrams.py
Writes experiments/figures/diagrams/*.svg and *.png (same drawing; the SVG is
the editable one). These are SCHEMATICS -- unlike make_figures.py they carry no
measured data, so nothing here needs regenerating when results change; edit the
drawing code, not the file. Numbers that do appear (cycle-model terms, widths,
resource counts) are labels, and each says where it comes from.
"""
import os
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import FancyBboxPatch, FancyArrowPatch, Rectangle

REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
OUT = os.path.join(REPO, "experiments", "figures", "diagrams")
os.makedirs(OUT, exist_ok=True)

ED, DENSE, MEM, HOST, FAB, NEUT = "#cfe3f5", "#fde3cc", "#e6e6e6", "#e8f0e0", "#f5f0d8", "#ffffff"
EDGE = "#333333"


def canvas(w=100, h=60, figsize=(11, 6.6), y0=0):
    """y0 crops unused space at the bottom of the drawing area."""
    fig, ax = plt.subplots(figsize=figsize)
    ax.set_xlim(0, w); ax.set_ylim(y0, h); ax.axis("off")
    return fig, ax


def box(ax, x, y, w, h, label, sub=None, fc=NEUT, fs=9, bold=False, dash=False, ec=EDGE):
    ax.add_patch(FancyBboxPatch((x, y), w, h, boxstyle="round,pad=0.35,rounding_size=0.6",
                                fc=fc, ec=ec, lw=1.1, ls="--" if dash else "-", zorder=2))
    ax.text(x + w / 2, y + h / 2 + (0.9 if sub else 0), label, ha="center", va="center",
            fontsize=fs, fontweight="bold" if bold else "normal", zorder=3)
    if sub:
        ax.text(x + w / 2, y + h / 2 - 1.25, sub, ha="center", va="center", fontsize=fs - 1.8,
                color="#444444", zorder=3)


def arrow(ax, p, q, label=None, dashed=False, color=EDGE, rad=0.0, fs=7.5, lw=1.2, off=(0, 0.9)):
    ax.add_patch(FancyArrowPatch(p, q, arrowstyle="-|>", mutation_scale=11, lw=lw, color=color,
                                 ls="--" if dashed else "-", shrinkA=1, shrinkB=1,
                                 connectionstyle="arc3,rad=%.2f" % rad, zorder=4))
    if label:
        ax.text((p[0] + q[0]) / 2 + off[0], (p[1] + q[1]) / 2 + off[1], label, ha="center",
                va="center", fontsize=fs, color=color, zorder=5,
                bbox=dict(fc="white", ec="none", pad=0.6))


def region(ax, x, y, w, h, label, color="#888888", fs=8.5):
    ax.add_patch(Rectangle((x, y), w, h, fc="none", ec=color, lw=1.0, ls=(0, (5, 3)), zorder=1))
    ax.text(x + 0.6, y + h - 0.9, label, ha="left", va="top", fontsize=fs, color=color, style="italic", zorder=1)


def save(fig, name, caption):
    fig.text(0.5, 0.015, caption, ha="center", va="bottom", fontsize=7.4, color="#555555", wrap=True)
    fig.tight_layout(rect=(0, 0.035, 1, 1))
    for ext in ("svg", "png"):
        fig.savefig(os.path.join(OUT, "%s.%s" % (name, ext)), dpi=150)
    plt.close(fig)
    print("wrote", name)


# ------------------------------------------------------------------ 1. system
def d_system():
    fig, ax = canvas()
    region(ax, 1, 6, 22, 40, "development host (Mac)")
    region(ax, 26, 6, 70, 46, "ZedBoard (Zynq XC7Z020)")
    region(ax, 28, 8, 30, 30, "PS: dual-core ARM, bare metal")
    region(ax, 61, 8, 33, 30, "PL: fabric at 100 MHz")
    box(ax, 3, 30, 18, 9, "client", "host/uart_client.py\nvectors, CRC-32 framing", fc=HOST)
    box(ax, 3, 14, 18, 9, "golden model", "golden/ (int8 / int16)\nthe reference for every check", fc=HOST)
    box(ax, 30, 26, 26, 9, "conv_server.c (build 5)", "command loop, -DDATASET", fc=HOST)
    box(ax, 30, 12, 26, 8, "DDR via HP0", "input / output buffers", fc=MEM)
    box(ax, 63, 26, 29, 9, "AXIS wrapper  axis_conv", "framing, tick counter,\nENGINE / DATASET / N_ENGINES", fc=FAB, bold=True)
    box(ax, 63, 11, 13, 10, "ED engine", "K banks\n(ENGINE=1)", fc=ED)
    box(ax, 79, 11, 13, 10, "dense engine", "P lanes\n(ENGINE=0)", fc=DENSE)
    arrow(ax, (12, 30), (12, 23.5), "same vectors", off=(7.5, 0))
    arrow(ax, (21, 34.5), (30, 30.5), "framed UART,\nCRC-32", off=(0, 2.6))
    arrow(ax, (43, 26), (43, 20.5), "AXI DMA")
    arrow(ax, (56, 16), (63, 27), "AXI-Stream", off=(3.2, 0))
    arrow(ax, (69.5, 26), (69.5, 21.5))
    arrow(ax, (85.5, 26), (85.5, 21.5))
    ax.text(77.5, 3.2, "exactly one engine is built in; everything else is identical", ha="center", fontsize=8, style="italic", color="#555555")
    arrow(ax, (30, 26.5), (21, 30.5), dashed=True, label="results +\nengine ticks", rad=0.12, off=(0, -3.4))
    save(fig, "fig_system", "System overview. One wrapper, one host, one set of vectors; the engine is a build-time parameter, which is what makes the comparison same-fabric (D0021). Sections 4.1, 4.7.")


# ------------------------------------------------------------------ 2. toolflow
def d_toolflow():
    fig, ax = canvas(h=42, figsize=(12, 4.6), y0=7)
    steps = [("train", "snnTorch, GPU\ntrain/03_train.py", HOST), ("quantise", "int8, threshold 2^k\ntrain/05_quantise.py", HOST),
             ("golden model", "integer network\ngolden/", HOST), ("vectors", "inputs, expected,\nthreshold, exposure", HOST),
             ("testbench", "Icarus, bit-identity\nsim/run_*_tb.sh", FAB), ("baked RTL", "weights inlined\nsim/gen_weight_vh.py", FAB),
             ("synthesis", "Vivado on the VM\nbuild_engine.tcl", FAB), ("board", "SD boot, BURST\n8-16 samples", FAB)]
    checks = ["accuracy within\n~1 pp of float", "clip fraction\nreported", "membrane fits\nint16?", "corner exposure\nper set",
              "bit-identical\nto golden", "baked == tracked\nnpz", "WNS >= 0 or\nno card", "bit-identical\non silicon"]
    x = 1.5
    for i, ((t, s, c), chk) in enumerate(zip(steps, checks)):
        box(ax, x, 24, 10.6, 9, t, s, fc=c, bold=True)
        ax.plot([x + 5.3, x + 5.3], [24, 19], color="#888888", lw=0.9, ls=":")
        ax.text(x + 5.3, 17.5, chk, ha="center", va="top", fontsize=7, color="#1b5e20")
        if i:
            arrow(ax, (x - 1.6, 28.5), (x - 0.1, 28.5))
        x += 12.2
    ax.text(50, 38, "every arrow has a check; the golden model is the contract at each one", ha="center", fontsize=9.5, style="italic")
    ax.text(50, 9.5, "checks (all of them run by one command: check_all.sh, 33 checks)", ha="center", fontsize=8.5, color="#1b5e20", style="italic")
    save(fig, "fig_toolflow", "From training to silicon. Nothing moves to the next stage without a check against the golden model or the tool's own gate. Sections 4.1, 4.8, 5.6.")


# ------------------------------------------------------------------ 3. the two paradigms
def d_paradigms():
    fig, ax = canvas(h=52, figsize=(12, 6))
    ax.text(25, 49, "clock-driven (dense)", ha="center", fontsize=11, fontweight="bold")
    ax.text(75, 49, "event-driven", ha="center", fontsize=11, fontweight="bold")
    ax.plot([50, 50], [2, 47], color="#bbbbbb", lw=1)
    # dense
    box(ax, 4, 36, 18, 7, "input frame", "every position, every t", fc=MEM)
    box(ax, 4, 24, 18, 7, "P lanes", "walk ALL output neurons", fc=DENSE, bold=True)
    box(ax, 4, 12, 18, 7, "membrane + output", "per-lane banks", fc=MEM)
    arrow(ax, (13, 36), (13, 31.5)); arrow(ax, (13, 24), (13, 19.5))
    box(ax, 26, 22, 20, 12, "cost", "neurons x fan-in x T / P\n\ndata-INdependent:\nthe same every sample", fc="#fff6f0", fs=8.5)
    # event-driven
    box(ax, 54, 40, 17, 6, "input frame", fc=MEM)
    box(ax, 54, 31, 17, 6, "spike address list", "only positions that fired", fc=ED)
    box(ax, 54, 21, 17, 7, "scatter", "fan-out -> K banks", fc=ED, bold=True)
    box(ax, 54, 11, 17, 6, "sweep", "leak + threshold, ALL neurons", fc=ED)
    for y1, y2 in ((40, 37.5), (31, 28.5), (21, 17.5)):
        arrow(ax, (62.5, y1), (62.5, y2))
    box(ax, 75, 18, 21, 17, "cost", "2 N T          (sweep floor)\n+ 5.0 s        (queue)\n+ 71.7 s / K   (scatter)\n\ndata-dependent: s = spikes\nonly the scatter term / K", fc="#f0f6fc", fs=8.5)
    ax.text(50, 6, "The crossover exists because the sweep floor does not shrink with K, while the dense cost divides by P.",
            ha="center", fontsize=9, style="italic")
    save(fig, "fig_paradigms", "The two execution models and where their costs come from. Constants fitted in experiments/dvsgesture/latency_sim (they transfer across datasets and layers). Sections 2.2, 4.4, 4.5.")


# ------------------------------------------------------------------ 4. dense datapath
def d_dense():
    fig, ax = canvas(h=52, y0=6)
    region(ax, 2, 9, 94, 35, "conv_layer_p.v  (P lanes; baked variants conv_layer_p_c1 / _g1)")
    box(ax, 5, 30, 18, 8, "input spike memory", "1 bit per position", fc=MEM)
    box(ax, 5, 14, 18, 8, "weight ROM", "int8, baked\n(stepped addresses)", fc=MEM)
    for i, y in enumerate((32, 24, 16)):
        box(ax, 32, y, 17, 6.5, "lane %d" % i, "accumulate 3x3 x C_IN", fc=DENSE)
        arrow(ax, (23, 34 - i * 0.0), (32, y + 3.2)) if i == 0 else arrow(ax, (23, 33.5), (32, y + 3.2), rad=-0.12)
        arrow(ax, (23, 18), (32, y + 2.2), rad=0.1)
    ax.text(40.5, 12.0, "...  P lanes (P in {1,2,4,8,16})", ha="center", fontsize=8, style="italic")
    box(ax, 56, 22, 16, 9, "lif_update", "shared core\nleak, compare,\nsubtract", fc=FAB, bold=True)
    box(ax, 78, 30, 16, 7, "membrane bank", "int16, per lane", fc=MEM)
    box(ax, 78, 16, 16, 7, "output words", "banked per lane\n(C0035 rev 2)", fc=MEM)
    for y in (35.2, 27.2, 19.2):
        arrow(ax, (49, y), (56, 26.5), rad=0.08)
    arrow(ax, (72, 28), (78, 33)); arrow(ax, (72, 25), (78, 19.5))
    arrow(ax, (86, 30), (86, 23.5), dashed=True, label="V[n-1]", off=(4.5, 0))
    ax.text(50, 47.5, "Dense: 88.0 cycles per output neuron per T=4 inference, exactly 1/P. Latency is the same for every sample.",
            ha="center", fontsize=9.5, style="italic")
    save(fig, "fig_dense_datapath", "The clock-driven engine. It has the same LIF core, the same memory discipline and the same parallelism knob as the event-driven one; only the schedule differs. Section 4.4.")


# ------------------------------------------------------------------ 5. event-driven datapath
def d_ed():
    fig, ax = canvas(h=54)
    region(ax, 2, 4, 94, 42, "ed_conv_layer.v + ed_scatter.v  (K banks; baked variants ed_scatter_c1 / _g1 / _r1)")
    box(ax, 4, 32, 15, 8, "input frame", "T x C_IN x H x W", fc=MEM)
    box(ax, 4, 18, 15, 8, "spike address list", "worst-case sized:\nnever overflows (D0016)", fc=ED)
    arrow(ax, (11.5, 32), (11.5, 26.5), "fill")
    box(ax, 24, 20, 17, 14, "scatter unit", "decode (ch,row,col)\n-> 2x2 x C_OUT targets\nweight column fetch", fc=ED, bold=True)
    arrow(ax, (19, 22), (24, 25), "one spike\nper pump", off=(3.0, 3.2))
    for i, y in enumerate((34, 28, 22, 16)):
        box(ax, 47, y, 13, 5, "bank %d" % i if i < 3 else "bank K-1", fc=MEM, fs=8)
        arrow(ax, (41, 27), (47, y + 2.5), rad=0.06)
    ax.text(53.5, 12.5, "channel-interleaved: K updates land per cycle,\nno arbiter (K must divide C_OUT)", ha="center", fontsize=7.5, style="italic")
    box(ax, 66, 24, 15, 10, "sweep", "2 cycles / neuron\nleak, threshold,\nzero I at the read beat", fc=ED, bold=True)
    arrow(ax, (60, 27), (66, 28), "after all spikes", off=(0, 2.6))
    box(ax, 85, 25, 11, 8, "output words", "word-parallel\n(C0035)", fc=MEM)
    arrow(ax, (81, 29), (85, 29))
    box(ax, 66, 8, 30, 11, "cycles = 2NT + 5.0 s + 71.7 s / K", "sweep floor is K-independent;\nonly the scatter divides by K.\nFitted on DVS-Gesture, transfers to N-MNIST\n(per-spike constants within 2-4 %).", fc="#f0f6fc", fs=8)
    ax.text(50, 49.5, "Event-driven: work scales with the spike count s, but the sweep still visits every neuron every timestep.",
            ha="center", fontsize=9.5, style="italic")
    save(fig, "fig_ed_datapath", "The event-driven engine. The C0044 bug lived in the sweep's current-zero write, which was gated on the update pipeline's valid flag and so never cleared neuron 0. Sections 4.5, 4.6.")


# ------------------------------------------------------------------ 6. bank interleaving
def d_banks():
    fig, ax = canvas(h=48, figsize=(10.5, 4.9), y0=11)
    ax.text(50, 45, "One input spike touches at most a 2x2 block of output positions, in every output channel",
            ha="center", fontsize=10, fontweight="bold")
    # input grid
    ax.text(15, 39, "input frame (stride 2, 3x3 kernel)", ha="center", fontsize=8.5, style="italic")
    for r in range(5):
        for c in range(5):
            ax.add_patch(Rectangle((5 + c * 4, 18 + r * 4), 4, 4, fc="#f7f7f7", ec="#cccccc", lw=0.6))
    ax.add_patch(Rectangle((13, 26), 4, 4, fc="#ffd9d9", ec="#c62828", lw=1.4))
    ax.text(15, 28, "spike", ha="center", va="center", fontsize=7.5, color="#c62828")
    # output positions
    ax.text(46, 39, "output positions hit", ha="center", fontsize=8.5, style="italic")
    for r in range(2):
        for c in range(2):
            ax.add_patch(Rectangle((40 + c * 6, 26 + r * 6), 6, 6, fc="#ffe9d9", ec="#e65100", lw=1.2))
    arrow(ax, (20, 28), (39, 31), "fan-out")
    # channels striped over banks
    ax.text(78, 39, "output channels striped over K banks", ha="center", fontsize=8.5, style="italic")
    cols = ["#cfe3f5", "#d8ecd0", "#fde3cc", "#e7d9f2"]
    for i in range(8):
        k = i % 4
        ax.add_patch(Rectangle((62 + i * 4, 26), 4, 8, fc=cols[k], ec=EDGE, lw=0.8))
        ax.text(64 + i * 4, 30, "c%d" % i, ha="center", va="center", fontsize=7)
        ax.text(64 + i * 4, 24.2, "b%d" % k, ha="center", va="center", fontsize=6.5, color="#666666")
    arrow(ax, (53, 29), (61, 30))
    ax.text(78, 20.5, "K = 4 shown. Because consecutive channels live in different banks,\n"
                      "K read-modify-writes are issued per cycle with no arbitration and no conflict.\n"
                      "Cost: K adders and K bank ports; BRAM grows with K (12.5 tiles at K=4, 13.5 at K=8).",
            ha="center", va="top", fontsize=8)
    ax.text(15, 14, "Alternatives considered (D0017): arbitrated shared memory (stalls under load),\n"
                    "output-row interleave (conflicts on the 2x2 block), full replication (BRAM).",
            ha="left", va="top", fontsize=7.5, color="#555555", style="italic")
    save(fig, "fig_bank_interleave", "Membrane banking. The fan-out pattern of a stride-2 3x3 layer is what makes channel interleaving conflict-free by construction. Section 4.6.")


# ------------------------------------------------------------------ 7. LIF core
def d_lif():
    fig, ax = canvas(h=44, figsize=(10.5, 5.0), y0=-4)
    box(ax, 3, 24, 13, 7, "V[n-1]", "int16, from bank", fc=MEM)
    box(ax, 22, 7, 14, 6, "I[n]", "accumulated weights", fc=MEM, fs=8.5)
    box(ax, 22, 30, 14, 6, "V >> 3", "leak: beta = 0.875", fc=FAB)
    box(ax, 22, 21, 14, 6, "pending?", "V[n-1] > theta", fc=FAB)
    box(ax, 42, 24, 15, 8, "V - (V>>3)\n+ I - pending*theta", fc=FAB, bold=True, fs=8.5)
    box(ax, 64, 24, 12, 8, "V[n] > theta", "strict >", fc=FAB)
    box(ax, 82, 29, 13, 6, "spike s[n]", fc=ED)
    box(ax, 82, 18, 13, 6, "V[n] -> bank", fc=MEM)
    arrow(ax, (16, 28.5), (22, 32.5)); arrow(ax, (16, 26.5), (22, 24.5))
    arrow(ax, (36, 10), (44, 24), rad=0.12)
    arrow(ax, (36, 32), (42, 30)); arrow(ax, (36, 23.5), (42, 26.5))
    arrow(ax, (57, 28), (64, 28)); arrow(ax, (76, 29), (82, 31)); arrow(ax, (76, 26), (82, 22))
    ax.text(50, 39.5, "hdl/common/lif_update.v -- one combinational core, shared by both engines and the M2 neuron",
            ha="center", fontsize=9.5, fontweight="bold")
    ax.text(50, 3, "Three details are load-bearing for bit-exactness (D0002, D0007): the reset is by SUBTRACTION, it is applied one timestep\n"
                   "AFTER the crossing (pending is computed from the STORED membrane), and the comparison is strict >, not >=.\n"
                   "The leak is an arithmetic shift, so there is no multiplier anywhere in the datapath and DSP usage is 0 by construction.",
            ha="center", va="top", fontsize=8)
    save(fig, "fig_lif_core", "The neuron. Everything in both engines reduces to this core plus a schedule; it is verified once (M2) against snnTorch and the golden model. Sections 4.2, 5.2.")


# ------------------------------------------------------------------ 8. measurement boundary
def d_measurement():
    fig, ax = canvas(h=54, figsize=(11, 5.9))
    box(ax, 3, 29, 13, 8, "12 V supply", fc=HOST)
    box(ax, 22, 30.5, 9, 5, "shunt\n0.1 ohm", fc="#ffe0e0", fs=8)
    box(ax, 22, 20, 9, 6, "DMM\nmV mode", "0.1 mA resolution", fc="#ffe0e0", fs=8)
    arrow(ax, (26.5, 30.5), (26.5, 26.5), dashed=True)
    box(ax, 37, 29, 13, 8, "regulators", "5 V / 3.3 V / 1.8 V\n1.0 V core", fc=MEM)
    region(ax, 55, 13, 41, 36, "ZedBoard")
    box(ax, 58, 35, 16, 8, "PS7 (ARM, DDR)", "Vivado estimate\n1.533 W in every build", fc=HOST)
    box(ax, 58, 20, 16, 9, "PL fabric", "engine + wrapper\n48-270 mW estimated", fc=FAB, bold=True)
    box(ax, 78, 20, 15, 9, "N engines", "replicated x8 / x4 / x2\nto lift the delta (C0003)", fc=ED, fs=8)
    arrow(ax, (16, 33), (22, 33)); arrow(ax, (31, 33), (37, 33)); arrow(ax, (50, 33), (58, 38), rad=0.1); arrow(ax, (50, 32), (58, 25), rad=-0.1)
    arrow(ax, (74, 24.5), (78, 24.5))
    ax.plot([54, 54], [13, 50], color="#c62828", lw=1.6, ls="--")
    ax.text(54, 51, "what the meter sees (board input)", ha="center", fontsize=8.5, color="#c62828")
    ax.add_patch(Rectangle((56.5, 18), 38, 12, fc="none", ec="#1565c0", lw=1.4, ls=":"))
    ax.text(75.5, 16.4, "what report_power estimates (fabric only, vectorless activity)", ha="center", fontsize=8.5, color="#1565c0")
    ax.text(50, 1.5, "Three quantities that must not be merged (C0038): fabric delta per inference, board-input delta per inference,\n"
                     "and energy per control period at the robot's 10 Hz duty. The meter measures the middle one directly; the first\n"
                     "comes from the replicated-minus-single subtraction; the third multiplies board power by the period.",
            ha="center", va="bottom", fontsize=8)
    save(fig, "fig_measurement_boundary", "The measurement boundary. The gap between the red line and the blue box is the reason a tool estimate and a meter can disagree. Sections 1.1, 4.9, 6.5.")


# ------------------------------------------------------------------ 9. verification flow
def d_verification():
    fig, ax = canvas(h=46, figsize=(11, 5.2))
    box(ax, 4, 30, 16, 8, "trained npz", "int8 weights,\nthreshold 2^k", fc=HOST)
    box(ax, 4, 14, 16, 8, "golden model", "integer network\n+ Python ED engine", fc=HOST, bold=True)
    box(ax, 27, 30, 16, 8, "baked RTL", "gen_weight_vh.py", fc=FAB)
    box(ax, 27, 14, 16, 8, "vector set", "inputs, expected spikes,\nthreshold, exposure", fc=HOST)
    box(ax, 50, 22, 17, 9, "testbench", "compare EVERY\noutput word", fc=FAB, bold=True)
    box(ax, 74, 30, 21, 8, "AXIS harness", "hostile handshake,\n240/240 random seeds", fc=FAB)
    box(ax, 74, 14, 21, 8, "board", "same vectors over\nthe framed link", fc=FAB)
    arrow(ax, (20, 34), (27, 34)); arrow(ax, (20, 18), (27, 18))
    arrow(ax, (12, 30), (12, 22.5), "same npz", off=(6.5, 0))
    arrow(ax, (43, 33), (50, 29), rad=0.08); arrow(ax, (43, 18), (50, 24), rad=-0.08)
    arrow(ax, (67, 28), (74, 33), rad=0.08); arrow(ax, (67, 25), (74, 19), rad=-0.08)
    box(ax, 27, 2.5, 40, 7, "sim/check_baked_weights.py", "the baked tables must equal the tracked npz, entry for entry", fc="#eef7ee", fs=8)
    arrow(ax, (28.5, 30), (33, 9.8), dashed=True, color="#1b5e20", rad=-0.32)
    arrow(ax, (12, 14), (30, 7.5), dashed=True, color="#1b5e20", rad=0.18)
    ax.text(82, 6, "bit-identical, never 'close'", ha="center", fontsize=10, style="italic", color="#1b5e20")
    ax.text(50, 42.5, "One reference, four consumers: any two disagreeing localises the fault immediately",
            ha="center", fontsize=10, fontweight="bold")
    save(fig, "fig_verification_flow", "The golden-model contract. Bit-identity proves the function; it does not prove port discipline, timing or toolchain behaviour, which is why the ladder also holds lints, corner sets and the hostile-handshake bench. Sections 4.8, 5.6.")


# ------------------------------------------------------------------ 10. perception loop
def d_perception():
    fig, ax = canvas(h=44, figsize=(11.5, 4.7), y0=1)
    ax.text(50, 41, "Simulation-in-the-loop: the perception budget is charged in wall-clock, never silently waited for",
            ha="center", fontsize=10, fontweight="bold")
    y = 30
    ax.annotate("", xy=(97, y), xytext=(4, y), arrowprops=dict(arrowstyle="-|>", color=EDGE, lw=1.2))
    ax.text(50, y - 9.5, "time", ha="center", fontsize=8, color="#666666")
    for i in range(4):
        x = 8 + i * 22
        ax.plot([x, x], [y - 1.5, y + 1.5], color=EDGE, lw=1.2)
        ax.text(x, y + 2.6, "camera frame %d" % i, ha="center", fontsize=7.5)
        ax.add_patch(Rectangle((x, y - 6.5), 6.5, 4, fc=ED, ec=EDGE, lw=0.9))
        ax.text(x + 3.2, y - 4.5, "encoder", ha="center", va="center", fontsize=7)
        ax.add_patch(Rectangle((x + 6.5, y - 6.5), 3, 4, fc=HOST, ec=EDGE, lw=0.9))
        ax.text(x + 8, y - 4.5, "GRU", ha="center", va="center", fontsize=6.5)
    ax.text(8, y - 8.8, "10 Hz  ->  100 ms period", ha="left", fontsize=8, color="#555555")
    box(ax, 6, 8, 26, 9, "measured on the board", "ED K=4: 1.73 ms mean, 2.75 ms worst\ndense P=4: 3.60 ms flat\n(64 real event frames, sim)", fc="#f0f6fc", fs=8)
    box(ax, 36, 8, 26, 9, "budget", "worst frame = 2.7 % of the period\nboth engines meet 10 Hz with margin", fc="#eef7ee", fs=8)
    box(ax, 66, 8, 29, 9, "on a miss", "the policy uses the STALE latent;\nphysics never waits -> a miss is an\nerror in the trajectory, not a pause", fc="#fff6f0", fs=8)
    ax.text(50, 3.5, "The encoder is what runs on the FPGA; the GRU and the MLP policy stay on the host. Because physics is lockstep,\n"
                     "a late latent is stale rather than skipped, which is what makes latency a correctness constraint.",
            ha="center", va="bottom", fontsize=8)
    save(fig, "fig_perception_loop", "The perception loop and its deadline. Latency numbers from experiments/p1_distill and the board records. Sections 4.10, 6.8.")


if __name__ == "__main__":
    for fn in (d_system, d_toolflow, d_paradigms, d_dense, d_ed, d_banks, d_lif, d_measurement, d_verification, d_perception):
        try:
            fn()
        except Exception as e:
            print("FAILED", fn.__name__, repr(e))
