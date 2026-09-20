"""Builds docs/thesis_outline.docx (the .docx is UNTRACKED via .git/info/exclude; this generator is tracked) and a dated
copy in the user's OneDrive 'Final_thesis_images' folder. Merges the
2026-08-20 template form (title page, 'Write in this section' guidance +
prose placeholder under every heading, live ToC/list fields) with the
current results. Edit OUTLINE, bump REVISED, re-run.
Tags in bullets: RESULT = a number that exists; TODO = not yet; WHERE = file.
"""
import os, re, shutil
from docx import Document
from docx.shared import Pt, RGBColor
from docx.enum.text import WD_ALIGN_PARAGRAPH, WD_BREAK
from docx.oxml.ns import qn
from docx.oxml import OxmlElement

REVISED = "2026-09-20f"
ONEDRIVE = os.path.expanduser("~/OneDrive - Carleton University/Research Papers/Final_thesis_images")
GREEN, RED, BLUE = RGBColor(0x1B, 0x5E, 0x20), RGBColor(0xB7, 0x1C, 0x1C), RGBColor(0x0D, 0x47, 0xA1)
PURPLE, ORANGE = RGBColor(0x6A, 0x1B, 0x9A), RGBColor(0xE6, 0x51, 0x00)

ACRONYMS = [
    "SNN — Spiking Neural Network", "LIF — Leaky Integrate-and-Fire", "ANN — Artificial Neural Network",
    "FPGA — Field-Programmable Gate Array", "PS / PL — Processing System / Programmable Logic (Zynq)",
    "LUT / FF / BRAM / DSP — FPGA primitive resources", "WNS / WHS — Worst Negative / Hold Slack",
    "AXI / AXIS — Advanced eXtensible Interface (memory-mapped / streaming)", "DMA — Direct Memory Access",
    "UART — Universal Asynchronous Receiver-Transmitter", "CRC — Cyclic Redundancy Check",
    "HDL / RTL — Hardware Description Language / Register-Transfer Level", "DVS — Dynamic Vision Sensor (event camera)",
    "ED — event-driven (datapath)", "K — event-driven bank count; P — dense lane count; T — timesteps per inference",
    "DAgger — Dataset Aggregation (imitation learning)", "PPO — Proximal Policy Optimization", "GRU — Gated Recurrent Unit",
    "DMM — Digital Multimeter", "INA226 — a current/power monitor IC", "MASc — Master of Applied Science",
]

