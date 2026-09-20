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

REVISED = "2026-09-20u"
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
    "RESULT: numbers to quote once final: ED K=4 beats dense P=4 by 1.52x on silicon (688.5 vs 1,048.9 us); dense wins at K=P=8 (540.3 vs 575.5 us); on DVS-Gesture ED wins 6 of 8 clips on silicon and loses the two densest (1.248x at the mean); accuracy 96.6-97.0 % N-MNIST, 63-69 % DVS-Gesture; robot frames ED 1.73 ms mean / 2.75 worst vs dense 3.60 ms (64 frames, sim).",
    "TODO: the measured-energy sentence (meter) and the student's success rates. No citations, figures or unexpanded acronyms in the abstract.",
]),
(0, "Acknowledgements", [
    "Supervisor (Dr. Ahmadi), committee, the lab's GPU hosts (MI210 box, 1080 Ti box), whoever lends the DMM, the extreme-parkour and snnTorch authors for released code. One page.",
]),
(0, "List of Acronyms", ACRONYMS),
(0, "List of Symbols", [
    "WHERE: docs/notation.md holds the full version, written out for a reader who has not lived in the repository; paste its tables here and trim. It defines, with what each one changes: the network (C1/C2/C3/FC, C_IN/C_OUT, H/W, N as output-neuron count, the 34- and 64-geometries, and the repo's c1/g1/r1/i1 vector-set naming); the neuron (V, I, s, theta, beta, pending, T, and the quantisation shift k); the two engines (dense vs ED, P lanes, K banks, matched parallelism K = P, s as the spike count, N_ENGINES for replication, activity, crossover) with both cost models; the board (PS/PL, LUT/FF/BRAM/DSP, WNS/WHS, AXI/AXI-Stream/DMA, BURST, bitstream); the three energy quantities; and the housekeeping identifiers (M-numbers, D-numbers, C-numbers, golden model, pre-registration).",
    "RESULT (resolved 2026-09-20): N means the output-neuron count and nothing else. The engine replication count is written R (the RTL parameter stays N_ENGINES) and the BURST repeat count is written B (the metering pre-registration calls it N). Say this once in the List of Symbols so a reader moving between the thesis and the repository can translate; do NOT rename the Verilog parameter, which is quoted in ten bitstream provenance strings and in every board record.",
    "Keep the symbol table to one page: only symbols that appear in more than one chapter. Anything used once is defined where it is used.",
]),
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
    "FIG: [exists] (experiments/figures/diagrams/fig_measurement_boundary.svg) Measurement-boundary diagram: 12 V input -> regulators -> PS (ARM, DDR) and PL (fabric) -> engine; shade what a Vivado report covers vs what the shunt sees (C0004, C0026, C0038). One figure, reused in 4.9 and 6.5.",
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
    "RESULT: silicon at 100 MHz, engine-only: ED K=4 688.5 us mean (554.8-815.8) vs dense P=4 1,048.9 us flat; ED K=8 575.5 vs dense P=8 540.3 us; DVS-Gesture ED K=4 2,970.8 us mean vs dense P=4 3,706.5 us flat (6 of 8 clips). Perception workload: teacher 95-99 % success per terrain; on 64 real robot event frames ED K=4 1.73 ms mean / 2.75 ms worst vs dense 3.60 ms (sim).",
    "TAB: [todo] Headline table: one row per result (latency at K=P=4 and 8, per-clip crossover, trained-activity crossovers, T ceiling, energy measured vs estimated, student success), with the basis column (sim / board / gpu) and the section.",
]),
(1, "1.6  Thesis Organization", [
    "One paragraph mapping chapters 2-7: Chapter 2 is the literature review (what the field has established and what it leaves open), Chapter 3 the closest prior work, the threats to validity of energy comparisons and the gap, Chapter 4 the decision log (docs/decisions.md) turned into prose and the mitigations of those threats, Chapter 5 the implementation, Chapter 6 the results with sim or board in every caption and the residual risk per threat, Chapter 7 the answers to RQ1-RQ3.",
]),
(0, "2  Background", [
    "This chapter is a literature review, not a description of the design: each subsection surveys what the field has established (with citations), organises it around the questions the thesis needs answered, and closes with what the literature leaves unsettled -- the design decisions Chapter 4 then makes are cited back to those open points. Implementation specifics (the exact LIF semantics built, the sign-off rules, this thesis's numbers) do not appear here. Target 15-20 pages, ~40-60 references.",
    "Writing pattern per subsection: (1) the concept and the canonical references, (2) the variants in the literature and what each trades, (3) how hardware papers in particular have handled it, (4) one paragraph 'what this leaves open', pointing to the section of Chapter 4 that decides it.",
]),
(1, "2.1  Spiking Neural Networks and the Leaky Integrate-and-Fire Neuron", [
    "Survey neuron models from biophysical to phenomenological: Hodgkin-Huxley, Izhikevich, adaptive exponential, LIF, IF; the surveys to anchor on (Roy, Jaiswal and Panda, Nature 575:607-617, 2019; Tavanaei et al. 2019; Eshraghian et al., Proc. IEEE 2023 'Training SNNs using lessons from deep learning'). Why the accelerator literature converges on IF/LIF: one state variable, add-compare-subtract per update.",
    "Reset semantics in the literature: reset-to-zero vs reset-by-subtraction (Rueckauer et al. 2017 on conversion accuracy; Han et al. 2020 'RMP-SNN'), hard vs soft reset, and the timing of the reset relative to the threshold check as implemented by frameworks (snnTorch snn.Leaky defaults, Norse, SpikingJelly). Point out that papers rarely state which they built, which makes bit-level reproduction impossible -- the gap 4.2 closes by stating it exactly.",
    "Leak implementations in hardware: multiply by beta, shift-based leak (V - V>>k), no leak (IF); what each costs in a fabric and what accuracy it costs in the literature (cite the hardware-cost comparisons in the FPGA accelerator papers of 3.1, e.g. Cerebron's IF choice, Cheng 2025's LIF).",
    "What this leaves open: which exact semantics a hardware implementer should fix so that a software reference and the silicon agree bit-for-bit; whether a shift leak at beta = 0.875 costs accuracy (decided in 4.2 with the beta sweep).",
    "FIG: [exists] LIF membrane trace with input spikes, threshold crossings and delayed subtraction reset (experiments/m0_lif_demo.png), used here as the illustration of the model defined in the literature.",
    "TAB: [todo] Neuron models as used by the surveyed hardware works: model, reset, leak implementation, state bits, arithmetic per update, source paper -- a literature table, not a design table (C0043).",
]),
(1, "2.2  Clock-Driven and Event-Driven Execution of Spiking Networks", [
    "The two execution paradigms and their lineage: address-event representation (Mahowald 1992; Boahen 2000) and the asynchronous digital descendants (TrueNorth, Merolla et al. Science 2014; Loihi, Davies et al. IEEE Micro 2018; SpiNNaker, Furber et al. 2014) vs time-multiplexed, clock-driven neuron update in FPGA accelerators (Cerebron, FireFly, Li 2021).",
    "The theoretical case that event-driven cost is proportional to activity and the counter-case that its fixed machinery is not: Sorbaro et al. 2020 (energy vs activity in neuromorphic hardware); Davidson and Furber, Frontiers 2021 ('Comparison of artificial and spiking neural networks on digital hardware': SNNs lose their advantage above a modest activity); Yik et al. 2025 NeuroBench on how to benchmark; note that every crossover claim in this literature is analytical or simulated.",
    "Event-driven layer engines on FPGA: Minitaur (Neil and Liu, TVLSI 2014) and Cheng et al. (TCAS-I 2025) as the closest designs; how they queue spikes and resolve write conflicts into shared membrane memory (arbiters, sorting, banking); what they compare against (none against a clock-driven twin on the same fabric).",
    "The sweep problem in the literature: leak and threshold must be applied to every neuron every timestep unless neurons are visited lazily (event-driven leak with timestamps, as in Loihi's compartment update) -- the fixed floor that bounds any event-driven design's advantage; how each surveyed work handles it (skip, lazy, or full sweep).",
    "What this leaves open: the crossover activity for a specific fabric at matched parallelism, established by measurement rather than analysis; what 'matched parallelism' should mean when the two designs' work units differ (decided in 4.7, C0029).",
    "FIG: [exists] (experiments/figures/diagrams/fig_paradigms.svg) Schematic of the two paradigms as drawn in the literature (dense time-multiplexed update vs AER queue and scatter), one panel each, with the cost expressions from the cited works.",
]),
(1, "2.3  Event-Based Vision and Input Encoding", [
    "Event cameras: the DVS principle (Lichtsteiner, Posch and Delbruck 2008), the DAVIS and later sensors, and the survey by Gallego et al. (TPAMI 2022) for representations; why event streams suit SNNs (sparse, asynchronous, polarity-coded).",
    "Event representations for networks: binary frames, event counts, time surfaces (Lagorce et al. 2017 HOTS), voxel grids (Zhu et al. 2019), and direct (repeated-frame) coding vs rate coding vs latency coding for SNN inputs (Guo et al. 2021 on coding schemes; Kim et al. 2022 on rate vs direct coding accuracy and robustness). What each discards and what each costs an event-driven engine (repeated frames repeat the scatter).",
    "Simulated events from conventional frames: ESIM (Rebecq et al. 2018), v2e (Hu et al. 2021), and the frame-difference-with-threshold approximation used by ES-Parkour on depth; the gap between simulated and real event statistics reported in that literature.",
    "The standard datasets and their published statistics: N-MNIST (Orchard et al. 2015) and DVS-Gesture (Amir et al. CVPR 2017); accuracies reported at various network sizes and T (so the reader can place the 58k-parameter results of Chapter 6).",
    "What this leaves open: the activity distribution a hardware engine actually sees depends on the encoding chosen (binarisation, T, window) -- an encoding decision (4.10, D0003, C0047) rather than a dataset property.",
    "FIG: [exists] (experiments/figures/fig_inputs.png: N-MNIST sample, DVS-Gesture clip and robot event frame as T=4 binarised ON/OFF frames plus their OR, with densities) An N-MNIST sample as T=4 binarised frames per polarity (experiments/m0_nmnist_sample.png); pair with a DVS-Gesture clip and a simulated robot event frame at the same scale as the illustration of the representations discussed.",
    "TAB: [todo] Published results on N-MNIST and DVS-Gesture: work, network, parameters, T, accuracy -- to situate the accuracy this thesis accepts in exchange for a fabric-sized network.",
]),
(1, "2.4  FPGA Architecture, Timing Closure and Power Estimation", [
    "The Zynq-7000 class of SoC FPGA (PS + PL) and the 7-series fabric primitives (LUT6, FF, BRAM36, DSP48E1) from the vendor documentation (UG474, UG473); what an SoC FPGA adds for a host-in-the-loop experiment (DMA, AXI) and what it costs (a 1.5 W processor beside a 50 mW datapath).",
    "On-chip memory as the binding constraint for SNN accelerators in the literature: every surveyed FPGA design keeps weights and state in BRAM; off-chip DRAM access energy vs a MAC (Horowitz, ISSCC 2014: ~200x) as the reason; how designs trade replication against memory.",
    "How vendor power estimation works and what is known about its accuracy: Vivado's report_power methodology (UG907), vectorless vs SAIF-driven activity, the switching-activity warning; academic assessments of estimator accuracy against measurement on FPGAs: PowerGear (Lin et al., DATE 2022, 10.23919/DATE54114.2022.9774682) measured nine HLS designs on a ZCU102 rail against Vivado post-implementation + SAIF and found an average total-power error of 21.8 % (11-28 %), with Vivado ignoring the power gating of unused hard blocks; HL-Pow (ASP-DAC 2020) is its on-board-ground-truth precursor. The finding to extract: even with SAIF the tool is off by tens of percent, and vectorless (this thesis's reports) is looser still (docs/references_verified.md).",
    "Board-level power measurement practice on development boards: onboard PMBus/INA226 rails (ZCU102/104, PYNQ-Z1) vs boards without them (ZedBoard), inline shunts and current monitors, idle-vs-active deltas; papers that report both an estimate and a measurement, in any domain, and the gap they saw.",
    "What this leaves open: for an event-driven datapath with data-dependent activity, whether vectorless estimation is even meaningfully defined, and how large the estimate-to-meter gap is on a 28 nm fabric -- the question of 4.9 and 6.5.",
    "FIG: [todo] Zynq-7020 block diagram (PS, DDR, HP ports, AXI DMA, PL) drawn from the vendor reference, with the power-report boundary and the board-input measurement boundary marked -- reused in 4.9.",
]),
(1, "2.5  Benchmarks and the Quadruped Perception Workload", [
    "Learned legged locomotion in simulation-to-real: Lee et al. Science Robotics 2020, Rudin et al. CoRL 2021 / PMLR 164 (massively parallel IsaacGym training), Cheng et al. ICRA 2024 (extreme parkour: scandots teacher, depth student by DAgger; arXiv 2023), Zhuang et al. 2023 (robot parkour learning); the teacher-student recipe as the field's standard.",
    "Event cameras and spiking networks on robots: ES-Parkour (Zhang et al., ICME 2025: events from depth at 10 Hz, spiking ResNet-18, theoretical energy in Table III), Guerra-Hernandez et al. 2017 (FPGA SNN CPG on a quadruped), and TODO: two or three event-vision drone/legged perception works 2022-2026; the recurring pattern that energy is reported as counted operations.",
    "Why perception latency is a correctness constraint in this setting: control periods (10-50 Hz), the effect of stale observations in learned policies (cite works on action/observation delay in RL locomotion), and the deadline-miss framing from real-time systems.",
    "What this leaves open: how a fabric-sized spiking encoder performs inside the paper's own pipeline, and what its latency distribution looks like on real event frames -- 4.10 and 6.8.",
    "TAB: [todo] Legged-locomotion perception works: work, sensor, network, simulator, success metric, energy reported and how obtained.",
]),
(1, "2.6  Training and Fixed-Point Quantisation of Spiking Networks", [
    "Training methods: ANN-to-SNN conversion (Rueckauer 2017; Sengupta 2019) vs direct training with surrogate gradients (Neftci, Mostafa and Zenke 2019; Wu et al. 2018 STBP); frameworks (snnTorch, SpikingJelly, Norse); why direct training is preferred at small T.",
    "Quantisation for SNN hardware: integer weights with power-of-two scales, post-training vs quantisation-aware (Jacob et al. 2018 for ANNs; Putra and Shafique 2021 'Q-SpiNN'; Brevitas), membrane bit-width choices in the surveyed accelerators (typically 16-bit) and any reported overflow handling; the observation that membrane range is rarely characterised.",
    "Activity control during training: rate regularisation (Sorbaro 2020; Pellegrini et al. 2021 low-activity SNNs), threshold scaling, and reports of the accuracy-activity trade-off -- the literature's version of the thesis's activity axis (4.9's regulariser).",
    "What this leaves open: whether int16 membranes suffice across T and activity for a given geometry (a Chapter 6 result), and how much activity can be traded for accuracy on the two benchmarks at this network size.",
    "FIG: [exists] Per-layer firing rate and accuracy per epoch on N-MNIST (experiments/m0_firing_rates_binarised.png) as the illustration of the activity-accuracy behaviour the literature describes.",
]),
(0, "3  Related Work", [
    "Closest prior work, grouped, each group closed with what it did not do; then the threats to validity that the literature and the corrections review identify for energy comparisons; then the gap statement. A comparison table with a 'power obtained by' column is the chapter's centrepiece (docs/baseline_table.md). Target 10-15 pages.",
]),
(1, "3.1  FPGA Accelerators for Spiking Neural Networks", [
    "RESULT: rows transcribed 2026-09-19 -- Harmeling NCE 2026, Cheng TCAS-I 2025 (ZCU104, 96.0 % N-MNIST, Vivado + SAIF), Cerebron TVLSI 2022 (XC7Z100, on-chip power report), Li TCAS-I 2021 (VC707, Vivado + SAIF), Minitaur TVLSI 2014 (idle/peak watts, method unstated), FireFly-P 2026 (Artix-7, post-implementation report). Four of five state a Vivado estimate; none measures at a board input. FireFly-S (TCAS-I 72(8) 2025, KV260 at 333 MHz, 92.05 % DVS-Gesture, 1.3-3.8 W 'derived from the reports generated by the Vivado Design Suite') and Spiker+ (TETC 13(3) 2025, XC7Z020 -- the ZedBoard's fabric -- at 100 MHz, MNIST 93.85 % at 780 us / 180 mW, 7,612 logic cells / 18 BRAM, power from synthesis) added 2026-09-20: seven of seven surveyed rows are tool estimates. DOIs for every row in docs/references_verified.md and docs/references.bib.",
    "For each work: fabric, network and dataset, accuracy, resources, clock, latency, how power was obtained, energy per inference as reported. Then the pattern: energy claims rest on report_power with or without SAIF, boundaries unstated, static power sometimes excluded.",
    "Place this thesis's numbers in the same columns (N-MNIST 96.6-97.0 %, ZedBoard, ~3.4k-5.8k LUT, 0.69-1.05 ms at 100 MHz, energy TODO measured) so the reader sees it is a small, slow, honestly-measured design rather than a state-of-the-art accelerator.",
    "TAB: [exists] The baseline table (docs/baseline_table.md): work, platform, network/dataset, accuracy, LUT/FF/BRAM/DSP, clock, latency, power method, energy per inference; add a 'this thesis' row at the bottom.",
]),
(1, "3.2  Event-Driven and Address-Event Architectures", [
    "Minitaur's event-driven DBN and Cheng's event-driven neuron update as the closest architectural relatives; how their queue/bank schemes differ from the K-bank scatter here; none compares against a clock-driven twin on the same fabric.",
    "Chip-scale event-driven systems (TrueNorth, Loihi, SpiNNaker) as context only: their energy numbers are for whole chips with routers and cores, not for one layer engine, and are measured by the vendor rather than by an independent board-level meter. One page.",
    "The bank-conflict problem in the literature (scatter-add into shared membrane memory) and the choices others made (arbiters, sorting, replication); the channel-interleaved K-bank choice here avoids an arbiter by construction (Section 4.6).",
]),
(1, "3.3  Neuromorphic Perception and Control for Legged Robots", [
    "Guerra-Hernandez et al. 2017 (FPGA SNN CPG on a quadruped, 6 hand-designed neurons, no camera); ES-Parkour (event camera + spiking ResNet-18, theoretical energy); extreme-parkour as the base recipe. No 'first' claims; the difference is a learned vision network and measurement.",
    "Event-camera robot perception 2022-2026 (verified, docs/references_verified.md): Paredes-Valles et al., Science Robotics 2024 (event-camera drone landing on Loihi; 0.94 W idle plus 7-12 mW -- a measured chip-level number, with the idle floor dominating exactly as C0038 predicts); CEAR quadruped event-camera dataset (RA-L 2024); Bhattacharya et al., CoRL 2024 (event-vision quadrotor, no power reported); Lopez-Osorio 2024 (hexapod on SpiNNaker), Jiang 2024 (Loihi, wheeled) as alternates. The pattern: either no energy at all or a chip-vendor figure; ES-Parkour's Table III (theoretical) is the one closest to this workload.",
    "Why the encoder and not the whole policy is the hardware target: the encoder is the bulk of the compute per frame, the GRU/MLP policy is small and stays on the host; the 58k geometry was chosen to fit the fabric on-chip (docs/environment.md).",
]),
(1, "3.4  Measured versus Estimated Energy in Neuromorphic Systems", [
    "The Loihi 2 vs GPU study (Nagy et al.: 3-3.5 W vs > 50 W, R^2 0.89 vs 0.94 -- power, not energy per inference); why tool estimates and meters can rank designs differently; the C0022 addendum's 2026 paper that states this thesis's question as open.",
    "FPGA works that DID measure (verified, docs/references_verified.md): FINN (Umuroglu et al., FPGA 2017) reports chip power via PMBus and wall power via a meter on a ZC706 but no tool estimate beside them; PACOX (arXiv 2601.04827, 2026) reports both a Vivado estimate (0.33 W) and an INA226 measurement on a ZCU102; Al Hafiz et al. 2025 (arXiv) uses INA226 on a ZCU104 and argues the same board-vs-execution boundary as C0004/C0038. The practice exists and is cheap; none of the SNN rows in 3.1 follows it -- and Spiker+ (TETC 2025) and Harmeling both state in print that the most power-efficient accelerators are clock-driven, on tool numbers.",
    "The formal statement this thesis tests (C0027): the tool's ratio of dense to ED energy vs the meter's ratio; agreement in sign, in magnitude, or neither; each outcome and what it would mean for the surveyed papers' claims.",
]),
(1, "3.5  Threats to the Validity of Energy Comparisons", [
    "Threats drawn from the literature above and from the project's own corrections review (docs/corrections.md), stated here BEFORE the design so that Chapter 4 can be read as the mitigations and Chapter 6 reports the residual risk of each. Group them as construct, internal, external and statistical validity.",
    "Construct validity (is the number the thing claimed?): power reported instead of energy per inference (Nagy et al.; C0007); the measurement boundary unstated -- fabric delta vs board input vs per control period (C0004, C0038); a single replayed sample's energy presented as the design's (C0018); theoretical operation counts presented as energy (ES-Parkour Table III; every SNN accelerator row of 3.1).",
    "Internal validity (could something else explain the difference?): static and idle power omitted or measured once rather than per bitstream (C0001); no noise floor before comparing deltas (C0002); implementation-seed and placement variance (C0019); die temperature differing between idle and active windows (C0009, C0020); the wrapper and host attributed unevenly to the two designs (C0014, C0041); an unfair baseline with no parallelism knob (C0029) and comparison at iso-frequency only (C0021); regulator non-linearity between the measurement point and the fabric (C0026).",
    "External validity (does it generalise?): one fabric, one clock, one network size (C0010); synthetic Bernoulli activity in place of spatially clustered real events (C0040); one dataset -- and the demonstrated case that bit-identity on a centred dataset hid an RTL bug (C0044); direct coding vs windowed encoding changing the activity the engine sees (C0047); three geometries conflated in a log (C0036).",
    "Statistical validity: 8-16 samples for cycle checks vs 264 for accuracy; single seeds; unresolvable deltas at the meter's floor (C0003); class-biased sample sets (C0039, C0016); no confidence intervals in the surveyed works. RESULT (C0050): on this project's own GPU host, training is not reproducible at a fixed seed -- two runs of identical code and seed put the DVS-Gesture fc membrane at 98 % and 102 % of int16, on either side of the overflow boundary, with 1.1 pp of accuracy difference. Any claim resting on a single training run, in this thesis or in the surveyed works, inherits that noise; cycle counts do not (simulation is exactly reproducible).",
    "For each threat name which surveyed works it applies to (from their methods sections) and the forward reference to the mitigation in Chapter 4 (pre-registration, replication, idle-per-bitstream, randomised order, three runs, corner sets, two datasets, K = P with iso-resource reported).",
    "TAB: [todo] Threats to validity: threat, type (construct / internal / external / statistical), source (paper or C-number), prior work affected, mitigation in this thesis (section), residual risk to be reported in 6.9.",
]),
(1, "3.6  Summary of the Gap", [
    "Same-fabric clock-driven vs event-driven comparison with bit-identical outputs, board-measured energy, swept over parallelism and activity, on a learned perception workload, with the threats of 3.5 addressed by design: not present in any row above.",
    "TAB: [todo] Gap matrix: rows = surveyed works plus this thesis; columns = same-fabric twin, bit-identical to a reference, activity sweep, parallelism sweep, measured energy, learned perception workload, threats addressed; tick marks. This is the one table a reader remembers from the chapter.",
]),
(0, "4  System Design and Methodology", [
    "Top-down: goals and system, neuron, network and budget, each datapath, the banking scheme, the comparison methodology, hardware considerations, the measurement methodology, and the perception workload in simulation. Every judgement call is a D-number in docs/decisions.md; this chapter is that log turned into prose. Target 30-40 pages, the longest chapter.",
]),
(1, "4.1  Design Goals and System Overview", [
    "Constraints: local simulation with a golden-model contract, Vivado in a VM, everything on-chip, hand-written Verilog for both datapaths. System figure: Mac -> framed UART -> bare-metal server -> AXI DMA -> AXIS wrapper -> ENGINE (dense | ED) -> back. Walk the loop once.",
    "The flow from data to silicon: train (GPU) -> quantise (npz) -> golden model -> exported vectors -> testbench -> baked RTL -> synthesis (VM) -> SD card -> board pass against the same vectors. Say which artefact is the contract at each arrow.",
    "Design goals ranked: (1) bit-identity, (2) same wrapper and host for both engines, (3) resolvable energy delta, (4) parallelism as a parameter, (5) simplicity over throughput -- and what was traded for each (e.g. no inter-layer chaining on silicon, C0034).",
    "FIG: [exists] (experiments/figures/diagrams/fig_system.svg) System block diagram: host Mac, UART link with CRC framing, Zynq PS running conv_server, AXI DMA, AXIS wrapper with the ENGINE parameter, the engine, DDR buffers; label the timing boundary (engine-only ticks vs wrapper-inclusive).",
    "FIG: [exists] (experiments/figures/diagrams/fig_toolflow.svg) Toolflow diagram from training to board pass (the arrow list above), with the check at each arrow (golden check, testbench, lint, WNS gate, PING build/dataset check, CRC).",
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
    "FIG: [exists] (experiments/figures/diagrams/fig_dense_datapath.svg) Dense datapath block diagram: input frame memory, P lanes, weight ROM addressing, shared lif_update, per-lane membrane bank, output word bank; annotate the 22 cycles per neuron per timestep.",
    "TAB: [todo] Dense cost per layer and P: predicted 88 N/P vs simulated cycles for C1/C2/C3 on both geometries (from experiments/latency_sim and rate_sweep*/bench), error column.",
]),
(1, "4.5  Event-Driven Datapath: Spike Queue, Scatter and Sweep", [
    "Scatter unit: decode one spike's (channel, row, col), add its weight column into every output neuron it touches (at most a 2x2 block x C_OUT); then the two-beat pipelined sweep (C0030: 2 cycles/neuron) applies the LIF update and zeroes each neuron's current at its read beat; word-parallel output (C0035). Addresses travel as packed fields, never flat indices (a divide on an address path cost 12 ns).",
    "Cost model: cycles = 2NT (sweep) + 5.0 s (FIFO pump, K-independent) + 71.7 s/K (scatter) -- the 5.0 term was found by a pre-registration miss. Per-spike constants transfer across datasets and layers (C2 40.4 vs 41.0, C3 74.0 vs 76.4). Direct coding makes the scatter repeat the same frame T times (C0047).",
    "RESULT: the sweep bug (C0044): the current-zero write was gated on the update pipeline's valid flag, so neuron 0 was never cleared; invisible on N-MNIST (zero corner exposure), caught by DVS-Gesture. hdl/eventdriven/ed_conv_layer.v.",
    "The three phases of one timestep and what bounds each: (i) address-list fill from the input frame, (ii) scatter, s spikes x (fan-out / K) cycles, (iii) sweep, 2N cycles. Which phase dominates at which activity, and why K only helps phase (ii).",
    "Stride-2 3x3 fan-out geometry: an input spike touches at most a 2x2 block of output positions x C_OUT channels; edge spikes touch fewer (corner exposure); how the scatter walks that block.",
    "FIG: [exists] (experiments/figures/diagrams/fig_ed_datapath.svg) Event-driven datapath block diagram: input frame -> spike address list -> scatter unit (weight column fetch, K bank adders) -> K membrane banks -> two-beat sweep pipeline -> output words. Annotate the three cost terms on the blocks that cause them.",
    "FIG: [todo] Timeline of one inference at two activities (e.g. 9 % and 44 % clips): fill / scatter / sweep bars per timestep for K=4, showing the fixed sweep and the growing scatter; from the testbench's phase counters.",
    "TAB: [todo] Cycle-model terms: term, meaning, fitted constant, how found (fit / pre-registration miss), datasets it was checked on, error.",
]),
(1, "4.6  Spike Address List and Banked Membrane Memory", [
    "The address list is sized for the worst case (every input firing once) so it can never overflow (D0016); K channel-interleaved banks so K read-modify-writes land per cycle with no arbiter; K must divide C_OUT; K in {1, 2, 4, 8, 16} simulated, 4 and 8 on silicon. One write + one read port per bank (the multi-ported first version could not map to BRAM).",
    "Design options considered for the banks (arbitrated shared memory, output-row interleave, channel interleave, full replication) with the trade-off each makes (conflict rate, BRAM, logic, timing); why channel interleave is conflict-free for this fan-out pattern (D0017).",
    "Worst-case sizing as a deliberate trade (C0032): what it costs in BRAM at each geometry vs the risk of an overflow path that would need a stall or a drop, both of which would make latency non-deterministic in a way the deadline analysis could not bound.",
    "The two-word neuron state (membrane + current) and whether it is structural or an ordering artefact (C0033); the answer chosen and its BRAM cost.",
    "FIG: [exists] (experiments/figures/diagrams/fig_bank_interleave.svg) Bank interleaving diagram: output channels striped across K banks, one spike's 2x2 x C_OUT footprint landing K-wide per cycle.",
    "RESULT (memory cost of K, derived from primitive geometry and verified against both built engines, 2026-09-20): each bank holds 4,624/K x 16 bits against an 18,432-bit RAMB18, the smallest primitive the fabric has. From K=2 to K=8 the per-bank primitive halves exactly as the bank count doubles, so bank memory is FLAT at 4.0 tiles; at K=16 it cannot halve again and doubles to 8.0. K=8 is therefore the largest bank count that costs no extra block RAM -- a hardware reason to stop there that is independent of the energy argument, and it converges with the pre-registered energy prediction (measure/k_energy_prereg_2026-09-20.md, K5)."
    "RESULT (C0052, a cost that is not the banks): the 288-byte weight table is read K-wide in one cycle, so synthesis replicates it into K/2 dual-port primitives -- 1.0 tile at K=4, 4.0 at K=16, where 147,456 bits hold 2,304 at 1.6 % utilisation. It also decides whether the K=16 engine replicates eight times (142 tiles of 140 as built, 110 with the table in distributed RAM). Report the table's share separately from the banks' so the sweep is not read as "the memory cost of parallelism" when part of it is a fixable artefact; the RTL is deliberately unchanged so the sweep measures the design its predictions were written against."
    "TAB: [todo] K options: K, banks, adders, BRAM tiles per engine (banks and weight table separately), WNS on silicon where built, cycles at the mean N-MNIST and DVS-Gesture sample.",
]),
(1, "4.7  A Shared Wrapper for Matched-Parallelism Comparison", [
    "One AXIS wrapper with an ENGINE parameter (D0021): identical framing, DMA path, server, client and vectors; baked weights for synthesis; the DATASET knob selecting table + geometry + threshold together (decision 2026-09-18); matched parallelism K = P. BURST mode with engine-only ticks (server build 4/5); PING reports build and dataset.",
    "Cycle models as the prediction instrument: derivation, fit, the validation standard (0.3 % per sample on a second dataset before predicting with it), a table of every model-vs-measurement comparison (board +0.4 to +1.5 %; the DVS-Gesture 'offsets' of 92.9 / 102.0 us turned out to be a comparison-basis artefact -- against wrapper-inclusive harness totals the board is +29.4 us ED / +20.0 us dense, constant).",
    "Pre-registration practice: predictions committed before every silicon pass (experiments/*prereg*.md); one where everything held (dense P=4), one where a hypothesis failed and was recorded (DVS-Gesture ED K=4 offset). The pre-card-write checklist and the deliveries it rejected.",
    "Why K = P is the fair axis, told as the history it is (C0029 -> D0026): the event-driven engine always had a parallelism knob (K banks), the first dense engine had none -- one tap per cycle, single-issue -- so the original headline compared a 4-wide engine against a 1-wide one, and a reviewer would have found that first. The dense engine was then given the SAME partition the scatter already used, output channels split by channel mod P, so K and P count the same unit of hardware and K = P is matched by construction rather than by assertion. RESULT: when the dense engine got its knob the C1 verdict flipped -- dense P=4 beat ED K=4 by 8 % in simulation -- which is how the crossover was found at all; state plainly that the fair baseline cost the thesis its original headline and gave it a better one. Then the two alternative framings and why each is reported beside K=P rather than instead of it: iso-resource / matched area (the honest asymmetry is state, not logic -- ED costs about half the LUTs and twice the BRAM at K=P=4) and iso-latency (C0021, open: clock the faster engine down to the deadline and compare energy there, which is what a control loop actually cares about).",
    "The wrapper's own cost (C0014, C0035, C0041): 6.3k-8.2k cycles per inference of framing and DMA; how it is attributed and why engine-only ticks are reported for latency but wrapper-inclusive totals are used for board-vs-sim comparison.",
    "FIG: [todo] Wrapper block diagram: AXIS in/out, frame parser, engine instance (ENGINE, DATASET, K or P, N_ENGINES), tick counter, CRC, the replicated-engine fan-out used for the metering builds.",
    "TAB: [exists] (docs/thesis_tables/passes.md from experiments/silicon_ledger.md; per-sample predicted-vs-board columns are in each record) Prediction vs measurement for every silicon pass (1-14): build, predicted cycles/latency, measured, error, pre-registered hypotheses held/failed.",
]),
(1, "4.8  Golden-Model Verification Methodology and Hardware Constraints", [
    "Fixed point: int8 weights (power-of-two scales), int16 membranes, integer thresholds 2^k, shift leak; no multiplier anywhere in the datapath. The int16 membrane budget as a real constraint: overflows on DVS-Gesture at T=16, at T=8 for one seed in three, and at 34 % activity on every seed (C0046) -- the options (18-bit, fc k=7, T=4).",
    "The golden-model rule as the central engineering contract: bit-identical, never close; corner-exposure reporting per check set (N-MNIST blind at all four C1 corners, the robot depth stream at the top two, only the synthetic set covers all four).",
    "What bit-identity does and does not prove: it proves the RTL computes the same function on the vectors tried; it does not prove port discipline, address timing, synthesis-tool behaviour, or coverage of untried input patterns -- each of those got its own check (lint_synth_safety, hostile-handshake wrapper bench, AXIS stress, corner set).",
    "Sample-set discipline: the class bias of the first check set (C0039) and the unbiased DVS-Gesture clip set; why 16 and 8 samples are enough for cycle checks (every sample is a full bit-identity test) but not for accuracy.",
    "FIG: [exists] (experiments/figures/diagrams/fig_verification_flow.svg) Verification flow: trained npz -> golden model -> vector files (inputs, expected outputs, threshold) -> testbench compare -> baked RTL -> board compare over the link; the ladder as the set of arrows.",
    "TAB: [exists] (docs/thesis_tables/vector_sets.md) Vector sets and their corner exposure: set, geometry, layer, samples, spikes per sample (range), corner-neuron activity count per corner, what it can and cannot catch (from sim/corner_exposure.py output).",
]),
(1, "4.9  Energy Measurement Methodology and Pre-Registration", [
    "The metering protocol, pre-registered (measure/metering_prereg_2026-09-19.md): 0.1 ohm shunt + mV reading on the 12 V input (0.1 mA resolution), idle-run-idle with timer cross-check, 3 runs x 15 readings, SEM, drift and resolvability flags, randomised order; the bitstream matrix (x8 replications first for a resolvable delta, then single engines, then DVS-Gesture per clip); the three energy quantities (C0038). Also available for the meter: C0019 implementation-strategy bitstreams (Performance_Explore, Congestion_SpreadLogic_high vs default) of ED K=4 and dense P=4 N-MNIST, same RTL, all closed within 0.4 ns of each other, in the estimates table and on the VM -- prereg rows 11-13 / P9, the measured bitstream-to-bitstream spread against the tool's ~9 mW / ~3 mW spread.",
    "RESULT (tool side, experiments/power_estimates/): fabric 48 mW ED K=4, 62.6 mW per dense P=4 engine (from x8), 54 / 83 mW at K=P=8, 72 / 135 mW DVS-Gesture at N=1, and by replication subtraction 54.7 mW per ED engine (x4) vs 135 mW per dense engine (x2) -> tool ratio 3.1x per engine on DVS-Gesture; PS7 1.533 W in every build. Placement alone moves the estimate ~9 mW (19 %) on ED and ~3 mW on dense across three implementation strategies at fixed RTL (C0019 variants) -- quote this as the tool's own uncertainty. The tool predicts ED 3.2x in energy at K=P=4 and 1.44x at K=P=8; my pre-registered P2 says 1.1-1.4x -- both on record before the meter (prereg sections 7-7d).",
    "The arithmetic, written out: delta I (mA) x 12 V / eta_reg = fabric-side delta power; per engine = delta / N_ENGINES minus the wrapper share found from the N=1 subtraction; energy per inference = per-engine power x engine-only latency; energy per control period = board power x period (C0005). Say which regulator efficiency is assumed and why the 12 V point is imperfect (C0026).",
    "Controls: die temperature logged or bounded (C0009, C0020); idle measured per bitstream, not once (C0001); noise floor from repeated idle windows before any comparison (C0002); BURST replays a set, not one sample (C0018); sample order randomised (C0016).",
    "Why replication (C0003) is legitimate: per-engine latency is unchanged at x8, x4 and x2 (passes 7, 8, 13, 14), so N engines doing N inferences in the same time is the same work; the wrapper share is removed by the N=1 subtraction.",
    "FIG: [part] (experiments/figures/diagrams/fig_measurement_boundary.svg covers the shunt and the boundary) Metering setup: still to add a photograph of the bench and a timing diagram of the idle / BURST / idle windows with the reading schedule.",
    "TAB: [exists] The bitstream matrix rows 1-13 (measure/metering_prereg_2026-09-19.md section 2): row, build, archive tag, purpose, BURST N, predicted delta; then the same table with measured columns filled in 6.5.",
    "TAB: [exists] Pre-registered predictions P1-P9 (metering) and K1-K7 (the energy-versus-K sweep, measure/k_energy_prereg_2026-09-20.md) with the tool's number and my contrary number side by side, and an empty 'outcome' column to be filled after the meter.",
]),
(1, "4.10  Simulation-in-the-Loop Perception Workload", [
    "Simulation-in-the-loop framing (decision 2026-08-20): lockstep physics, wall-clock-charged perception budget, stale latent on a miss, never a silent wait (robot/host/perception_loop.py, delay-injection test). The IsaacGym port: event simulator bit-identical to the recreation's, the 58k encoder verbatim, plugged into extreme-parkour's learn_vision as base_backbone only. Judgement calls: repeat window (direct coding) vs consecutive windows, 2 m depth clip, 64x64 resize, binarisation before the encoder.",
    "The teacher-student pipeline as run: teacher by PPO on scandots (15,000 iterations), student by DAgger on the teacher's actions with the event encoder as the vision backbone (10,000 iterations, 192 camera environments, 13.6 s/iteration on the 1080 Ti); evaluation protocol identical to extreme-parkour's (success = episode reaches its length without termination, per terrain).",
    "What is charged to the FPGA and what is not: the encoder's latency (measured on the board on real frames) is the perception budget; the GRU and MLP run on the host; physics is lockstep so a late latent is stale, not skipped.",
    "The event simulator's parameters and their provenance from the paper (contrast threshold, 10 Hz, inverse depth) and the one deviation (frame repeat over T rather than four consecutive 25 ms windows, C0047) with its cost to the ED engine (the scatter repeats).",
    "FIG: [exists] (experiments/figures/diagrams/fig_perception_loop.svg) Perception-loop timing diagram: physics steps, camera frame at 10 Hz, event simulation, encoder budget, latent hand-off, stale-latent path on a miss.",
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
    "TAB: [exists] (docs/thesis_tables/vector_sets.md) Vector sets: name, source npz, geometry, layer, samples, T, threshold, spikes per sample range, corner exposure, ladder checks that use it.",
]),
(1, "5.2  LIF Neuron Core and Baked-Weight Generation", [
    "lif_update.v: one shared combinational LIF core used by the M2 neuron and both engines. Vendor-neutral Verilog, simulated in Icarus Verilog and linted with Verilator; weights inlined into generated module variants (sim/gen_weight_vh.py from the tracked npz files, checked by sim/check_baked_weights.py) because $readmemh is silently zeroed in this flow.",
    "M2 as the first bit-identical module: the single-neuron testbench replaying golden traces; how the same core is instantiated P times (dense) and once per sweep pipeline (ED) so that the neuron arithmetic is verified once and shared.",
    "Baked-weight provenance as a chain: tracked npz -> generator -> Verilog case tables -> check_baked_weights.py entry-for-entry compare; the near miss where synthetic hex overwrote the r1 tables and what now prevents it.",
    "FIG: [exists] (experiments/figures/diagrams/fig_lif_core.svg) lif_update schematic: inputs (V, I, threshold, pending), the shift leak, the subtract, the compare, outputs (V', spike, pending'); one figure for the whole thesis's neuron.",
]),
(1, "5.3  RTL Implementation of the Two Datapaths", [
    "conv_layer_p.v; ed_scatter.v + ed_conv_layer.v; baked variants c1 / g1 / r1. The sign-off rules: one write + one read port per bank, no multipliers/dividers on address paths, re-registered BRAM outputs, use_dsp = no, single-stage ROM init.",
    "Module-by-module: what each does, its parameters (P or K, DATASET, geometry localparams), its state machine, and which ladder check covers it. Keep the prose to one paragraph per module; the code is in Appendix A.",
    "Parameterisation discipline: geometry derives from DATASET at the top (DS_H_IN, DS_W_IN, DS_THRESHOLD ...) so a build cannot mix a table from one dataset with the geometry of another; PING reports the dataset so a mis-built image is rejected before any card is written.",
    "TAB: [exists] (docs/thesis_tables/rtl_inventory.md) RTL inventory: module, file, lines, role (engine / wrapper / common), parameters, ladder checks, on silicon (yes/no).",
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
    "TAB: [exists] (docs/thesis_tables/utilisation.md joins provenance, utilisation, timing and estimate per build) Build provenance: tag, configuration, WNS, LUT / FF / BRAM tiles / DSP, estimate (total W, fabric mW), board pass number (experiments/power_estimates/README.md joined with the board records).",
    "TAB: [exists] (docs/thesis_tables/timing_closure.md) Timing-closure history: build, WNS before, critical path, fix, WNS after (from docs/decisions.md 2026-09-05 onward).",
]),
(1, "5.6  Verification Ladder and Silicon Sign-Off", [
    "The ladder (check_all.sh, 33 checks) and its counts (e.g. 591,872 comparisons ED c1; 1,048,576 DVS-Gesture g1; 18/18 N-MNIST rate sweep; 12/12 DVS-Gesture C2/C3); hostile-handshake wrapper benches -- RESULT: AXIS stress of the baked wrappers, 60 random gap/backpressure seeds x {N-MNIST c1, DVS-Gesture g1} x {ED K=4, dense P=4} = 240 runs, 240/240 bit-identical (experiments/axis_stress/README.md, 2026-09-20), i.e. handshake robustness far beyond the ladder's single seed and the DMA's one pattern; fault injection; the synthetic corner set; what simulation does NOT prove (port discipline, address timing, toolchain regressions), each converted into a standing check.",
    "Silicon sign-off as a procedure: the pre-card-write checklist (parameter read-back, WNS gate, PING build and dataset, golden mock first), the pre-registration file, the pass record; RESULT: fourteen passes, zero correctness misses, two wrong-bitstream deliveries rejected before any number was recorded.",
    "The negative test: the ladder's corner set fails on pre-C0044 RTL (proved by checking out the old RTL), so the guard is known to guard; say this explicitly, a check that has never failed proves little.",
    "TAB: [exists] (docs/thesis_tables/ladder.md, 33 rows) The ladder: check number, what it compares, vectors, comparison count, runtime, what class of bug it catches (from check_all.sh; 33 rows, or grouped into ~10 classes if the full table is too long for the body).",
    "TAB: [exists] (experiments/silicon_ledger.md; docs/thesis_tables/passes.md) Silicon passes 1-14: pass, date, build tag, dataset, engine, N_ENGINES, samples, bit-identical, latency, WNS, tiles (docs/results_ledger.md section 1 and 3 plus the DVS-Gesture x4/x2 records).",
]),
(0, "6  Results and Evaluation", [
    "Every table carries the brief's metrics (energy measured / estimated, latency, deadline-miss where applicable, mean power, LUT-FF-BRAM-DSP, firing rate per layer, accuracy) and says sim or board in the caption. Either crossover outcome is a valid result; nothing is tuned toward one. Target 25-35 pages.",
    "Figure discipline: every figure is generated by experiments/figures/make_figures.py from committed data, never from typed numbers; captions name the basis (sim / board / gpu), the dataset, the geometry, K or P, and the sample count.",
]),
(1, "6.1  Experimental Setup", [
    "ZedBoard XC7Z020 at 100 MHz, SD boot, bare metal; 16 N-MNIST / 8 DVS-Gesture golden samples over the framed link; BURST windows; engine-only timing; the Mac (iverilog/verilator) for every simulation; the MI210 and 1080 Ti hosts for training; the meter (TODO).",
    "Software versions and seeds (docs/environment.md): snnTorch, PyTorch/ROCm and CUDA versions, Vivado 2024.1, Icarus and Verilator versions, IsaacGym preview and extreme-parkour commit; seeds 0-2 where three seeds are reported. State that GPU training was NOT run with deterministic algorithms enabled and what that costs (C0050): repeated runs at a fixed seed differ, so accuracy rows are single-run numbers with ~1 pp of noise, while every simulation and board number is exactly reproducible.",
    "TAB: [todo] Setup table: item, version or model, role, where used; one row for the DMM (model, range, resolution, shunt value and tolerance).",
    "FIG: [todo] Photograph of the bench (ZedBoard, UART, SD, the shunt and meter in the 12 V lead) -- the one photograph in the thesis.",
]),
(1, "6.2  Task Accuracy and Firing Rates", [
    "RESULT (state the run count with every row; C0050: run-to-run noise at fixed seed is ~1 pp on DVS-Gesture): N-MNIST 96.6-97.0 % (3 seeds), quantisation cost within noise; DVS-Gesture 63.3 / 68.6 / 63.3 % (3 seeds, T=4), golden 63.3 / 66.7 / 65.9 %; T sweep 63.3 / 65.2 / 68.9 % at T=4/8/16. Per-layer rates: N-MNIST conv 6-11 %, FC ~30 %; DVS-Gesture c1 .073, c2 .143, c3 .186, fc .359. Trained-rate networks: N-MNIST accuracy flat 2-8 % then -0.5/-1.9 pp at 16/30 %; DVS-Gesture a 3 pp step between the 2-5 % and 10-35 % regimes. WHERE: experiments/dvsgesture/README.md, experiments/rate_sweep*/README.md.",
    "Say why the DVS-Gesture accuracy is low against the literature (a 58k-parameter network at 64x64 with T=4 and 264 test samples, vs published ~95 % with far larger networks and T=16+) and why that is acceptable: the datapath comparison needs realistic activity, not state-of-the-art accuracy; accuracy is reported at every sweep point (C0008).",
    "Report the rate-regulariser's reach: what conv rates it produced (2-35 %), that C1's input activity is unmovable, and the accuracy price at each point with seeds.",
    "FIG: [exists] Accuracy vs achieved conv activity, both datasets, mean +- sd over 3 seeds (experiments/figures/fig_accuracy_vs_activity.png).",
    "FIG: [exists] Per-layer firing rate per epoch, N-MNIST binarised (experiments/m0_firing_rates_binarised.png); optionally the counts arm beside it (D0003).",
    "TAB: [exists] (docs/thesis_tables/accuracy_rates.md, 46 networks; quantisation.md for the per-layer k, threshold, clip fraction and membrane range) Accuracy and rates: dataset, seed, T, float accuracy, golden integer accuracy, per-layer rate (c1, c2, c3, fc), peak fc membrane as % of int16 -- one row per trained network used anywhere in Chapter 6.",
]),
(1, "6.3  Resource Utilisation and Timing", [
    "RESULT: per build -- ED K=4 ~3.4k LUT / 12.5 tiles / WNS +0.508; dense P=4 5,760 LUT / 6.5 tiles / +0.299; ED K=8 13.5 tiles / +0.332; dense P=8 8.5 tiles / +0.101; ED K=4 x8 11,733 LUT / 86 tiles / +0.430; dense P=4 x8 27,829 LUT (52 %) / 46 tiles / +0.041; DVS-Gesture ED K=4 +0.190, dense P=4 +1.091 (rev 3); ED K=4 DVS-Gesture x4 86 tiles / +0.119; dense P=4 DVS-Gesture x2 21 tiles / +0.842 and x4 does not place. DSP = 0 everywhere. The honest asymmetry is STATE not logic. WHERE: experiments/board_*.md utilisation sections.",
    "Interpretation: the ED engine costs about half the LUTs of the dense engine at K=P=4 but about twice the BRAM (address list + K banks + two-word state + the replicated weight table, C0052); the dense engine's logic (decoded output enables) is what fails to replicate x4 at the 64-geometry while the ED engine's memory is what fails at x8. Neither is 'smaller'; they spend different resources.",
    "Timing: every build closes at 100 MHz with the sign-off rules; the smallest margins (dense x8 +0.041, ED x4 DVS-Gesture +0.119) and what limits them; the strategy variants show +0.35 to +0.77 ns spread at fixed RTL.",
    "FIG: [exists] (experiments/figures/fig_resources.png) Grouped bars of LUT, FF, BRAM tiles per build (N=1 builds on one panel, replicated on another), ED vs dense side by side; generated from the board records.",
    "TAB: [exists] (docs/thesis_tables/utilisation.md) Utilisation and timing per build: build, engine, K or P, dataset, N_ENGINES, LUT (% of 53,200), FF, BRAM tiles (% of 140), DSP, WNS, WHS, power estimate -- the brief's resource row for every silicon pass.",
]),
(1, "6.4  Latency per Inference at Matched Parallelism", [
    "RESULT: N-MNIST C1 at matched parallelism -- ED K=4 688.5 us mean (554.8-815.8, 1.47x spread) vs dense P=4 1,048.9 us flat -> 1.52x; ED K=8 575.5 us vs dense P=8 540.3 us -> dense 1.065x; sim-vs-board +0.4 to +1.5 %; x8 replications leave per-engine latency unchanged. DVS-Gesture: ED K=4 2,970.8 us mean (2.24x spread) vs dense P=4 3,706.5 us flat -> ED 1.248x at the mean; ED x4 replication (pass 13, 2026-09-20) 8/8 with per-clip latency equal to N=1 to 0.1 us, 86 BRAM tiles, 1.926 W estimate; dense P=4 DVS-Gesture does NOT place at x4 (65k decoded-enable output flops), so its replicated build is x2 -- a fabric-fit fact worth a sentence beside the resource table; dense P=4 DVS-Gesture x2 on silicon (pass 14, 2026-09-20): 8/8, per-clip latency 3,706.4-3,706.5 us equal to N=1, WNS +0.842, 21 BRAM tiles, 1.956 W estimate (experiments/dvsgesture/board_dense_p4_x2_20260920.md). Both replicated pairs are on silicon (N-MNIST x8/x8, DVS-Gesture x4/x2): fourteen board passes, zero correctness misses (docs/results_ledger.md rows 1-14).",
    "Per-sample view: ED latency is a straight line in input spike count (the cycle model), dense is a constant; plotting every board sample against the model line shows the +0.4 to +1.5 % board offset as a parallel shift, and the spread (1.47x N-MNIST, 2.24x DVS-Gesture) as the deadline problem in one picture.",
    "Board-vs-sim as a result: the constant per-inference offsets (N-MNIST ED 10.7 / dense 8.3 us; DVS-Gesture +29.4 / +20.0 us against wrapper-inclusive totals) attributed to DMA and framing, and the lesson that the comparison basis must be stated (Section 4.7).",
    "FIG: [exists] Latency vs K = P for both datasets, simulated curves with silicon points overlaid, the fitted crossovers at K = P = 7.4 / 5.8 marked (experiments/figures/fig_kp_sweep.png).",
    "FIG: [exists] DVS-Gesture per-clip latency: ED sim and board, dense sim and board, the two densest clips above the dense line (experiments/figures/fig_dvsg_perclip.png).",
    "FIG: [exists] (experiments/figures/fig_per_sample.png: N-MNIST K=4/K=8 board, DVS-Gesture K=4 board, robot frames sim, each against the cycle-model line and the dense constant) Per-sample scatter: board latency vs input spike count for every ED board sample (N-MNIST 16, DVS-Gesture 8, robot 64 if benched on the board), with the cycle-model line and the dense constant; add to make_figures.py from the board records.",
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
    "RESULT (parallelism axis): K sweep 135.5k / 90.3k / 67.8k / 56.5k / 50.8k cycles (K=1..16) = 45.2k + 90.3k/K; dense 407.2k/P + 2k; crossover K=P = 7.4 (N-MNIST), 5.8 (DVS-Gesture), bracketed on silicon by 4 and 8 (C0049: the N-MNIST figure was quoted as ~6.6 until 2026-09-20; recomputed from the cycle files at every table build). WHERE: experiments/latency_sim/ksweep_c0035/README.md, experiments/dvsgesture/latency_sim/README.md.",
    "RESULT (activity axis, data): DVS-Gesture per clip at K=P=4 -- ED wins iff < ~10,000 input spikes per clip (~30.5 % density); on silicon ED wins 6 of 8 clips and loses clips 1 and 5, exactly as pre-registered. RESULT (activity axis, training): N-MNIST C2/C3 ED over dense 10x/14x at 2 % to 1.6x/1.9x at 30 %, crossovers ~48 %/~57 % at K=P=4, falling to 40/52 % at K=P=8 and 29/44 % at K=P=16 (the 29 % C2 network exactly at the crossover at K=P=16; per-spike constants equal DVS-Gesture's at every K); DVS-Gesture C2/C3 8.4x/11.0x at 3 % to 1.33x/1.36x at 32-35 %, crossovers ~43 %/~48 % at K=P=4, falling to 36/44 % at K=P=8 and 26/37 % at K=P=16 (the 32 % network is past the C2 crossover at K=P=16: dense 1.18x). WHERE: experiments/rate_sweep/README.md, experiments/rate_sweep_dvsg/README.md.",
    "RESULT (timesteps, C0023's first half): T was swept on BOTH datasets at T = 4 / 8 / 16 with three seeds at every point, each run quantised and golden-checked on the full test set (N-MNIST 10,000 samples, DVS-Gesture 264), plus a T = 8 x activity grid on DVS-Gesture. N-MNIST: 96.9 / 97.6 / 98.0 %, about +0.7 pp per doubling, seed spread 0.2 pp, golden integer within 0.15 pp of float on every run. DVS-Gesture 65.0 / 65.7 / 69.3 % mean at T=4/8/16 (3 seeds each) but the fc membrane is at 98-121 % of int16 at T=16 -- and C0050 shows the same configuration and seed can land on either side of that ceiling run to run, so 'T=16 fits' is not a statement about a configuration -- and T x activity compound (at T=8 the ceiling moves to ~15-19 % activity; usable band T x activity <= ~1.2) (C0046); N-MNIST gains +0.7 pp per doubling to 98.0 % at T=16 with the fc at 9-25 % of int16, so the ceiling is a geometry property; C0046 options costed (9 networks): fc at k=7 instead of 8 costs no measurable accuracy (-1.5 to +1.9 pp over seven networks, 0 % clipping) and halves the fc range (95-186 % -> 47-93 % of int16; k=6 -> 23-47 %), and the chosen-k golden accuracy is by construction the 18-bit option's, so a wider membrane buys no accuracy (experiments/dvsgesture/c0046/README.md); cycle projections ED 3.4 / 5.9 / 9.8 ms vs dense 3.6 / 7.2 / 14.4 ms. Not swept: T = 1 and T = 2 (C0023 asked for {1,2,4,8}; the low end was dropped once T = 4 was fixed as the hardware build), no board run at any T other than 4 (the engines are T-parameterised and the cycle model projects the rest), and the weight bit-width axis -- C0023's other half -- was never run at all, which the limitations section must say. WHERE: experiments/tsweep_nmnist/, experiments/dvsgesture/README.md, docs/thesis_tables/tsweep.md.",
    "TODO: the energy curve on the same axes once the meter exists. Plot both engines' curves; report the crossover point or its absence -- both are findings. The parallelism axis has its own pre-registered energy experiment (measure/k_energy_prereg_2026-09-20.md, C0025): does the energy-optimal K differ from the latency-optimal K? Predicted yes at the fabric level (8 vs 16) and no at the board level (16 either way), because the always-on processor is thirty times the fabric's power -- so the most efficient configuration depends on which of the three energy quantities is asked for. Report it as a table of K against fabric energy, board energy, latency and resources, with the optimum identified per quantity or declared unresolved.",
    "The unifying statement: the crossover is a surface in (activity, K=P), not a point -- the ED sweep floor 2NT is fixed while the dense cost falls as 1/P, so more parallelism moves the crossover to lower activity; at the operating activities of these networks (C1 14-27 %, C2/C3 7-19 % trained), ED wins at K=P=4, is roughly even at 8, and loses at 16 on C1 and on the densest C2 network.",
    "Where the operating point sits on each axis (C0037): the N-MNIST C1 crossover at ~31 % density is just above the data's 13.6 %; the DVS-Gesture per-clip range 9-44 % straddles it; the trained-activity crossovers are above any accuracy-preserving network on N-MNIST but reachable on DVS-Gesture at K=P=16.",
    "Cycle-count basis and its limits: these are cycles at a fixed 100 MHz; energy may move the crossover because the two engines' per-cycle power differs (the tool says 48 vs 62.6 mW per engine); 6.5 supplies the correction if the meter allows.",
    "FIG: [exists] Dense/ED cycle ratio vs trained activity for C2 and C3 on both datasets, the 1.0 line and the fitted crossovers (experiments/figures/fig_activity_c2c3.png).",
    "FIG: [exists] Fitted crossover activity vs K = P for C2/C3 on both datasets at K=P=4/8/16 (experiments/figures/fig_crossover_vs_kp.png).",
    "FIG: [exists] DVS-Gesture accuracy and fc membrane range vs T per seed with the int16 ceiling, N-MNIST beside it (experiments/figures/fig_tsweep_int16.png).",
    "FIG: [exists] (experiments/figures/fig_crossover_heatmap.png: log2 dense/ED over activity x K=P for DVS-Gesture C2 with the dense = ED contour of every fitted layer) Crossover surface as a heat map or contour: ED/dense ratio over (activity, K=P) from the cycle model, with the benched points overlaid and the measured operating points of each network marked.",
    "TAB: [exists] (docs/thesis_tables/crossover.md, 15 rows) Crossover table: axis, layer, dataset, K=P, crossover value, basis (model / sim / board), the operating point of the trained network, verdict at the operating point.",
    "TAB: [exists] (docs/thesis_tables/tsweep.md) T sweep: dataset, T, seeds, accuracy mean +- sd, fc membrane % of int16 (min-max over seeds), golden-clean (y/n), projected ED and dense latency.",
]),
(1, "6.7  Lessons from Sign-Off: What Simulation Could Not See", [
    "As findings: multi-ported accumulator -> 62k LUTs; multipliers on address paths WNS -4.5; dividers in spike decode WNS -3.5; BRAM latches; two-stage ROM init -> all-zero silicon; the LIF->obits path at the DVS-Gesture geometry (WNS -0.696 -> rev 3); the sweep bug invisible to a centred dataset (C0044); wrong-bitstream deliveries caught by the checklist; the baked-weight provenance near miss (tracked npz + check_baked_weights.py).",
    "Frame each as (symptom, why simulation passed, root cause, fix, the standing check that now catches it); the point of the section is that bit-identical simulation is necessary and not sufficient, and that each gap was closed with a check rather than with care.",
    "The C0044 lesson in full: the bug lived in the RTL for weeks under a 30-check ladder because every N-MNIST sample is centred and never fires a corner neuron; the second dataset's 3 of 32 corner-active samples caught it; the corner-exposure report now prints for every vector set and a synthetic all-corner set is in the ladder; the fix was one unconditional write.",
    "TAB: [exists] (docs/thesis_tables/lessons.md, 12 rows) Lessons table: date, symptom, where seen (synthesis / timing / silicon / second dataset), root cause, fix, guard added (check name), reference (decisions.md date or C-number).",
]),
(1, "6.8  The Perception Workload: Distillation, Evaluation and Deployment", [
    "RESULT: teacher 15,000 iterations (23.3 h, 1080 Ti), success gap 95.3 / hurdle 96.1 / parkour 97.2 / step 99.2 % under extreme-parkour's protocol (experiments/p1_distill/isaac_eval_README.md). FPGA-student distillation running (10k iterations, ETA 2026-09-21): TODO its success rates on the same protocol, GIFs per terrain (teacher and student), student-driven frames. Queued behind it to 1 October (robot/isaac/gpu_queue.sh): the paper's own depth student as the same-stack reference, two further independent FPGA-student runs so the success rate is reported as a spread rather than a point (C0050 showed single runs are not reproducible), and the C0047 consecutive-window student, which tests the one encoding deviation from the paper and is also what makes the event-driven engine scatter the same frame four times. Real robot event frames (64, direct coding): both engines bit-identical; ED K=4 1.73 ms mean / 2.75 ms worst vs dense 3.60 ms (2.09x / 1.31x, all 64 frames; the first write-up's 1.86 / 2.52 ms were 8 frames, C0048). The MuJoCo recreation's earlier result (58k student vs the 11.19M reference) as precursor (experiments/p1_distill/results_fpga_*.md).",
    "Deadline reading: per-frame spread 2.01x (robot, 64 frames), 2.24x (DVS-Gesture, board) -- the worst-case verdict differs from the mean one. TODO: FPGA-in-the-loop over SSH and the perception-rate sweep (energy per control cycle, deadline-miss rate) if time allows.",
    "How to read the student's success rates: against the teacher (the ceiling, privileged scandots), against the stock depth student (the paper's own recipe with an 11M-parameter ResNet), and against ES-Parkour's Fig. 5 (a different simulator seed and protocol, so only the ordering of terrains is comparable). State the distillation budget (10k vs the paper's unspecified) as the main caveat.",
    "The deadline budget at 10 Hz is 100 ms; the encoder's worst frame is 2.75 ms (ED, sim over 64 frames) or 3.60 ms (dense, board-confirmed constant), so both meet it with margin; the interesting number is the fraction of the budget and the spread, and what perception rate (20, 50, 100 Hz) each engine would first miss -- from the cycle model, then measured if the FPGA-in-the-loop run happens.",
    "Student-driven frames vs teacher-driven frames: the student's own trajectories produce the activity distribution the hardware would see in deployment; compare density and ED latency between the two frame sets once the student frames are benched.",
    "FIG: [todo] One still per terrain (gap, hurdle, parkour, step) from the teacher and student GIFs, side by side, with success annotated (experiments/p1_distill/gifs/ once copied).",
    "FIG: [todo] Per-frame latency on the 64 real event frames: ED K=4 and dense, sorted by input spike count, with the worst-case and the 10 Hz budget line; add the student-driven set as a second series.",
    "TAB: [todo] Success rate per terrain: teacher, FPGA student (58k spiking encoder), stock depth student (reference), ES-Parkour Fig. 5; with episodes per terrain and the protocol line.",
    "TAB: [exists] (docs/thesis_tables/deadline.md: per-sample distributions, worst as % of the 100 ms budget, max sustainable rate, miss rates; student-driven set to add) Robot-frame latency: frame set (teacher-driven / student-driven), frames, input density mean / range, ED mean / worst, dense, ratio, fraction of the 100 ms budget, projected deadline-miss rate at 20 / 50 / 100 Hz.",
]),
(1, "6.9  Discussion", [
    "Two crossover axes; on N-MNIST no trained network reaches the C2/C3 crossover while DVS-Gesture straddles the C1 one per clip, now on silicon; the int16 ceiling as the binding constraint on the harder dataset; direct-coding cost (C0047); the tool-vs-meter disagreement once measured.",
    "Answer the reader's objections in order: 'the dense engine is unoptimised' (it has the same knobs and the same discipline; its 88 cycles/neuron are within 2 of the model); 'K=P is arbitrary' (iso-resource and iso-latency readings given beside it); 'C1 only on silicon' (C2/C3/FC bit-identical in sim, per-spike constants transfer); 'accuracy is low' (activity is the variable, accuracy reported at every point); 'no physical robot' (simulation-in-the-loop with charged wall-clock).",
    "Residual risk per threat of Section 3.5, now that the results exist: walk the threats table and say for each whether the mitigation held (e.g. the delta resolved above the noise floor; the strategy-variant spread was smaller than the tool gap; the corner set caught C0044; sim-vs-board within 1.5 %; the cycle results are exactly reproducible where the accuracy results are not, C0050) or what remains (one fabric, 8-16 cycle samples, single seeds where noted, the constant board offsets attributed but not decomposed further).",
    "Generalisation limits: one 28 nm fabric at one clock; a different fabric changes the per-cycle power of banks vs lanes and so the energy crossover but not the cycle one; the cycle model transfers across layers and datasets here, which is the evidence for the claim's scope (C0010).",
    "What would change the conclusion: an 18-bit membrane (removes the T ceiling), a skip-scatter for repeated frames (cuts ED cost at direct coding by up to 4x on the scatter term), an event-driven FC on silicon (C0015), a per-rail meter (separates PS from PL).",
    "TAB: [todo] Residual-risk table: threat (from 3.5), mitigation, evidence it held (number and section), residual.",
]),
(0, "7  Conclusion and Future Work", [
    "Close the loop from Chapter 1 with numbers attached. 4-6 pages.",
]),
(1, "7.1  Summary of Findings", [
    "Answer RQ1-RQ3 in three paragraphs; revisit each objective from 1.3 with its number.",
    "RQ1: crossover at K=P = 7.4 (N-MNIST) and 5.8 (DVS-Gesture), silicon-bracketed by the 4 and 8 pairs and ~30 % input density per clip (silicon); trained-activity crossovers 43-57 % at K=P=4 falling to 26-44 % at 16 (sim). RQ2: TODO the measured ratio vs the tool's 3.1-3.2x. RQ3: the worst-case verdict flips on DVS-Gesture (dense wins the densest clips) and narrows on the robot frames (2.09x mean -> 1.31x worst).",
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
    "IEEE style; Zotero/BibTeX -- docs/references.bib (67 verified entries, 2026-09-20) is the starting file and docs/references_verified.md the audit trail (49 verified, 4 corrected: Roy/Jaiswal/Panda; Rudin CoRL 2021; Cheng ICRA 2024; Sanaullah & Koravuna 2023 as Harmeling's neuron-cost source). Must include: ES-Parkour (ICME 2025, DOI 10.1109/ICME59968.2025.11209556), extreme-parkour, IsaacGym, snnTorch, N-MNIST, DVS-Gesture, Harmeling et al. NCE 2026, Cheng TCAS-I 2025, Cerebron TVLSI 2022, Li TCAS-I 2021, Minitaur TVLSI 2014, FireFly-P 2026, Nagy et al. (Loihi 2), Guerra-Hernandez et al. 2017, Mahowald (AER), TrueNorth / Loihi / SpiNNaker overview papers, Xilinx UG907 (power analysis) for how report_power works.",
]),
(0, "Appendices", [
    "A. Verilog listings (lif_update, conv_layer_p, ed_scatter, ed_conv_layer, axis_conv, axis_conv_top).",
    "B. The decision log (docs/decisions.md) and the corrections review (docs/corrections.md, C0001-C0047) with status.",
    "C. Protocols: framed UART, BURST, the metering pre-registration and DMM procedure, pre-card-write checklist, build and card-writing procedure (docs/vivado_session_next.md, docs/vivado_new_project.md).",
    "D. Pre-registrations and outcomes (experiments/*prereg*.md, experiments/dvsgesture/silicon_prereg_20260919.md, measure/metering_prereg_2026-09-19.md, measure/k_energy_prereg_2026-09-20.md).",
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
                    m = re.match(r"\[(exists|part|todo)\]\s*(.*)", rest, re.S)
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
    ne = sum(1 for r in rows if r[2] == "exists"); npart = sum(1 for r in rows if r[2] == "part")
    doc.add_paragraph("%d figures and %d tables planned; %d exist, %d partial, %d to make."
                      % (nf, nt, ne, npart, len(rows) - ne - npart)).runs[0].italic = True
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
