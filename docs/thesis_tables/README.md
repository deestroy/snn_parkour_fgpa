# Thesis tables

Markdown tables ready to paste into the thesis, each traceable to repository files. Regenerate the data-derived ones with `python3 docs/thesis_tables/make_tables.py` after any board pass, build or ladder change; the hand-maintained ones are edited here.

| file | outline section | source | kind |
|---|---|---|---|
| utilisation.md | 5.5 (build provenance), 6.3 (resources and timing) | experiments/power_estimates/*_power.rpt, *_summary.txt, README.md; experiments/silicon_ledger.md | generated |
| ladder.md | 5.6 (verification ladder) | check_all.sh | generated |
| vector_sets.md | 4.8 / 5.1 (vector sets and corner exposure) | sim/run_ed_tb.sh, sim/vectors/*_thresh.txt, *_exposure.txt | generated (exposure as last exported; the ladder regenerates the default sets) |
| rtl_inventory.md | 5.3 (RTL inventory) | hdl/ (line counts); roles in the script | generated |
| quantisation.md | 2.6 / 4.2 / 6.2 (quantisation per layer) | golden/*.npz, golden-check logs | generated |
| timing_closure.md | 5.5 (timing-closure history) | docs/decisions.md | hand-maintained |
| lessons.md | 6.7 (lessons from sign-off) | docs/decisions.md, docs/corrections.md | hand-maintained |
| (silicon passes 1-14) | 5.6 / 6.4 | experiments/silicon_ledger.md already is that table | existing |
| (metering matrix, predictions P1-P9) | 4.9 / 6.5 | measure/metering_prereg_2026-09-19.md sections 2 and 7 | existing |
| (baseline table) | 3.1 | docs/baseline_table.md | existing |
