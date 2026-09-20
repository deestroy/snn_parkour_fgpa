# Timing-closure history (hand-maintained from docs/decisions.md)

Every negative-slack build, its critical path, the change that closed it, and the slack after. 100 MHz PL clock throughout; the pre-card-write rule "WNS >= 0 or no card" dates from 2026-08-18.

| date | engine / build | WNS before (ns) | critical path | fix | WNS after (ns) | reference |
|---|---|---|---|---|---|---|
| 2026-08-18 | ED K=4, first synthesis | (did not fit: ~62k LUTs) | multi-ported accumulator banks inferred as distributed logic | one write + one read port per bank so the banks map to BRAM | fits (3.4k LUT) | decisions.md 2026-08-18 (C0035 era) |
| 2026-08-18 22:40 | ED K=4 | -4.534 (TNS -287) | bank offset and weight-row address computed with multipliers on the address path | addresses stepped/added, no multiplier on any address path | -3.541 | decisions.md 2026-08-18 addendum |
| 2026-08-18/19 | ED K=4 | -3.541 (17 logic levels, 13.3 ns) | dividers in the spike decode (flat index -> channel, row, col) | D0020 rev 2: addresses carried as packed fields, every divider gone | -0.420 | decisions.md D0020 |
| 2026-08-19 00:10 | ED K=4 | -0.420 (one endpoint) | LIF chain sourced directly from BRAM output latches (clock-to-out + compare + subtract + add in one cycle) | re-register the BRAM outputs before lif_update | +0.735 | decisions.md 2026-08-19 00:35 |
| 2026-08-19 21:50 | dense P=1 | -3.934 (119 endpoints) | same address-path and latch pattern as the ED engine | same fixes applied to the dense engine | +0.787 | decisions.md 2026-08-19 22:56 |
| 2026-09-06 | dense P=4 (C0029 P-wide) | -3.230 | every critical path in the flat out_words flop file (decoded write enables) | banked output word file per lane (C0035 rev 2) | +0.299 (pass 4) | decisions.md 2026-09-06 |
| 2026-09-17 | dense P=4 x8 (N_ENGINES=8) | (met, +0.041) | replication congestion; smallest margin of any build | none needed; recorded as the limit of dense replication on this fabric | +0.041 (pass 8) | board_dense_p4_x8_20260917.md |
| 2026-09-19 | dense P=4, DATASET=1 (64-geometry) | -0.696 | LIF update -> output-bit write in one cycle at the larger bank | rev 3: registered output-bit write | +1.091 (pass 11) | decisions.md 2026-09-19 |
| 2026-09-20 | dense P=4 x4, DATASET=1 | (does not place: ~65k decoded-enable output flops) | placer runs out of flops for four replicated decoded write-enable files | build at N_ENGINES=2 instead | +0.842 at x2 (pass 14) | decisions.md 2026-09-20 |
| 2026-09-20 | ED K=4 / dense P=4 N-MNIST, three implementation strategies (C0019) | -- | -- | same RTL, Default / Performance_Explore / Congestion_SpreadLogic_high | ED +0.475 / +0.346 / +0.499; dense +0.768 / +0.388 / +0.354 | experiments/power_estimates/README.md |

Two further tool-flow events belong beside this table rather than in it: the all-zero bitstream from a two-stage weight-ROM initialisation (2026-09-05, fixed by single-stage init and guarded by sim/lint_synth_safety.sh), and the .xsa that lost the DMA address map after a timing-clean build (2026-08-19, D0015).