# (level, title, [bullets]); level 0 = Heading 1, 1 = Heading 2
# Bullet tags: RESULT (a number that exists), TODO (not yet), WHERE (file), FIG (recommended figure),
# TAB (recommended table). FIG/TAB bullets start with [exists] or [todo] and are collected into the
# 'Figure and Table Plan' after the List of Figures.
OUTLINE = [
(0, "Abstract", [
    "One paragraph (150-300 words), written last, in this order: the gap (SNN energy claims rest on tool estimates), what was built (dense and event-driven datapaths behind one wrapper on a Zynq-7020, bit-identical to a golden model on two datasets), how it was verified (33-check ladder, 14 silicon passes, zero misses), the two crossovers (parallelism, activity), the measured energy and its gap to the estimate, the perception workload.",
    "RESULT: numbers to quote once final: ED K=4 beats dense P=4 by 1.52x on silicon (688.5 vs 1,048.9 us); dense wins at K=P=8 (540.3 vs 575.5 us); on DVS-Gesture ED wins 6 of 8 clips on silicon and loses the two densest (1.248x at the mean); accuracy 96.6-97.0 % N-MNIST, 63-69 % DVS-Gesture; robot frames ED 1.86 ms mean / 2.52 worst vs dense 3.60 ms.",
    "TODO: the measured-energy sentence (meter) and the student's success rates. No citations, figures or unexpanded acronyms in the abstract.",
]),
(0, "Acknowledgements", [
    "Supervisor (Dr. Ahmadi), committee, the lab's GPU hosts (MI210 box, 1080 Ti box), whoever lends the DMM, the extreme-parkour and snnTorch authors for released code. One page.",
]),
(0, "List of Acronyms", ACRONYMS),
(0, "1  Introduction", [
    "Open wide, then narrow: SNNs are justified by an energy argument; the field's numbers are overwhelmingly tool estimates; the one careful measurement (Loihi 2 vs GPU: 3-3.5 W vs > 50 W, power not energy) shows how estimates and measurements can diverge. This thesis builds both canonical datapaths on one fabric and measures.",
    "End with the one-sentence thesis: on this fabric the event-driven datapath wins latency at matched parallelism K=P=4 and loses at K=P=8; on real data it wins below ~30 % input activity and loses above; whether it wins ENERGY is answered with a meter, not a model.",
    "Keep the chapter under 8 pages; every claim here is repeated with evidence in Chapter 6, so cite forward ('Section 6.4') rather than argue.",
]),
(1, "1.1  Motivation", [
    "Energy per inference is the figure of merit; power alone misleads (a chip that draws 17x less power but is 27x slower uses more energy). Define energy per inference, latency, deadline-miss rate, and the three energy quantities that must be kept apart (C0038: fabric delta, board delta, per-inference at duty).",
    "The estimation problem: tool estimates count arithmetic and under-weight memory traffic, static power and time; the baseline table shows four of five surveyed FPGA accelerators reporting a Vivado estimate as their power method and none measuring at a board input (docs/baseline_table.md).",
    "Why an FPGA: same fabric, toolchain, wrapper, host and vectors for both datapaths -- the only variable is the datapath (D0011, D0021). Why a robot workload: latency is a correctness constraint for a learned quadruped perception policy (ES-Parkour, ICME 2025); the same encoder is trained in the paper's own simulator.",
    "State early what 'measured' means here: current at the board's 12 V input with a shunt, idle-run-idle deltas, replicated engines to lift the delta above the meter's floor (C0001-C0003). Everything before Section 6.5 is cycles or a tool estimate, and the text must say so each time.",
    "FIG: [todo] Measurement-boundary diagram: 12 V input -> regulators -> PS (ARM, DDR) and PL (fabric) -> engine; shade what a Vivado report covers vs what the shunt sees (C0004, C0026, C0038). One figure, reused in 4.9 and 6.5.",
    "TAB: [todo] The three energy quantities (C0038): name, definition, what it includes, how obtained (delta at fabric, delta at board input, per inference at the control-loop duty), and which sections report each.",
]),
(1, "1.2  Problem Statement and Research Questions", [
    "Prior work positioned fairly: FPGA SNNs on quadrupeds exist (Guerra-Hernandez et al. 2017, 6 hand-designed neurons, no camera); FPGA SNN accelerators are mature but report ESTIMATED energy. No 'first' claims; the difference is a real learned vision network (58k-122k parameters) and measurement rather than demonstration.",
    "Research questions: RQ1 at matched parallelism, at what activity does event-driven stop beating dense, in cycles and measured energy? RQ2 how far is the tool estimate from the meter, per datapath, and does the tool rank the two designs the same way the meter does (C0027)? RQ3 does the mean-latency verdict survive the worst-case (deadline) one?",
    "Hypotheses written before the data, with where each was tested: H1 ED wins latency at K=P=4 and loses at K=P=8 (silicon, held); H2 the per-clip activity crossover is a sharp threshold in input spike count (silicon, held at ~10,000 spikes); H3 the tool favours ED by 2-3x in energy but the meter by 1.1-1.4x (P2 of the metering prereg, open).",
    "Define the independent variables (input activity per sample, trained activity per layer, parallelism K=P, timesteps T) and the dependent ones (cycles, latency, energy, accuracy); say which are swept in simulation only and which on the board.",
]),
(1, "1.3  Objectives and Scope", [
    "Testable objectives: (1) train the conv SNN and log per-layer rates; (2) fixed-point golden model within 1 % of float; (3) dense datapath bit-identical on the board; (4) event-driven datapath bit-identical on the board; (5) measured energy per inference for both vs the tool estimate; (6) the crossover in the parallelism and activity axes; (7) the learned perception encoder on the same hardware.",
    "RESULT: status 2026-09-20 -- 1-4, 6 and most of 7 complete; 5 waits on the meter. WHERE: docs/results_ledger.md.",
    "Scope boundaries, stated as such: C1 is the layer on silicon (C2, C3 and FC are bit-identical in simulation, C0015); one fabric at 100 MHz; T=4 as built; no physical robot (simulation-in-the-loop, decision 2026-08-20); energy at the board input, not per rail.",
    "TAB: [todo] Objectives vs status vs evidence: one row per objective with the milestone (M0-M8), status, the number that closes it, and the section where it is shown.",
]),
(1, "1.4  Contributions", [
    "(a) A same-fabric dense-vs-event-driven comparison with bit-identical outputs and a 33-check verification ladder plus pre-registered silicon passes (hdl/, sim/, check_all.sh, experiments/*prereg*.md).",
    "(b) A validated cycle model for both datapaths (ED = 2NT + 5.0 s + 71.7 s/K; dense = 88 N/P per T=4 inference), within 0.3 % of simulation and ~1 % of silicon on two datasets and three layers (experiments/latency_sim/, experiments/dvsgesture/latency_sim/README.md, experiments/rate_sweep*/README.md).",
    "(c) The crossover, measured: parallelism crossover between K=P=4 and 8 on silicon; activity crossover ~30 % input density per clip on DVS-Gesture, on silicon; trained-activity crossovers ~48 %/~57 % (N-MNIST C2/C3) and ~43 %/~48 % (DVS-Gesture C2/C3) in simulation, falling with K=P.",
    "(d) TODO: board-measured energy vs tool estimate, the delta as a result in itself (measure/metering_prereg_2026-09-19.md, experiments/power_estimates/).",
    "(e) The 58k-parameter perception encoder distilled inside ES-Parkour's own stack (IsaacGym) and benched on real event frames (robot/isaac/, experiments/p1_distill/).",
    "(f) Methodological: the second benchmark exposed a sweep bug invisible to N-MNIST (C0044) -- bit-identity on one dataset is not verification; corner-exposure reporting and a synthetic corner set are the guards. Pre-registration before every silicon pass, with one recorded miss (the 5.0-cycle FIFO term).",
    "Be precise about reused (snnTorch, N-MNIST, DVS-Gesture, extreme-parkour, IsaacGym) vs built (both datapaths, golden model, wrapper, server, protocol, exporters, benches, event simulator port). One sentence per contribution on what is NOT claimed (no novel neuron, no new dataset, no physical robot).",
]),
(1, "1.5  Summary of Results", [
    "Copy docs/results_ledger.md sections 1-5 as a one-page table; refresh when the meter and the student results land.",
    "RESULT: silicon at 100 MHz, engine-only: ED K=4 688.5 us mean (554.8-815.8) vs dense P=4 1,048.9 us flat; ED K=8 575.5 vs dense P=8 540.3 us; DVS-Gesture ED K=4 2,970.8 us mean vs dense P=4 3,706.5 us flat (6 of 8 clips). Perception workload: teacher 95-99 % success per terrain; on 64 real robot event frames ED K=4 1.86 ms mean / 2.52 ms worst vs dense 3.60 ms.",
    "TAB: [todo] Headline table: one row per result (latency at K=P=4 and 8, per-clip crossover, trained-activity crossovers, T ceiling, energy measured vs estimated, student success), with the basis column (sim / board / gpu) and the section.",
]),
(1, "1.6  Thesis Organization", [
    "One paragraph mapping chapters 2-7; say that Chapter 4 is the decision log (docs/decisions.md) turned into prose and Chapter 6 reports sim and board with the basis in every caption.",
]),
(0, "2  Background", [
    "Every concept Chapters 4-6 need, defined at first use. Keep biology to half a page; related work has its own chapter. Target 15-20 pages.",
]),
(1, "2.1  Spiking Neural Networks and the Leaky Integrate-and-Fire Neuron", [
    "The LIF neuron and the EXACT semantics implemented: delayed reset-by-subtraction, strict '>' threshold, beta = 0.875 as a shift (V - V>>3); why each is load-bearing for bit-exactness (D0002, D0007). Cross-check: snnTorch and the hand-written loop agree to max |V| diff 0.0 (train/00_lif_demo.py, experiments/m0_lif_demo.png).",
    "Neuron-model choice justified by citation and a hardware-cost table, not assertion (C0043). Reset variants (to zero vs by subtraction) and why subtraction keeps the residual charge; hard vs soft threshold; what a rate-coded readout is.",
    "Spike coding and why SNNs promise efficiency (a spike is a 1-bit event, so a synapse costs an add, not a multiply; silence costs nothing in an event-driven design) -- and why the promise has to be measured (queues, memory and static power are paid whether or not spikes arrive).",
    "FIG: [exists] LIF membrane trace with input spikes, threshold crossings and delayed subtraction reset, snnTorch vs the integer loop overlaid (experiments/m0_lif_demo.png; regenerate at 300 dpi from train/00_lif_demo.py).",
    "TAB: [todo] Neuron models and their hardware cost: IF, LIF with shift leak, LIF with multiply leak, adaptive-threshold; columns = state bits, arithmetic per update, DSP use, citation, chosen? (C0043).",
]),
(1, "2.2  Clock-Driven and Event-Driven Execution of Spiking Networks", [
    "Dense: every neuron and synapse every timestep; cost = neurons x fan-in x T / P; data-independent latency. Event-driven: spike queue, scatter to fan-out targets in K banks, then a sweep; cost = sweep floor + per-spike work / K; data-dependent latency.",
    "Where a crossover must come from (the sweep floor and queue overhead vs the dense walk), and why it must be established per fabric by measurement. Matched parallelism K = P as the fair axis (decisions 2026-09-06, C0029).",
    "The sweep floor 2NT: the event-driven engine still visits every neuron once per timestep to apply leak and threshold, so it can never be cheaper than that; the sweep-skip question (C0006, D0025) and the touched-neuron fraction that decided it (experiments/touched_fraction.md).",
    "FIG: [todo] Side-by-side schematic: dense walk (P lanes striding through N neurons, every timestep) vs event-driven (spike list -> scatter into K banks -> sweep). Annotate each with its cost term. Draw once, reuse in 4.4/4.5.",
    "FIG: [todo] Conceptual crossover sketch: cycles vs activity for both designs, the dense line flat, the ED line rising, the crossing marked; then the real one in 6.6 replaces it.",
]),
(1, "2.3  Event-Based Vision and Input Encoding", [
    "How a DVS works (per-pixel log-intensity change, ON/OFF polarity, microsecond timestamps); events simulated from depth for the robot workload (frame-difference on inverse depth, contrast threshold, 10 Hz; robot/isaac/event_sim_torch.py).",
    "Encoding: T bins per sample, binarised (D0003); what binarisation discards (0.13 % of pixel-bins clipped at T=4, ~0 at T=16). Direct coding (one frame repeated over T) vs consecutive windows (C0047) and what each costs the event-driven engine.",
    "Input density as the variable that drives everything downstream: N-MNIST 13.6 % mean, DVS-Gesture 22-27 % mean and 9-44 % per clip, robot frames after the 2 m clip and binarisation (quote from experiments/p1_distill/).",
    "FIG: [exists] An N-MNIST sample as T=4 binarised frames per polarity (experiments/m0_nmnist_sample.png); extend to a three-panel figure with one DVS-Gesture clip and one robot event frame (from the exported vector sets) at the same scale.",
    "TAB: [todo] Input statistics per source: resolution, polarity channels, T, mean density, per-sample density range, clip fraction from binarisation.",
]),
(1, "2.4  FPGA Architecture, Timing Closure and Power Estimation", [
    "Zynq-7020 PS+PL; LUT/FF/BRAM/DSP budgets (53,200 / 106,400 / 140 tiles / 220); AXI-Stream and DMA; timing closure and WNS; why 100 MHz; why everything stays on-chip (off-chip reads ~200x a multiply). Fixed-point arithmetic: shifts not multiplies, so DSP = 0 by construction.",
    "What a block RAM physically provides and the port discipline learned on silicon (one write + one read port per bank, no multipliers on address paths, single-stage ROM init): decisions 2026-09-06, sim/lint_synth_safety.sh.",
    "How Vivado's power report is produced (vectorless activity propagation, default toggle rates, warning 33-332 on every report) and what it omits; what a board-input measurement includes (C0004); the replication trick for a resolvable delta (C0003).",
    "Static vs dynamic power on a 28 nm fabric and why the PS7 estimate (1.533 W in every build) dominates the total: the engine is a 48-270 mW perturbation on a ~1.7 W board, which is why the shunt resolution and replication matter.",
    "FIG: [todo] Zynq-7020 block diagram: ARM PS, DDR, HP0 port, AXI DMA, AXI-Stream into the PL wrapper; mark the 100 MHz PL clock domain.",
    "TAB: [todo] XC7Z020 resources vs the target network's budget (161 KB = 26 % of BRAM) and vs the largest build actually placed (dense P=4 x8: 52 % LUT, 46 tiles; ED K=4 x8: 86 tiles).",
]),
(1, "2.5  Benchmarks and the Quadruped Perception Workload", [
    "N-MNIST (2x34x34) and DVS-Gesture (11 gestures, downsampled to 2x64x64; C0012 for why a second benchmark): input densities N-MNIST 13.6 %, DVS-Gesture 22-27 % mean and 9-44 % per clip -- the independent variable. Raw N-MNIST is class-ordered (D0009).",
    "The perception workload: extreme-parkour (Cheng et al.) teacher-student recipe (scandots teacher by PPO, depth student by DAgger with yaw supervision) and ES-Parkour's changes (events from depth at 10 Hz, spiking ResNet-18, IF, T=4, GRU, spiking MLP); its Fig. 5 success rates (gap 45 / step 60 / hurdle 71 / parkour 29 %) and Table III theoretical energy; the paper's code was never released, so the recipe was rebuilt on extreme-parkour (C0022).",
    "What each benchmark is for: N-MNIST for comparability with the surveyed accelerators and as the low-activity point; DVS-Gesture as the harder, denser, per-clip-variable point that exposed C0044; the robot frames as the workload whose latency has a deadline.",
    "TAB: [todo] Dataset table: classes, native and used resolution, train/test counts, T, encoding, mean density, accuracy of the float model here vs a published reference at similar size.",
]),
(1, "2.6  Training and Fixed-Point Quantisation of Spiking Networks", [
    "Surrogate gradients (snnTorch, arctan), rate-decoded readout; post-training quantisation to int8 weights with power-of-two scales (threshold = 2^k, D0008), int16 membranes, FC pool/4 folded into its scale (D0004). Firing-rate regularisation as an experimental knob (train/03_train.py --rate_target); what it does and does not move (C1's cost is set by the input data).",
    "RESULT: N-MNIST 96.60 % float -> 96.75 % golden integer; DVS-Gesture 63.26 -> 63.26 % (seed 0). Beta sweep 0.5-0.97 flat, 0.875 stands (experiments/beta_sweep/README.md).",
    "Why quantisation is post-training and not quantisation-aware here: the per-layer power-of-two scale keeps every operation a shift, the accuracy cost was within seed noise on both datasets, and the same npz feeds golden model, baked RTL and board (provenance: sim/check_baked_weights.py).",
    "The int16 membrane as a design constant with a measurable margin: the golden check reports each layer's peak |V| as a percentage of int16 (train/06_golden_check.py); how the margin depends on fan-in, T and activity (C0046) is a Chapter 6 result, introduce the quantity here.",
    "FIG: [exists] Per-layer firing rate and accuracy per epoch on N-MNIST (experiments/m0_firing_rates_binarised.png) -- the M0 plot that established the operating range.",
    "TAB: [todo] Quantisation per layer: weight scale 2^k, clip fraction, threshold, peak membrane as % of int16 at T=4, float vs integer accuracy, for both geometries (from train/05_quantise.py and 06_golden_check.py logs).",
]),
(0, "3  Related Work", [
    "Three groups, each closed with what they did not do; then the gap statement. A comparison table with a 'power obtained by' column is the chapter's centrepiece (docs/baseline_table.md). Target 10-15 pages.",
]),
(1, "3.1  FPGA Accelerators for Spiking Neural Networks", [
    "RESULT: rows transcribed 2026-09-19 -- Harmeling NCE 2026, Cheng TCAS-I 2025 (ZCU104, 96.0 % N-MNIST, Vivado + SAIF), Cerebron TVLSI 2022 (XC7Z100, on-chip power report), Li TCAS-I 2021 (VC707, Vivado + SAIF), Minitaur TVLSI 2014 (idle/peak watts, method unstated), FireFly-P 2026 (Artix-7, post-implementation report). Four of five state a Vivado estimate; none measures at a board input. TODO: FireFly-S and Spiker+ rows.",
    "For each work: fabric, network and dataset, accuracy, resources, clock, latency, how power was obtained, energy per inference as reported. Then the pattern: energy claims rest on report_power with or without SAIF, boundaries unstated, static power sometimes excluded.",
    "Place this thesis's numbers in the same columns (N-MNIST 96.6-97.0 %, ZedBoard, ~3.4k-5.8k LUT, 0.69-1.05 ms at 100 MHz, energy TODO measured) so the reader sees it is a small, slow, honestly-measured design rather than a state-of-the-art accelerator.",
    "TAB: [exists] The baseline table (docs/baseline_table.md): work, platform, network/dataset, accuracy, LUT/FF/BRAM/DSP, clock, latency, power method, energy per inference; add a 'this thesis' row at the bottom.",
]),
(1, "3.2  Event-Driven and Address-Event Architectures", [
    "Minitaur's event-driven DBN and Cheng's event-driven neuron update as the closest architectural relatives; how their queue/bank schemes differ from the K-bank scatter here; none compares against a clock-driven twin on the same fabric.",
    "Address-event representation as the origin of the idea (Mahowald; AER buses) and its digital descendants (TrueNorth, Loihi, SpiNNaker): what 'event-driven' means at chip scale vs inside one layer engine. Keep to one page; the thesis is about one engine, not a many-core chip.",
    "The bank-conflict problem in the literature (scatter-add into shared membrane memory) and the choices others made (arbiters, sorting, replication); the channel-interleaved K-bank choice here avoids an arbiter by construction (Section 4.6).",
]),
(1, "3.3  Neuromorphic Perception and Control for Legged Robots", [
    "Guerra-Hernandez et al. 2017 (FPGA SNN CPG on a quadruped, 6 hand-designed neurons, no camera); ES-Parkour (event camera + spiking ResNet-18, theoretical energy); extreme-parkour as the base recipe. No 'first' claims; the difference is a learned vision network and measurement.",
    "TODO: two or three event-camera legged-robot or drone perception works (search 2022-2026) to show the trend toward event vision on robots and that their energy numbers are also theoretical; note ES-Parkour's Table III as the one closest to this workload.",
    "Why the encoder and not the whole policy is the hardware target: the encoder is the bulk of the compute per frame, the GRU/MLP policy is small and stays on the host; the 58k geometry was chosen to fit the fabric on-chip (docs/environment.md).",
]),
(1, "3.4  Measured versus Estimated Energy in Neuromorphic Systems", [
    "The Loihi 2 vs GPU study (Nagy et al.: 3-3.5 W vs > 50 W, R^2 0.89 vs 0.94 -- power, not energy per inference); why tool estimates and meters can rank designs differently; C0001-C0004, C0038.",
    "TODO: one or two FPGA works that DID measure at a board or rail (any domain, e.g. ANN accelerators reporting wall-plug power) to show the practice exists and is cheap; contrast with the SNN rows that did not.",
    "The formal statement this thesis tests (C0027): the tool's ratio of dense to ED energy vs the meter's ratio; agreement in sign, in magnitude, or neither; each outcome and what it would mean for the surveyed papers' claims.",
]),
(1, "3.5  Summary of the Gap", [
    "Same-fabric clock-driven vs event-driven comparison with bit-identical outputs, board-measured energy, swept over parallelism and activity, on a learned perception workload: not present in any row above.",
    "TAB: [todo] Gap matrix: rows = surveyed works plus this thesis; columns = same-fabric twin, bit-identical to a reference, activity sweep, parallelism sweep, measured energy, learned perception workload; tick marks. This is the one table a reader remembers from the chapter.",
]),
(0, "4  System Design and Methodology", [
    "Top-down: goals and system, neuron, network and budget, each datapath, the banking scheme, the comparison methodology, hardware considerations, the measurement methodology, and the perception workload in simulation. Every judgement call is a D-number in docs/decisions.md; this chapter is that log turned into prose. Target 30-40 pages, the longest chapter.",
]),
(1, "4.1  Design Goals and System Overview", [
    "Constraints: local simulation with a golden-model contract, Vivado in a VM, everything on-chip, hand-written Verilog for both datapaths. System figure: Mac -> framed UART -> bare-metal server -> AXI DMA -> AXIS wrapper -> ENGINE (dense | ED) -> back. Walk the loop once.",
    "The flow from data to silicon: train (GPU) -> quantise (npz) -> golden model -> exported vectors -> testbench -> baked RTL -> synthesis (VM) -> SD card -> board pass against the same vectors. Say which artefact is the contract at each arrow.",
    "Design goals ranked: (1) bit-identity, (2) same wrapper and host for both engines, (3) resolvable energy delta, (4) parallelism as a parameter, (5) simplicity over throughput -- and what was traded for each (e.g. no inter-layer chaining on silicon, C0034).",
    "FIG: [todo] System block diagram: host Mac, UART link with CRC framing, Zynq PS running conv_server, AXI DMA, AXIS wrapper with the ENGINE parameter, the engine, DDR buffers; label the timing boundary (engine-only ticks vs wrapper-inclusive).",
    "FIG: [todo] Toolflow diagram from training to board pass (the arrow list above), with the check at each arrow (golden check, testbench, lint, WNS gate, PING build/dataset check, CRC).",
]),
(1, "4.2  Neuron Model and Fixed-Point Arithmetic", [
    "The recurrence: pending[n] = 1 if V[n-1] > theta; V[n] = beta V[n-1] + sum w s[n] - pending theta; s[n] = 1 if V[n] > theta. Why it matches snnTorch defaults exactly (D0002), quantisation on top (D0007, D0008).",
    "Every signal's format: weights int8, membrane int16 with saturation semantics stated, threshold 2^k per layer, current accumulator width, the shift leak V - (V >> 3) and its rounding toward negative infinity for negative V (the one place Python and Verilog could disagree; the golden model reproduces Verilog's arithmetic shift).",
    "One worked timestep for a single neuron with numbers, so a reader can reproduce a line of the trace by hand.",
    "TAB: [todo] Fixed-point formats: signal, width, signedness, scale, overflow behaviour, where set (golden/lif.py, hdl/common/lif_update.v).",
]),
(1, "4.3  Network Architecture and On-Chip Memory Budget", [
    "C1 2->16, C2 16->32, C3 32->64 (3x3 stride 2), 2x2 pool, FC to 128; readout is scaffolding. Two geometries: N-MNIST 2x34x34 (56k params) and DVS-Gesture / robot 2x64x64 (58k). Budget table (docs/environment.md 'The network'); the target-network budget 161 KB = 26 % of BRAM.",
    "Why this network: small enough to stay on-chip with room for replication, deep enough to have a layer (C1) whose input activity is set by the data and layers (C2, C3) whose activity is set by training -- both crossover axes in one model.",
    "Geometry discipline (C0036): three geometries existed at one point; the thesis reports two and names them everywhere (34-geometry, 64-geometry).",
    "FIG: [todo] Network diagram with per-layer shapes for both geometries, parameters, and the layer on silicon highlighted.",
    "TAB: [todo] Per-layer budget: parameters, weight bytes (int8), membrane bytes (int16), address-list bytes (worst case), BRAM tiles as placed, for both geometries; total vs the 140-tile fabric.",
]),
(1, "4.4  Clock-Driven (Dense) Datapath", [
    "P lanes walking output neurons in groups, weight ROM at stepped addresses, LIF update, per-lane membrane and output-word banks (conv_layer_p.v). Cost model 88.0 cycles per neuron per T=4 inference, exactly 1/P (N-MNIST C1 407.2k/P; DVS-Gesture C1 1,441,788/P within 2 cycles at every P; C2/C3 1,212,412 / 1,196,028 at P=4).",
    "Silicon-forced changes: banked output word file for timing (WNS -3.23 -> +0.30); single-stage weight ROM init after an all-zero build; registered output-bit write (rev 3) after WNS -0.696 at the DVS-Gesture geometry (decisions 2026-09-06, 2026-09-19).",
    "The dense engine's claim to fairness: it is not a straw man -- it has the same parallelism knob (C0029), the same LIF core, the same memory discipline and the same wrapper; its only disadvantage is the one the thesis is about (it does the work whether or not spikes arrive).",
    "Where the 88 cycles go: 3x3x C_IN multiply-free accumulations per output neuron per timestep, the LIF update, the output write; why the count is data-independent to within 2 cycles.",
    "FIG: [todo] Dense datapath block diagram: input frame memory, P lanes, weight ROM addressing, shared lif_update, per-lane membrane bank, output word bank; annotate the 22 cycles per neuron per timestep.",
    "TAB: [todo] Dense cost per layer and P: predicted 88 N/P vs simulated cycles for C1/C2/C3 on both geometries (from experiments/latency_sim and rate_sweep*/bench), error column.",
]),
(1, "4.5  Event-Driven Datapath: Spike Queue, Scatter and Sweep", [
    "Scatter unit: decode one spike's (channel, row, col), add its weight column into every output neuron it touches (at most a 2x2 block x C_OUT); then the two-beat pipelined sweep (C0030: 2 cycles/neuron) applies the LIF update and zeroes each neuron's current at its read beat; word-parallel output (C0035). Addresses travel as packed fields, never flat indices (a divide on an address path cost 12 ns).",
    "Cost model: cycles = 2NT (sweep) + 5.0 s (FIFO pump, K-independent) + 71.7 s/K (scatter) -- the 5.0 term was found by a pre-registration miss. Per-spike constants transfer across datasets and layers (C2 40.4 vs 41.0, C3 74.0 vs 76.4). Direct coding makes the scatter repeat the same frame T times (C0047).",
    "RESULT: the sweep bug (C0044): the current-zero write was gated on the update pipeline's valid flag, so neuron 0 was never cleared; invisible on N-MNIST (zero corner exposure), caught by DVS-Gesture. hdl/eventdriven/ed_conv_layer.v.",
    "The three phases of one timestep and what bounds each: (i) address-list fill from the input frame, (ii) scatter, s spikes x (fan-out / K) cycles, (iii) sweep, 2N cycles. Which phase dominates at which activity, and why K only helps phase (ii).",
    "Stride-2 3x3 fan-out geometry: an input spike touches at most a 2x2 block of output positions x C_OUT channels; edge spikes touch fewer (corner exposure); how the scatter walks that block.",
    "FIG: [todo] Event-driven datapath block diagram: input frame -> spike address list -> scatter unit (weight column fetch, K bank adders) -> K membrane banks -> two-beat sweep pipeline -> output words. Annotate the three cost terms on the blocks that cause them.",
    "FIG: [todo] Timeline of one inference at two activities (e.g. 9 % and 44 % clips): fill / scatter / sweep bars per timestep for K=4, showing the fixed sweep and the growing scatter; from the testbench's phase counters.",
    "TAB: [todo] Cycle-model terms: term, meaning, fitted constant, how found (fit / pre-registration miss), datasets it was checked on, error.",
]),
(1, "4.6  Spike Address List and Banked Membrane Memory", [
    "The address list is sized for the worst case (every input firing once) so it can never overflow (D0016); K channel-interleaved banks so K read-modify-writes land per cycle with no arbiter; K must divide C_OUT; K in {1, 2, 4, 8, 16} simulated, 4 and 8 on silicon. One write + one read port per bank (the multi-ported first version could not map to BRAM).",
    "Design options considered for the banks (arbitrated shared memory, output-row interleave, channel interleave, full replication) with the trade-off each makes (conflict rate, BRAM, logic, timing); why channel interleave is conflict-free for this fan-out pattern (D0017).",
    "Worst-case sizing as a deliberate trade (C0032): what it costs in BRAM at each geometry vs the risk of an overflow path that would need a stall or a drop, both of which would make latency non-deterministic in a way the deadline analysis could not bound.",
    "The two-word neuron state (membrane + current) and whether it is structural or an ordering artefact (C0033); the answer chosen and its BRAM cost.",
    "FIG: [todo] Bank interleaving diagram: output channels striped across K banks, one spike's 2x2 x C_OUT footprint landing K-wide per cycle.",
    "TAB: [todo] K options: K, banks, adders, BRAM tiles per engine, WNS on silicon where built, cycles at the mean N-MNIST and DVS-Gesture sample.",
]),
(1, "4.7  A Shared Wrapper for Matched-Parallelism Comparison", [
    "One AXIS wrapper with an ENGINE parameter (D0021): identical framing, DMA path, server, client and vectors; baked weights for synthesis; the DATASET knob selecting table + geometry + threshold together (decision 2026-09-18); matched parallelism K = P. BURST mode with engine-only ticks (server build 4/5); PING reports build and dataset.",
    "Cycle models as the prediction instrument: derivation, fit, the validation standard (0.3 % per sample on a second dataset before predicting with it), a table of every model-vs-measurement comparison (board +0.4 to +1.5 %; the DVS-Gesture 'offsets' of 92.9 / 102.0 us turned out to be a comparison-basis artefact -- against wrapper-inclusive harness totals the board is +29.4 us ED / +20.0 us dense, constant).",
    "Pre-registration practice: predictions committed before every silicon pass (experiments/*prereg*.md); one where everything held (dense P=4), one where a hypothesis failed and was recorded (DVS-Gesture ED K=4 offset). The pre-card-write checklist and the deliveries it rejected.",
    "What 'matched parallelism' buys and what it hides: K and P are both 'work units per cycle' but of different kinds (bank adders vs neuron lanes); iso-resource and iso-latency comparisons (C0021) as the two alternatives, and why K=P was chosen as primary with resources reported beside it.",
    "The wrapper's own cost (C0014, C0035, C0041): 6.3k-8.2k cycles per inference of framing and DMA; how it is attributed and why engine-only ticks are reported for latency but wrapper-inclusive totals are used for board-vs-sim comparison.",
    "FIG: [todo] Wrapper block diagram: AXIS in/out, frame parser, engine instance (ENGINE, DATASET, K or P, N_ENGINES), tick counter, CRC, the replicated-engine fan-out used for the metering builds.",
    "TAB: [todo] Prediction vs measurement for every silicon pass (1-14): build, predicted cycles/latency, measured, error, pre-registered hypotheses held/failed.",
]),
(1, "4.8  Golden-Model Verification Methodology and Hardware Constraints", [
    "Fixed point: int8 weights (power-of-two scales), int16 membranes, integer thresholds 2^k, shift leak; no multiplier anywhere in the datapath. The int16 membrane budget as a real constraint: overflows on DVS-Gesture at T=16, at T=8 for one seed in three, and at 34 % activity on every seed (C0046) -- the options (18-bit, fc k=7, T=4).",
    "The golden-model rule as the central engineering contract: bit-identical, never close; corner-exposure reporting per check set (N-MNIST blind at all four C1 corners, the robot depth stream at the top two, only the synthetic set covers all four).",
    "What bit-identity does and does not prove: it proves the RTL computes the same function on the vectors tried; it does not prove port discipline, address timing, synthesis-tool behaviour, or coverage of untried input patterns -- each of those got its own check (lint_synth_safety, hostile-handshake wrapper bench, AXIS stress, corner set).",
    "Sample-set discipline: the class bias of the first check set (C0039) and the unbiased DVS-Gesture clip set; why 16 and 8 samples are enough for cycle checks (every sample is a full bit-identity test) but not for accuracy.",
    "FIG: [todo] Verification flow: trained npz -> golden model -> vector files (inputs, expected outputs, threshold) -> testbench compare -> baked RTL -> board compare over the link; the ladder as the set of arrows.",
    "TAB: [todo] Vector sets and their corner exposure: set, geometry, layer, samples, spikes per sample (range), corner-neuron activity count per corner, what it can and cannot catch (from sim/corner_exposure.py output).",
]),
(1, "4.9  Energy Measurement Methodology and Pre-Registration", [
    "The metering protocol, pre-registered (measure/metering_prereg_2026-09-19.md): 0.1 ohm shunt + mV reading on the 12 V input (0.1 mA resolution), idle-run-idle with timer cross-check, 3 runs x 15 readings, SEM, drift and resolvability flags, randomised order; the bitstream matrix (x8 replications first for a resolvable delta, then single engines, then DVS-Gesture per clip); the three energy quantities (C0038). Also available for the meter: C0019 implementation-strategy bitstreams (Performance_Explore, Congestion_SpreadLogic_high vs default) of ED K=4 and dense P=4 N-MNIST, same RTL, all closed within 0.4 ns of each other, in the estimates table and on the VM -- prereg rows 11-13 / P9, the measured bitstream-to-bitstream spread against the tool's ~9 mW / ~3 mW spread.",
    "RESULT (tool side, experiments/power_estimates/): fabric 48 mW ED K=4, 62.6 mW per dense P=4 engine (from x8), 54 / 83 mW at K=P=8, 72 / 135 mW DVS-Gesture at N=1, and by replication subtraction 54.7 mW per ED engine (x4) vs 135 mW per dense engine (x2) -> tool ratio 3.1x per engine on DVS-Gesture; PS7 1.533 W in every build. Placement alone moves the estimate ~9 mW (19 %) on ED and ~3 mW on dense across three implementation strategies at fixed RTL (C0019 variants) -- quote this as the tool's own uncertainty. The tool predicts ED 3.2x in energy at K=P=4 and 1.44x at K=P=8; my pre-registered P2 says 1.1-1.4x -- both on record before the meter (prereg sections 7-7d).",
    "The arithmetic, written out: delta I (mA) x 12 V / eta_reg = fabric-side delta power; per engine = delta / N_ENGINES minus the wrapper share found from the N=1 subtraction; energy per inference = per-engine power x engine-only latency; energy per control period = board power x period (C0005). Say which regulator efficiency is assumed and why the 12 V point is imperfect (C0026).",
    "Controls: die temperature logged or bounded (C0009, C0020); idle measured per bitstream, not once (C0001); noise floor from repeated idle windows before any comparison (C0002); BURST replays a set, not one sample (C0018); sample order randomised (C0016).",
    "Why replication (C0003) is legitimate: per-engine latency is unchanged at x8, x4 and x2 (passes 7, 8, 13, 14), so N engines doing N inferences in the same time is the same work; the wrapper share is removed by the N=1 subtraction.",
    "FIG: [todo] Metering setup: schematic of the shunt in the 12 V lead with the DMM in mV mode, plus a photograph of the bench; timing diagram of idle / BURST / idle windows with the reading schedule.",
    "TAB: [exists] The bitstream matrix rows 1-13 (measure/metering_prereg_2026-09-19.md section 2): row, build, archive tag, purpose, BURST N, predicted delta; then the same table with measured columns filled in 6.5.",
    "TAB: [exists] Pre-registered predictions P1-P9 with the tool's number and my contrary number side by side, and an empty 'outcome' column to be filled after the meter.",
]),
(1, "4.10  Simulation-in-the-Loop Perception Workload", [
    "Simulation-in-the-loop framing (decision 2026-08-20): lockstep physics, wall-clock-charged perception budget, stale latent on a miss, never a silent wait (robot/host/perception_loop.py, delay-injection test). The IsaacGym port: event simulator bit-identical to the recreation's, the 58k encoder verbatim, plugged into extreme-parkour's learn_vision as base_backbone only. Judgement calls: repeat window (direct coding) vs consecutive windows, 2 m depth clip, 64x64 resize, binarisation before the encoder.",
    "The teacher-student pipeline as run: teacher by PPO on scandots (15,000 iterations), student by DAgger on the teacher's actions with the event encoder as the vision backbone (10,000 iterations, 192 camera environments, 13.6 s/iteration on the 1080 Ti); evaluation protocol identical to extreme-parkour's (success = episode reaches its length without termination, per terrain).",
    "What is charged to the FPGA and what is not: the encoder's latency (measured on the board on real frames) is the perception budget; the GRU and MLP run on the host; physics is lockstep so a late latent is stale, not skipped.",
    "The event simulator's parameters and their provenance from the paper (contrast threshold, 10 Hz, inverse depth) and the one deviation (frame repeat over T rather than four consecutive 25 ms windows, C0047) with its cost to the ED engine (the scatter repeats).",
    "FIG: [todo] Perception-loop timing diagram: physics steps, camera frame at 10 Hz, event simulation, encoder budget, latent hand-off, stale-latent path on a miss.",
    "FIG: [todo] Event-simulation pipeline on one real frame: depth -> inverse depth -> difference -> threshold -> ON/OFF frames -> T bins -> binarised input to C1 (from robot/artifacts/isaac_event_frames.npz).",
    "TAB: [todo] Training configuration: teacher and student hyper-parameters, environments, iterations, wall time, hardware, seeds, the code paths changed vs stock extreme-parkour (robot/isaac/README.md).",
]),
(0, "5  FPGA Implementation", [
    "From golden model to sign-off-clean silicon: RTL, toolchain, bare-metal bring-up, and the timing/mapping lessons bit-identical simulation could not see. Target 15-20 pages; listings go to Appendix A.",
]),
(1, "5.1  Fixed-Point Golden Model and Test-Vector Generation", [
    "golden/: the all-integer network (geometry-generic since C0012), the Python event-driven engine (bank model), trace export; sim/export_*: vector sets c1-c3 (N-MNIST), g1-g3 (DVS-Gesture), r1 (recreation), i1 (IsaacGym frames), each with a threshold file and a corner-exposure line.",
    "The golden event-driven engine as a second model of the same function: it reproduces the bank order and the sweep so that the RTL's intermediate state (not only its outputs) can be compared; where the two Python models are cross-checked against each other in the ladder.",
    "Vector file format (inputs, expected spikes, threshold, sample ids) and why thresholds ride with the vectors (a threshold mismatch was the cause of one dense g1 failure, fixed by per-layer threshold files).",
    "TAB: [todo] Vector sets: name, source npz, geometry, layer, samples, T, threshold, spikes per sample range, corner exposure, ladder checks that use it.",
]),
(1, "5.2  LIF Neuron Core and Baked-Weight Generation", [
    "lif_update.v: one shared combinational LIF core used by the M2 neuron and both engines. Vendor-neutral Verilog, simulated in Icarus Verilog and linted with Verilator; weights inlined into generated module variants (sim/gen_weight_vh.py from the tracked npz files, checked by sim/check_baked_weights.py) because $readmemh is silently zeroed in this flow.",
    "M2 as the first bit-identical module: the single-neuron testbench replaying golden traces; how the same core is instantiated P times (dense) and once per sweep pipeline (ED) so that the neuron arithmetic is verified once and shared.",
    "Baked-weight provenance as a chain: tracked npz -> generator -> Verilog case tables -> check_baked_weights.py entry-for-entry compare; the near miss where synthetic hex overwrote the r1 tables and what now prevents it.",
    "FIG: [todo] lif_update schematic: inputs (V, I, threshold, pending), the shift leak, the subtract, the compare, outputs (V', spike, pending'); one figure for the whole thesis's neuron.",
]),
(1, "5.3  RTL Implementation of the Two Datapaths", [
    "conv_layer_p.v; ed_scatter.v + ed_conv_layer.v; baked variants c1 / g1 / r1. The sign-off rules: one write + one read port per bank, no multipliers/dividers on address paths, re-registered BRAM outputs, use_dsp = no, single-stage ROM init.",
    "Module-by-module: what each does, its parameters (P or K, DATASET, geometry localparams), its state machine, and which ladder check covers it. Keep the prose to one paragraph per module; the code is in Appendix A.",
    "Parameterisation discipline: geometry derives from DATASET at the top (DS_H_IN, DS_W_IN, DS_THRESHOLD ...) so a build cannot mix a table from one dataset with the geometry of another; PING reports the dataset so a mis-built image is rejected before any card is written.",
    "TAB: [todo] RTL inventory: module, file, lines, role (engine / wrapper / common), parameters, ladder checks, on silicon (yes/no).",
]),
(1, "5.4  Host Interface: AXI DMA, Bare-Metal Server and Link Protocol", [
    "Zynq PS + DMA + HP0 into DDR; conv_server.c (build 5; -DDATASET) and the conv_server_g1 component; SD boot chain; framed UART protocol with CRC-32; golden mock server; the Mac client (host/uart_client.py, snn_link.py). Board preset and DMA address map as load-bearing (D0014/D0015).",
    "Bring-up story in brief: the DMA that could not be reached from the CPU (address filter routing DDR away, docs/decisions.md 2026-09), the AHB-AP diagnosis, the board preset fix -- as a lesson that the PS configuration is part of the design under test.",
    "The BURST command and engine-only ticks (D0022): how latency is timed on the fabric rather than by the host, what the tick counter includes, and the cross-check against wall-clock over a known N.",
    "FIG: [todo] Link frame format (sync, length, command, payload, CRC-32) and the command sequence for one board pass (PING -> LOAD -> RUN x samples -> BURST); a sequence diagram, not a screenshot.",
    "TAB: [todo] Protocol commands: command, direction, payload, reply, what it is used for (from host/snn_link.py and host/conv_server.c).",
]),
(1, "5.5  Synthesis Flow, Timing Closure and Build Provenance", [
    "Vivado/Vitis 2024.1 on a Windows VM over RDP; scripted builds (host/vivado/build_engine.tcl: parameter read-back, WNS gate, power report, bootgen, tags) and the fresh project (docs/vivado_new_project.md). Vivado gotchas as lessons: stale Design Runs table, auto-incremental checkpoints, bitstream timestamps, $readmemh silently zeroed.",
    "Build provenance as a rule: every bitstream has a tag (build_date_time), a read-back of its parameters, its WNS, its utilisation and its power report archived (experiments/power_estimates/, experiments/board_*.md); the unattended build queue (build_queue.tcl) and what it produced overnight.",
    "Timing-closure history as a table rather than a story: each negative-slack build, its critical path, the change that closed it, the new WNS. Keep the causes (address-path multipliers, dividers, unregistered BRAM outputs, the LIF->obits path at the 64-geometry).",
    "TAB: [exists] Build provenance: tag, configuration, WNS, LUT / FF / BRAM tiles / DSP, estimate (total W, fabric mW), board pass number (experiments/power_estimates/README.md joined with the board records).",
    "TAB: [todo] Timing-closure history: build, WNS before, critical path, fix, WNS after (from docs/decisions.md 2026-09-05 onward).",
]),
(1, "5.6  Verification Ladder and Silicon Sign-Off", [
    "The ladder (check_all.sh, 33 checks) and its counts (e.g. 591,872 comparisons ED c1; 1,048,576 DVS-Gesture g1; 18/18 N-MNIST rate sweep; 12/12 DVS-Gesture C2/C3); hostile-handshake wrapper benches -- RESULT: AXIS stress of the baked wrappers, 60 random gap/backpressure seeds x {N-MNIST c1, DVS-Gesture g1} x {ED K=4, dense P=4} = 240 runs, 240/240 bit-identical (experiments/axis_stress/README.md, 2026-09-20), i.e. handshake robustness far beyond the ladder's single seed and the DMA's one pattern; fault injection; the synthetic corner set; what simulation does NOT prove (port discipline, address timing, toolchain regressions), each converted into a standing check.",
    "Silicon sign-off as a procedure: the pre-card-write checklist (parameter read-back, WNS gate, PING build and dataset, golden mock first), the pre-registration file, the pass record; RESULT: fourteen passes, zero correctness misses, two wrong-bitstream deliveries rejected before any number was recorded.",
    "The negative test: the ladder's corner set fails on pre-C0044 RTL (proved by checking out the old RTL), so the guard is known to guard; say this explicitly, a check that has never failed proves little.",
    "TAB: [todo] The ladder: check number, what it compares, vectors, comparison count, runtime, what class of bug it catches (from check_all.sh; 33 rows, or grouped into ~10 classes if the full table is too long for the body).",
    "TAB: [exists] Silicon passes 1-14: pass, date, build tag, dataset, engine, N_ENGINES, samples, bit-identical, latency, WNS, tiles (docs/results_ledger.md section 1 and 3 plus the DVS-Gesture x4/x2 records).",
]),
(0, "6  Results and Evaluation", [
    "Every table carries the brief's metrics (energy measured / estimated, latency, deadline-miss where applicable, mean power, LUT-FF-BRAM-DSP, firing rate per layer, accuracy) and says sim or board in the caption. Either crossover outcome is a valid result; nothing is tuned toward one. Target 25-35 pages.",
    "Figure discipline: every figure is generated by experiments/figures/make_figures.py from committed data, never from typed numbers; captions name the basis (sim / board / gpu), the dataset, the geometry, K or P, and the sample count.",
]),
(1, "6.1  Experimental Setup", [
    "ZedBoard XC7Z020 at 100 MHz, SD boot, bare metal; 16 N-MNIST / 8 DVS-Gesture golden samples over the framed link; BURST windows; engine-only timing; the Mac (iverilog/verilator) for every simulation; the MI210 and 1080 Ti hosts for training; the meter (TODO).",
    "Software versions and seeds (docs/environment.md): snnTorch, PyTorch/ROCm and CUDA versions, Vivado 2024.1, Icarus and Verilator versions, IsaacGym preview and extreme-parkour commit; seeds 0-2 where three seeds are reported.",
    "TAB: [todo] Setup table: item, version or model, role, where used; one row for the DMM (model, range, resolution, shunt value and tolerance).",
    "FIG: [todo] Photograph of the bench (ZedBoard, UART, SD, the shunt and meter in the 12 V lead) -- the one photograph in the thesis.",
]),
(1, "6.2  Task Accuracy and Firing Rates", [
    "RESULT: N-MNIST 96.6-97.0 % (3 seeds), quantisation cost within noise; DVS-Gesture 63.3 / 68.6 / 63.3 % (3 seeds, T=4), golden 63.3 / 66.7 / 65.9 %; T sweep 63.3 / 65.2 / 68.9 % at T=4/8/16. Per-layer rates: N-MNIST conv 6-11 %, FC ~30 %; DVS-Gesture c1 .073, c2 .143, c3 .186, fc .359. Trained-rate networks: N-MNIST accuracy flat 2-8 % then -0.5/-1.9 pp at 16/30 %; DVS-Gesture a 3 pp step between the 2-5 % and 10-35 % regimes. WHERE: experiments/dvsgesture/README.md, experiments/rate_sweep*/README.md.",
    "Say why the DVS-Gesture accuracy is low against the literature (a 58k-parameter network at 64x64 with T=4 and 264 test samples, vs published ~95 % with far larger networks and T=16+) and why that is acceptable: the datapath comparison needs realistic activity, not state-of-the-art accuracy; accuracy is reported at every sweep point (C0008).",
    "Report the rate-regulariser's reach: what conv rates it produced (2-35 %), that C1's input activity is unmovable, and the accuracy price at each point with seeds.",
    "FIG: [exists] Accuracy vs achieved conv activity, both datasets, mean +- sd over 3 seeds (experiments/figures/fig_accuracy_vs_activity.png).",
    "FIG: [exists] Per-layer firing rate per epoch, N-MNIST binarised (experiments/m0_firing_rates_binarised.png); optionally the counts arm beside it (D0003).",
    "TAB: [todo] Accuracy and rates: dataset, seed, T, float accuracy, golden integer accuracy, per-layer rate (c1, c2, c3, fc), peak fc membrane as % of int16 -- one row per trained network used anywhere in Chapter 6.",
]),
(1, "6.3  Resource Utilisation and Timing", [
    "RESULT: per build -- ED K=4 ~3.4k LUT / 12.5 tiles / WNS +0.508; dense P=4 5,760 LUT / 6.5 tiles / +0.299; ED K=8 13.5 tiles / +0.332; dense P=8 8.5 tiles / +0.101; ED K=4 x8 11,733 LUT / 86 tiles / +0.430; dense P=4 x8 27,829 LUT (52 %) / 46 tiles / +0.041; DVS-Gesture ED K=4 +0.190, dense P=4 +1.091 (rev 3); ED K=4 DVS-Gesture x4 86 tiles / +0.119; dense P=4 DVS-Gesture x2 21 tiles / +0.842 and x4 does not place. DSP = 0 everywhere. The honest asymmetry is STATE not logic. WHERE: experiments/board_*.md utilisation sections.",
    "Interpretation: the ED engine costs about half the LUTs of the dense engine at K=P=4 but about twice the BRAM (address list + K banks + two-word state); the dense engine's logic (decoded output enables) is what fails to replicate x4 at the 64-geometry while the ED engine's memory is what fails at x8. Neither is 'smaller'; they spend different resources.",
    "Timing: every build closes at 100 MHz with the sign-off rules; the smallest margins (dense x8 +0.041, ED x4 DVS-Gesture +0.119) and what limits them; the strategy variants show +0.35 to +0.77 ns spread at fixed RTL.",
    "FIG: [todo] Grouped bars of LUT, FF, BRAM tiles per build (N=1 builds on one panel, replicated on another), ED vs dense side by side; generated from the board records.",
    "TAB: [todo] Utilisation and timing per build: build, engine, K or P, dataset, N_ENGINES, LUT (% of 53,200), FF, BRAM tiles (% of 140), DSP, WNS, WHS, power estimate -- the brief's resource row for every silicon pass.",
]),
(1, "6.4  Latency per Inference at Matched Parallelism", [
    "RESULT: N-MNIST C1 at matched parallelism -- ED K=4 688.5 us mean (554.8-815.8, 1.47x spread) vs dense P=4 1,048.9 us flat -> 1.52x; ED K=8 575.5 us vs dense P=8 540.3 us -> dense 1.065x; sim-vs-board +0.4 to +1.5 %; x8 replications leave per-engine latency unchanged. DVS-Gesture: ED K=4 2,970.8 us mean (2.24x spread) vs dense P=4 3,706.5 us flat -> ED 1.248x at the mean; ED x4 replication (pass 13, 2026-09-20) 8/8 with per-clip latency equal to N=1 to 0.1 us, 86 BRAM tiles, 1.926 W estimate; dense P=4 DVS-Gesture does NOT place at x4 (65k decoded-enable output flops), so its replicated build is x2 -- a fabric-fit fact worth a sentence beside the resource table; dense P=4 DVS-Gesture x2 on silicon (pass 14, 2026-09-20): 8/8, per-clip latency 3,706.4-3,706.5 us equal to N=1, WNS +0.842, 21 BRAM tiles, 1.956 W estimate (experiments/dvsgesture/board_dense_p4_x2_20260920.md). Both replicated pairs are on silicon (N-MNIST x8/x8, DVS-Gesture x4/x2): fourteen board passes, zero correctness misses (docs/results_ledger.md rows 1-14).",
    "Per-sample view: ED latency is a straight line in input spike count (the cycle model), dense is a constant; plotting every board sample against the model line shows the +0.4 to +1.5 % board offset as a parallel shift, and the spread (1.47x N-MNIST, 2.24x DVS-Gesture) as the deadline problem in one picture.",
    "Board-vs-sim as a result: the constant per-inference offsets (N-MNIST ED 10.7 / dense 8.3 us; DVS-Gesture +29.4 / +20.0 us against wrapper-inclusive totals) attributed to DMA and framing, and the lesson that the comparison basis must be stated (Section 4.7).",
    "FIG: [exists] Latency vs K = P for both datasets, simulated curves with silicon points overlaid, the crossover at ~6.6 / 5.8 marked (experiments/figures/fig_kp_sweep.png).",
    "FIG: [exists] DVS-Gesture per-clip latency: ED sim and board, dense sim and board, the two densest clips above the dense line (experiments/figures/fig_dvsg_perclip.png).",
    "FIG: [todo] Per-sample scatter: board latency vs input spike count for every ED board sample (N-MNIST 16, DVS-Gesture 8, robot 64 if benched on the board), with the cycle-model line and the dense constant; add to make_figures.py from the board records.",
    "TAB: [todo] Latency at matched parallelism: dataset, K=P, ED mean / min / max, dense, ratio, sim prediction, board-sim error, samples; one row per silicon pair (the ledger's section 1 plus the DVS-Gesture rows).",
]),
(1, "6.5  Energy per Inference: Measured versus Estimated", [
    "TODO: the central result. Tool estimates exist for every silicon build (experiments/power_estimates/README.md) and predict ED 3.2x in energy at K=P=4 (3.1x per engine on DVS-Gesture) and 1.44x at K=P=8; the pre-registration records the contrary P2 (1.1-1.4x) beside it. Report measured uJ/inference for both engines at K=P=4 and x8 with intervals, the measured/estimate delta as a headline, and the DVS-Gesture per-clip energy if the session allows.",
    "Report structure once the meter exists: (i) noise floor and idle per bitstream (C0001, C0002); (ii) the x8 / x4 / x2 deltas and their SEM; (iii) per-engine power by N=1 subtraction; (iv) energy per inference = per-engine power x latency, per dataset, both engines; (v) the same for the DVS-Gesture clips individually; (vi) the tool's number beside each, the ratio, and the sign test of C0027; (vii) P1-P9 outcomes.",
    "The three energy quantities in three separate rows, never merged (C0038): fabric delta per inference (the datapath claim), board delta per inference (what a deployment pays), energy per control period at 10 Hz (the robot's number, C0005) -- the last is dominated by the PS7 idle and is the honest one for the deadline argument.",
    "If the delta does not resolve at N=1 (possible: 48-73 mW behind regulators at 12 V is ~5-7 mA), say so and report the replicated per-engine numbers only; that outcome is itself the C0003 finding.",
    "FIG: [todo] Energy per inference, measured vs estimated, grouped bars per engine and dataset with error bars (SEM over runs) -- the thesis's headline figure; make_figures.py gains a function reading measure/ logs.",
    "FIG: [todo] Measured vs estimated as a scatter with the identity line, one point per bitstream (rows 1-13), colour by engine; the strategy variants show the tool's own spread.",
    "TAB: [todo] Energy table: build, N_ENGINES, idle mA, burst mA, delta mA (SEM), delta mW at the fabric, per-engine mW, latency, uJ per inference measured, uJ per inference estimated, ratio; then a second table with the P1-P9 outcomes (prediction, tool number, contrary number, measured, verdict).",
]),
(1, "6.6  The Crossover: Parallelism, Activity and Timesteps", [
    "RESULT (parallelism axis): K sweep 135.5k / 90.3k / 67.8k / 56.5k / 50.8k cycles (K=1..16) = 45.2k + 90.3k/K; dense 407.2k/P + 2k; crossover K=P ~6.6 (N-MNIST), 5.8 (DVS-Gesture), bracketed on silicon by 4 and 8. WHERE: experiments/latency_sim/ksweep_c0035/README.md, experiments/dvsgesture/latency_sim/README.md.",
    "RESULT (activity axis, data): DVS-Gesture per clip at K=P=4 -- ED wins iff < ~10,000 input spikes per clip (~30.5 % density); on silicon ED wins 6 of 8 clips and loses clips 1 and 5, exactly as pre-registered. RESULT (activity axis, training): N-MNIST C2/C3 ED over dense 10x/14x at 2 % to 1.6x/1.9x at 30 %, crossovers ~48 %/~57 %; DVS-Gesture C2/C3 8.4x/11.0x at 3 % to 1.33x/1.36x at 32-35 %, crossovers ~43 %/~48 % at K=P=4, falling to 36/44 % at K=P=8 and 26/37 % at K=P=16 (the 32 % network is past the C2 crossover at K=P=16: dense 1.18x). WHERE: experiments/rate_sweep/README.md, experiments/rate_sweep_dvsg/README.md.",
    "RESULT (timesteps): DVS-Gesture 65.0 / 65.7 / 69.3 % mean at T=4/8/16 (3 seeds each) but the fc membrane is at 98-121 % of int16 at T=16 and T x activity compound (at T=8 the ceiling moves to ~15-19 % activity; usable band T x activity <= ~1.2) (C0046); N-MNIST gains +0.7 pp per doubling to 98.0 % at T=16 with the fc at 9-25 % of int16, so the ceiling is a geometry property; cycle projections ED 3.4 / 5.9 / 9.8 ms vs dense 3.6 / 7.2 / 14.4 ms. WHERE: experiments/tsweep_nmnist/, experiments/dvsgesture/README.md.",
    "TODO: the energy curve on the same axes once the meter exists. Plot both engines' curves; report the crossover point or its absence -- both are findings.",
    "The unifying statement: the crossover is a surface in (activity, K=P), not a point -- the ED sweep floor 2NT is fixed while the dense cost falls as 1/P, so more parallelism moves the crossover to lower activity; at the operating activities of these networks (C1 14-27 %, C2/C3 7-19 % trained), ED wins at K=P=4, is roughly even at 8, and loses at 16 on C1 and on the densest C2 network.",
    "Where the operating point sits on each axis (C0037): the N-MNIST C1 crossover at ~31 % density is just above the data's 13.6 %; the DVS-Gesture per-clip range 9-44 % straddles it; the trained-activity crossovers are above any accuracy-preserving network on N-MNIST but reachable on DVS-Gesture at K=P=16.",
    "Cycle-count basis and its limits: these are cycles at a fixed 100 MHz; energy may move the crossover because the two engines' per-cycle power differs (the tool says 48 vs 62.6 mW per engine); 6.5 supplies the correction if the meter allows.",
    "FIG: [exists] Dense/ED cycle ratio vs trained activity for C2 and C3 on both datasets, the 1.0 line and the fitted crossovers (experiments/figures/fig_activity_c2c3.png).",
    "FIG: [exists] Fitted crossover activity vs K = P for C2/C3 on both datasets (experiments/figures/fig_crossover_vs_kp.png) -- the 'surface' figure; add the N-MNIST K=8/16 points if benched.",
    "FIG: [exists] DVS-Gesture accuracy and fc membrane range vs T per seed with the int16 ceiling, N-MNIST beside it (experiments/figures/fig_tsweep_int16.png).",
    "FIG: [todo] Crossover surface as a heat map or contour: ED/dense ratio over (activity, K=P) from the cycle model, with the benched points overlaid and the measured operating points of each network marked.",
    "TAB: [todo] Crossover table: axis, layer, dataset, K=P, crossover value, basis (model / sim / board), the operating point of the trained network, verdict at the operating point.",
    "TAB: [todo] T sweep: dataset, T, seeds, accuracy mean +- sd, fc membrane % of int16 (min-max over seeds), golden-clean (y/n), projected ED and dense latency.",
]),
(1, "6.7  Lessons from Sign-Off: What Simulation Could Not See", [
    "As findings: multi-ported accumulator -> 62k LUTs; multipliers on address paths WNS -4.5; dividers in spike decode WNS -3.5; BRAM latches; two-stage ROM init -> all-zero silicon; the LIF->obits path at the DVS-Gesture geometry (WNS -0.696 -> rev 3); the sweep bug invisible to a centred dataset (C0044); wrong-bitstream deliveries caught by the checklist; the baked-weight provenance near miss (tracked npz + check_baked_weights.py).",
    "Frame each as (symptom, why simulation passed, root cause, fix, the standing check that now catches it); the point of the section is that bit-identical simulation is necessary and not sufficient, and that each gap was closed with a check rather than with care.",
    "The C0044 lesson in full: the bug lived in the RTL for weeks under a 30-check ladder because every N-MNIST sample is centred and never fires a corner neuron; the second dataset's 3 of 32 corner-active samples caught it; the corner-exposure report now prints for every vector set and a synthetic all-corner set is in the ladder; the fix was one unconditional write.",
    "TAB: [todo] Lessons table: date, symptom, where seen (synthesis / timing / silicon / second dataset), root cause, fix, guard added (check name), reference (decisions.md date or C-number).",
]),
(1, "6.8  The Perception Workload: Distillation, Evaluation and Deployment", [
    "RESULT: teacher 15,000 iterations (23.3 h, 1080 Ti), success gap 95.3 / hurdle 96.1 / parkour 97.2 / step 99.2 % under extreme-parkour's protocol (experiments/p1_distill/isaac_eval_README.md). FPGA-student distillation running (10k iterations, ETA 2026-09-21): TODO its success rates on the same protocol, GIFs per terrain (teacher and student), student-driven frames, then the stock depth student as the reference. Real robot event frames (64, direct coding): both engines bit-identical; ED K=4 1.86 ms mean / 2.52 ms worst vs dense 3.60 ms (1.94x / 1.43x). The MuJoCo recreation's earlier result (58k student vs the 11.19M reference) as precursor (experiments/p1_distill/results_fpga_*.md).",
    "Deadline reading: per-frame spread 1.71x (robot), 2.30x (DVS-Gesture) -- the worst-case verdict differs from the mean one. TODO: FPGA-in-the-loop over SSH and the perception-rate sweep (energy per control cycle, deadline-miss rate) if time allows.",
    "How to read the student's success rates: against the teacher (the ceiling, privileged scandots), against the stock depth student (the paper's own recipe with an 11M-parameter ResNet), and against ES-Parkour's Fig. 5 (a different simulator seed and protocol, so only the ordering of terrains is comparable). State the distillation budget (10k vs the paper's unspecified) as the main caveat.",
    "The deadline budget at 10 Hz is 100 ms; the encoder's worst frame on the board is 2.52 ms (ED) or 3.60 ms (dense), so both meet it with margin; the interesting number is the fraction of the budget and the spread, and what perception rate (20, 50, 100 Hz) each engine would first miss -- from the cycle model, then measured if the FPGA-in-the-loop run happens.",
    "Student-driven frames vs teacher-driven frames: the student's own trajectories produce the activity distribution the hardware would see in deployment; compare density and ED latency between the two frame sets once the student frames are benched.",
    "FIG: [todo] One still per terrain (gap, hurdle, parkour, step) from the teacher and student GIFs, side by side, with success annotated (experiments/p1_distill/gifs/ once copied).",
    "FIG: [todo] Per-frame latency on the 64 real event frames: ED K=4 and dense, sorted by input spike count, with the worst-case and the 10 Hz budget line; add the student-driven set as a second series.",
    "TAB: [todo] Success rate per terrain: teacher, FPGA student (58k spiking encoder), stock depth student (reference), ES-Parkour Fig. 5; with episodes per terrain and the protocol line.",
    "TAB: [todo] Robot-frame latency: frame set (teacher-driven / student-driven), frames, input density mean / range, ED mean / worst, dense, ratio, fraction of the 100 ms budget, projected deadline-miss rate at 20 / 50 / 100 Hz.",
]),
(1, "6.9  Discussion and Threats to Validity", [
    "Two crossover axes; on N-MNIST no trained network reaches the C2/C3 crossover while DVS-Gesture straddles the C1 one per clip, now on silicon; the int16 ceiling as the binding constraint on the harder dataset; direct-coding cost (C0047); the tool-vs-meter disagreement once measured; threats to validity (one fabric, 100 MHz, 8-16 samples for cycles vs 264 for accuracy, single seeds where noted, the constant board offsets).",
    "Answer the reader's objections in order: 'the dense engine is unoptimised' (it has the same knobs and the same discipline; its 88 cycles/neuron are within 2 of the model); 'K=P is arbitrary' (iso-resource and iso-latency readings given beside it); 'C1 only on silicon' (C2/C3/FC bit-identical in sim, per-spike constants transfer); 'accuracy is low' (activity is the variable, accuracy reported at every point); 'no physical robot' (simulation-in-the-loop with charged wall-clock).",
    "Generalisation limits: one 28 nm fabric at one clock; a different fabric changes the per-cycle power of banks vs lanes and so the energy crossover but not the cycle one; the cycle model transfers across layers and datasets here, which is the evidence for the claim's scope (C0010).",
    "What would change the conclusion: an 18-bit membrane (removes the T ceiling), a skip-scatter for repeated frames (cuts ED cost at direct coding by up to 4x on the scatter term), an event-driven FC on silicon (C0015), a per-rail meter (separates PS from PL).",
    "TAB: [todo] Threats to validity: threat, type (internal / external / construct / statistical), mitigation taken, residual risk, section.",
]),
(0, "7  Conclusion and Future Work", [
    "Close the loop from Chapter 1 with numbers attached. 4-6 pages.",
]),
(1, "7.1  Summary of Findings", [
    "Answer RQ1-RQ3 in three paragraphs; revisit each objective from 1.3 with its number.",
    "RQ1: crossover at K=P ~6 on both datasets (silicon-bracketed) and ~30 % input density per clip (silicon); trained-activity crossovers 43-57 % at K=P=4 falling to 26-44 % at 16 (sim). RQ2: TODO the measured ratio vs the tool's 3.1-3.2x. RQ3: the worst-case verdict flips on DVS-Gesture (dense wins the densest clips) and narrows on the robot frames (1.94x mean -> 1.43x worst).",
    "One paragraph on the methodological finding (verification on one dataset is not verification; pre-registration caught one wrong model term and rejected two wrong bitstreams).",
]),
(1, "7.2  Limitations", [
    "C1 on silicon (all layers bit-identical in simulation); one board; energy at the board input (or TODO); no physical robot -- simulation-in-the-loop with charged wall-clock; T=4 as built (int16); one seed where noted; the recreation's student success was low for both sizes (distillation budget, not capacity).",
    "Meter limitations once known: DMM resolution vs delta size, regulator efficiency assumed, temperature bounded not controlled, one measurement point (12 V) rather than per rail.",
]),
(1, "7.3  Future Work", [
    "18-bit membranes or fc k=7 (C0046); consecutive-window student (C0047); FC on silicon (C0015); skip-scatter for repeated frames; Nexys 4 DDR portability point; the physical Go1/Go2; per-rail INA226 rig; the perception-rate sweep with the FPGA in the loop.",
    "Order them by what each would change in the conclusion (from 6.9), and give each one sentence of expected effect with a number where the cycle model already predicts it (e.g. skip-scatter removes up to 3/4 of the 71.7 s/K term at direct coding).",
]),
(0, "References", [
    "IEEE style; Zotero/BibTeX. Must include: ES-Parkour (ICME 2025, DOI 10.1109/ICME59968.2025.11209556), extreme-parkour, IsaacGym, snnTorch, N-MNIST, DVS-Gesture, Harmeling et al. NCE 2026, Cheng TCAS-I 2025, Cerebron TVLSI 2022, Li TCAS-I 2021, Minitaur TVLSI 2014, FireFly-P 2026, Nagy et al. (Loihi 2), Guerra-Hernandez et al. 2017, Mahowald (AER), TrueNorth / Loihi / SpiNNaker overview papers, Xilinx UG907 (power analysis) for how report_power works.",
]),
(0, "Appendices", [
    "A. Verilog listings (lif_update, conv_layer_p, ed_scatter, ed_conv_layer, axis_conv, axis_conv_top).",
    "B. The decision log (docs/decisions.md) and the corrections review (docs/corrections.md, C0001-C0047) with status.",
    "C. Protocols: framed UART, BURST, the metering pre-registration and DMM procedure, pre-card-write checklist, build and card-writing procedure (docs/vivado_session_next.md, docs/vivado_new_project.md).",
    "D. Pre-registrations and outcomes (experiments/*prereg*.md, experiments/dvsgesture/silicon_prereg_20260919.md, measure/metering_prereg_2026-09-19.md).",
    "E. Cycle-model fits and the results ledger (docs/results_ledger.md).",
    "F. Reproduction: check_all.sh, exporters, robot/isaac scripts -- listed, not printed.",
    "G. Raw metering logs (measure/) and the power reports (experiments/power_estimates/*_summary.txt) once the meter has run.",
]),
]


