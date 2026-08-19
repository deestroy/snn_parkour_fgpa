# Per-layer latency in simulation, all conv layers, both engines (2026-08-19)

`sim/run_ed_tb.sh <layer> <dut>` with `CYCLES=<file>`: cycles from the first
spike push of a timestep to `done`, summed over T=4, per sample; 16 golden
N-MNIST samples at the trained firing rates. `ed_iface_shim` = the dense
engine behind the event-driven interface; `ed_conv_layer` K=1 / K=4 = the
event-driven engine. Every run is also a bit-identity check (all PASS).
Engine-only (no AXIS wrapper); 100 MHz assumed.

| layer | dense cycles (ms) | ED K=1 (ms) | ED K=4 (ms) | K=4 vs dense |
|---|---|---|---|---|
| C1 (2->16, 34x34) | 389,995 (3.900) | 194,825 (1.948) | 110,078 (1.101) | 3.5x |
| C2 (16->32, 17x17) | 1,525,734 (15.257) | 283,934 (2.839) | 108,191 (1.082) | 14.1x |
| C3 (32->64, 9x9) | 1,863,461 (18.635) | 337,059 (3.371) | 107,403 (1.074) | 17.4x |
| conv stack | 3,779,190 (37.79) | 815,818 (8.16) | 325,672 (3.26) | 11.6x |

Reading: dense cost = neurons x taps, and taps grow with input channels
(C2: 16x9, C3: 32x9), so the deeper layers dominate. Event-driven cost =
spikes x fan-out + a fixed sweep, and at trained rates the deeper layers'
spike counts are modest (C2 1,626/sample, C3 1,049/sample), so the ED
cost stays ~1.1 ms per layer. C1 ED K=4 here (110,078) matches the AXIS
bench's engine-busy count (110,070) and the board within 3 %.

Consequence for M7: at K=4 there is NO latency crossover for this network
at any of the tested activities (see ../m7_sim/) -- event-driven is faster
everywhere. The open question is therefore energy: the ED engine holds
~4x the block RAM and ~1.7x the logic (static power) and moves fewer bits
(dynamic power). That is precisely what the meter decides, and it is why
M5 is the critical path. Raw per-sample counts: layer_<L>_<engine>.txt.
