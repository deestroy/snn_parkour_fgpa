# External baseline table (C0011) — FPGA SNN accelerators, published figures

Skeleton with the rows the review names. RULE: numbers are transcribed
from the papers, never recalled from memory — rows marked [fill] await
transcription with the paper in hand. The "power obtained by" column is
the thesis's argument in visual form; ours will be the only measured
entries.

| work | platform | network | benchmark | acc | LUT/FF/BRAM/DSP | clk | latency | power obtained by | energy/inference |
|---|---|---|---|---|---|---|---|---|---|
| Harmeling et al., NCE 6 024022 (2026) | Artix-7 XC7A200T | 784-100-10, fully parallel per layer, 4-bit weights | MNIST | 96.31 % | 93,347 logic cells / — / 341 BRAM / — | 100 MHz | 1.7424 ms/digit | Vivado post-impl estimate, 1.13 W incl. HUB75 LED matrix | 1.972 mJ/digit (see note) |
| Cheng et al., TCAS-I (2025) | [fill] | [fill] | [fill] | [fill] | [fill] | [fill] | [fill] | [fill — expect tool estimate] | [fill] |
| Cerebron, TVLSI (2022) | [fill] | [fill] | [fill] | [fill] | [fill] | [fill] | [fill] | [fill] | [fill] |
| FireFly-S | [fill] | [fill] | [fill] | [fill] | [fill] | [fill] | [fill] | [fill] | [fill] |
| Spiker+ | [fill] | [fill] | [fill] | [fill] | [fill] | [fill] | [fill] | [fill] | [fill] |
| **ours, dense P=1 (naive)** | Zynq XC7Z020 (PL) | conv 2-16-32-64 + FC 256-128, int8 pow2 | N-MNIST | 96.75 % (quantised) | 3,167 / 4,059 / 7.5 / 0 | 100 MHz | 4.409 ms/inference (measured) | **board-rail meter (pending session)** | [meter] |
| **ours, event-driven K=4** | Zynq XC7Z020 (PL) | same network | N-MNIST | 96.75 % | 3,383 / 4,036 / 13 / 0* | 100 MHz | 1.51 ms/inference (measured) | **board-rail meter (pending session)** | [meter] |

\* ED DSP=0 by construction (use_dsp), to be confirmed measured on the
next build. Matched-parallelism rows (dense P=4) join after the C0035
re-baseline.

## Comparability note (the trap, stated)

Harmeling's energy is **per digit**, where one digit is a 220-image spike
train — not comparable to a per-inference figure at T=4 without explicit
normalisation. Any cross-row comparison in a results chapter states its
normalisation in the caption or does not happen. Boundaries also differ
per row (die-only estimates vs whole-board measurement, C0004); the
"power obtained by" column is the honest axis.

## The gap, in the field's own words (C0022 addendum)

Harmeling et al. adopt synchronous processing on the strength of the
assumed tradeoff and close by leaving it open: "The event-driven approach
... is highly efficient when spikes are sparse, but becomes less
effective under dense or bursty activity. In such cases, synchronous
layer-by-layer processing is commonly adopted." and "...this suggests
that an event-based implementation could become advantageous when
activity is sufficiently sparse." A 2026 peer-reviewed statement that the
tradeoff this thesis measures is assumed, not measured — use it in the
introduction and related work.

## Neuron-model cost anchor (C0043)

Harmeling et al. Table 4 (after Koravuna et al.), per-neuron Artix-7
cost: LIF 13 LUT / 17 FF / 0 DSP; SRC 75/21/0; QIF 82/21/0; Izhikevich
42/25/1; Hodgkin-Huxley 73/25/3. Quantitative justification for the LIF
choice — and the balancing acknowledgement that SRC preserves dynamics
LIF discards.