def field(paragraph, instr):
    """Insert a Word field (e.g. TOC) into a paragraph."""
    r = paragraph.add_run()
    for t, extra in (("begin", None), (None, instr), ("separate", None), (None, "Right-click -> Update Field (F9)"), ("end", None)):
        if t:
            fc = OxmlElement("w:fldChar"); fc.set(qn("w:fldCharType"), t); r._r.append(fc)
        elif extra == instr:
            it = OxmlElement("w:instrText"); it.set(qn("xml:space"), "preserve"); it.text = instr; r._r.append(it)
        else:
            tx = OxmlElement("w:t"); tx.text = extra; r._r.append(tx)


def build(path):
    doc = Document()
    doc.styles["Normal"].font.name = "Calibri"; doc.styles["Normal"].font.size = Pt(11)
    # title page
    for text, size, bold, gap in (("[ THESIS TITLE ]", 20, True, 6),
                                  ("e.g. Measured, Not Estimated: Energy and Latency of Dense and Event-Driven Spiking Neural Network Datapaths on an FPGA, with a Learned Quadruped Perception Workload", 11, False, 3),
                                  ("by", 12, False, 1), ("Dhriti Aravind", 14, True, 3),
                                  ("A thesis submitted to the Faculty of Graduate and Postdoctoral Affairs\nin partial fulfillment of the requirements for the degree of", 11, False, 2),
                                  ("Master of Applied Science", 12, True, 1), ("in", 11, False, 1),
                                  ("Electrical and Computer Engineering", 12, False, 3),
                                  ("Carleton University\nOttawa, Ontario", 11, False, 3),
                                  ("© [ Year ], Dhriti Aravind", 11, False, 0)):
        p = doc.add_paragraph(); p.alignment = WD_ALIGN_PARAGRAPH.CENTER
        r = p.add_run(text); r.font.size = Pt(size); r.bold = bold
        for _ in range(gap): doc.add_paragraph()
    p = doc.add_paragraph(); p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    r = p.add_run("Outline revised %s. Living document (untracked; regenerate with docs/thesis_outline_build.py). Bullets: RESULT = a number that exists, TODO = not yet, WHERE = where the material lives. Delete the italic guidance as you write." % REVISED)
    r.italic = True; r.font.size = Pt(9)
    doc.add_paragraph().add_run().add_break(WD_BREAK.PAGE)
    # front matter with live fields
    doc.add_heading("Abstract", 1)
    for level, title, bullets in OUTLINE:
        if title == "Abstract":
            guidance(doc, bullets); break
    for title, instr, note in (("Table of Contents", 'TOC \\o "1-3" \\h \\z \\u', "Live field: right-click -> Update Field (F9) after writing headings."),
                               ("List of Tables", 'TOC \\h \\z \\c "Table"', "Live field; populates once tables have captions."),
                               ("List of Figures", 'TOC \\h \\z \\c "Figure"', "Live field. Already generated from the data (experiments/figures/, re-run make_figures.py after any sweep or board pass): fig_kp_sweep (latency vs K=P, silicon overlaid), fig_dvsg_perclip (per-clip crossover, sim and board), fig_activity_c2c3 (ED advantage vs trained activity, both datasets), fig_accuracy_vs_activity (3-seed error bars), fig_tsweep_int16 (accuracy and fc range vs T with the int16 ceiling). Still to draw: system figure, both datapath block diagrams, the measurement rig, energy figures (TODO meter), student success rates and GIF stills.")):
        doc.add_heading(title, 1)
        n = doc.add_paragraph(); rr = n.add_run(note); rr.italic = True; rr.font.size = Pt(9)
        field(doc.add_paragraph(), instr)
    plan_table(doc)
    for level, title, bullets in OUTLINE:
        if title == "Abstract":
            continue
        doc.add_heading(title, 1 if level == 0 else 2)
        if title == "List of Acronyms":
            for b in bullets:
                doc.add_paragraph(b, style="List Bullet")
            doc.add_paragraph("[ Add/trim as needed; expand every acronym at first use in the body too. ]").runs[0].italic = True
            continue
        guidance(doc, bullets)
    doc.save(path)


