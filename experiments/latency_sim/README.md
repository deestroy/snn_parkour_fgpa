# Per-sample latency in simulation (2026-08-19, overnight)

`sim/run_axis_tb.sh` with `NOGAP=1 CYCLES=<file>`: the AXIS testbench drives
the DMA side with no gaps and no backpressure and counts cycles from the
first input word of a sample to its last output word (tlast), plus the
cycles the engine's `busy` is high. 16 golden N-MNIST samples, C1, 100 MHz
assumed. `*_cycles.txt`: `sample total engine_busy`.

| engine | total cycles/sample (mean) | ms | engine-only ms | wrapper (pack/unpack) share |
|---|---|---|---|---|
| dense (ENGINE=0) | 436,247 — constant, data-independent | 4.362 | 3.884 | 11 % |
| event-driven K=1 | 234,009 (215,499–259,076) | 2.340 | 1.948 | 17 % |
| event-driven K=4 | 149,273 (143,801–156,596) | 1.493 | 1.101 | 26 % |

Cross-check against the board (2026-08-19 01:30, BURST): ED K=4 sample 0
measured 1,514.5 us; simulated 146,822 cycles = 1,468 us -> DMA + software
loop overhead ~46 us (3 %). Predicted dense on the board: ~4.4 ms.

At the trained C1 firing rate the event-driven K=4 engine is 2.9x faster
end to end (3.5x engine-only). This is latency only; energy needs the
meter (README "Next steps"). The wrapper's bit-serial pack/unpack is a
fixed ~39-48k cycles shared by both engines (a post-M7 optimisation).
