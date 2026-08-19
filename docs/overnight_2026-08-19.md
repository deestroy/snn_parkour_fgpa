# Overnight 2026-08-19 — morning summary

Everything below is committed and pushed (last commit e471f27). No board
action was taken, nothing irreversible; every RTL change went through the
same harness. `check_all.sh`: 17 passed, 0 failed.

## Results produced (all simulation, all saved under experiments/)

1. **Latency table, both engines, per sample** — `experiments/latency_sim/README.md`
   Dense 4.36 ms/inference (constant); ED K=1 2.34 ms; ED K=4 1.49 ms.
   ED K=4 sample 0 in sim = 1.468 ms vs 1.5145 ms measured on the board
   last night -> DMA + software loop overhead is ~46 us (3 %). Predicted
   dense on the board: ~4.4 ms. Wrapper's bit-serial pack/unpack = 39-48k
   cycles of every figure (a post-M7 optimisation, shared by both engines).

2. **M7 rehearsal: latency vs C1 input firing rate** — `experiments/m7_sim/`
   (plot `m7_sim_crossover.png`, `sweep.csv`). Ten densities, both engines,
   30 runs, all bit-identical (incl. 89 % activity — the worst-case address
   list held). Dense flat; ED K=1 crosses dense at ~45 % input rate;
   **ED K=4 never crosses** (still 1.45x faster at 89 %).

3. **Per-layer latency, whole conv stack, trained rates** —
   `experiments/latency_sim/layers.md`. Dense C1/C2/C3 3.9/15.3/18.6 ms;
   ED K=4 1.10/1.08/1.07 ms; stack 37.8 vs 3.26 ms (11.6x). All 9 runs
   bit-identical — the ED engine is now verified on C2 and C3 too.

**The finding worth reading first (also in decisions.md):** in LATENCY,
event-driven K=4 wins at every activity tested; there is no latency
crossover on this network. The crossover question is purely about ENERGY
(ED's ~4x BRAM / ~1.7x logic static cost vs its far fewer memory accesses).
That is the thesis question exactly, and only the meter answers it. It
sharpens M7: sweep activity, measure energy per inference for both engines.

## Tooling added

- `sim/tb_axis_conv.v` / `sim/run_axis_tb.sh`: `NOGAP=1` (no gaps/backpressure)
  and `CYCLES=<file>` per-sample cycle counts (total + engine-busy);
  `AXIS_IN/AXIS_OUT` vector override.
- `sim/tb_ed_conv.v` / `sim/run_ed_tb.sh`: `CYCLES=<file>` per-sample cycles.
- `sim/export_axis_sweep.py`: synthetic-density C1 vectors + golden outputs.
- `experiments/m7_sim_sweep.py`: the sweep orchestrator (`--replot` redraws).
- `measure/dmm_protocol.md` + `measure/manual_meter.py` (`--selftest`):
  the bench-DMM measurement procedure and a manual-entry calculator
  (idle/burst/idle readings -> uJ/inference with SEM, drift and
  "resolvable" flags, JSON record in measure/runs/).
- `check_all.sh`: + ED AXIS K=4, scatter K=4, DMM arithmetic, ED lint (17 checks).
- `docs/status_2026-08-19.md`: supervisor page (supersedes 08-18).

## Decisions made overnight

None architectural. I did NOT implement the word-parallel wrapper
pack/unpack: it changes both engines' latency and belongs after the first
energy measurement, not before (your call — it is listed under "later" in
README "Next steps").

## What is waiting on you

1. Meter session (DMM first): `measure/dmm_protocol.md`, then
   `python3 measure/manual_meter.py --label ed_k4`.
2. Dense ENGINE=0 rebuild for its board latency (predicted ~4.4 ms) and exact
   utilisation. Same server, same BURST command.
Robot brief: `robot/CLAUDE-robot.md` updated to ZedBoard, still excluded from git.