def plan_table(doc):
    """Collect every FIG:/TAB: bullet into one table: section, type, status, description."""
    doc.add_heading("Figure and Table Plan", 1)
    n = doc.add_paragraph(); rr = n.add_run("Every recommended figure and table, collected from the section bullets below. 'exists' = generated or transcribed already (path given); 'todo' = to make. Delete this page before submission.")
    rr.italic = True; rr.font.size = Pt(9)
    rows = []
    for level, title, bullets in OUTLINE:
        if title == "List of Acronyms": continue
        for b in bullets:
            for key in ("FIG:", "TAB:"):
                if b.startswith(key):
                    rest = b[len(key):].strip()
                    m = re.match(r"\[(exists|todo)\]\s*(.*)", rest, re.S)
                    status, text = (m.group(1), m.group(2)) if m else ("?", rest)
                    rows.append((title.split("  ")[0], key[:-1], status, text))
    t = doc.add_table(rows=1, cols=4); t.style = "Light Grid Accent 1"
    for c, h in zip(t.rows[0].cells, ("Section", "Type", "Status", "Description")):
        c.text = h
    for sec, kind, status, text in rows:
        cells = t.add_row().cells
        cells[0].text, cells[1].text, cells[2].text, cells[3].text = sec, kind, status, text
    for row in t.rows:
        for c in row.cells:
            for para in c.paragraphs:
                for run in para.runs: run.font.size = Pt(8)
    nf = sum(1 for r in rows if r[1] == "FIG"); nt = len(rows) - nf
    ne = sum(1 for r in rows if r[2] == "exists")
    doc.add_paragraph("%d figures and %d tables planned; %d exist, %d to make." % (nf, nt, ne, len(rows) - ne)).runs[0].italic = True
    doc.add_paragraph().add_run().add_break(WD_BREAK.PAGE)


def guidance(doc, bullets):
    h = doc.add_paragraph(); r = h.add_run("Write in this section:"); r.bold = True; r.italic = True; r.font.size = Pt(10)
    for b in bullets:
        para = doc.add_paragraph(style="List Bullet")
        for key, colour in (("RESULT:", GREEN), ("TODO:", RED), ("WHERE:", BLUE), ("FIG:", PURPLE), ("TAB:", ORANGE)):
            if b.startswith(key):
                rr = para.add_run(key + " "); rr.bold = True; rr.italic = True; rr.font.color.rgb = colour
                b = b[len(key):].strip(); break
        parts = b.split("WHERE:")
        rr = para.add_run(parts[0]); rr.italic = True
        for extra in parts[1:]:
            rr = para.add_run("WHERE:"); rr.bold = True; rr.italic = True; rr.font.color.rgb = BLUE
            rr = para.add_run(extra); rr.italic = True
        for run in para.runs: run.font.size = Pt(10)
    ph = doc.add_paragraph(); r = ph.add_run("[ Begin your prose here. Delete the italic guidance above as you write. ]"); r.italic = True; r.font.size = Pt(10)


if __name__ == "__main__":
    build("docs/thesis_outline.docx"); print("wrote docs/thesis_outline.docx")
    if os.path.isdir(ONEDRIVE):
        dst = os.path.join(ONEDRIVE, "Thesis_Outline_updated_%s.docx" % REVISED)
        shutil.copy("docs/thesis_outline.docx", dst); print("copied to", dst)
