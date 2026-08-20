# FPGA-in-the-loop link budget (sim-in-the-loop era, updated 2026-08-20)

Originally written for the physical robot; revised for the simulation
pivot. Two changes of meaning: (1) the sim runs in LOCKSTEP, so a slow
link cannot break the loop — it produces logged deadline misses instead
(which is data); (2) the engine numbers at the ROBOT GEOMETRY are now
simulated-verified, not extrapolated.

## The budget

Policy rate 50 Hz -> the whole perception step has a 20 ms budget
(camera -> preprocess -> encoder (FPGA) -> policy -> command), and the
literature runs perception at 10 Hz (100 ms) with control at 50 Hz using
the latest latent. Two budgets to satisfy: 100 ms comfortable, 20 ms
ambitious (the "exploit the camera's 90 fps" result the plan wants).

## What the sim ships to the FPGA per perception tick

Event frames are 2x64x64 binary x T=4 (D0024; corrected from the older
48x64 table) = 32,768 bits = 1,024 words in; C1 output back 16x32x32 x4 =
2,048 words. The engines are verified at this geometry (synthetic AND
real distilled weights); the board bitstream retarget is a parameter
change + baked-weight regeneration, prepared in sim/ for the next Vivado
session.

## Transport options, computed

| transport | raw rate | 1,536 words in + ~2,900 out (full conv out) | verdict |
|---|---|---|---|
| UART 115200 (today's link) | ~11.5 kB/s | ~1.5 s | hopeless for the loop; fine for bring-up/verification |
| UART 921600 | ~92 kB/s | ~190 ms | misses even 10 Hz |
| ZedBoard Ethernet, bare-metal lwIP UDP | ~10-40 MB/s practical | ~0.5-2 ms | fits both budgets |
| Zynq PS DDR shared with a Linux image | n/a (same board) | ~0 | only if we adopt Linux; big bring-up cost |

Conclusion (recommendation, revisit at R4): the UART link stays as the
verification/bring-up channel (it is debugged and framed); the CONTROL
path needs the ZedBoard's Ethernet under bare-metal lwIP (echo server
first, then the framed protocol over UDP with the same CRC discipline).
The robot side treats the FPGA as one more UDP peer on 192.168.123.x
(Go1) or a DDS-adjacent raw-UDP peer (Go2) — either way plain sockets.

## Compute inside the budget (verified at the robot geometry, 2026-08-20)

At the ACTUAL year-two shape (2x64x64 -> 16x32x32; both engines
bit-identical there, 1,048,576 comparisons, incl. with the distilled
network's real quantised weights and real sim event frames at 6 %
activity): C1 dense 13.79 ms; C1 ED K=4 3.06-3.21 ms. So per-C1-layer:
ED K=4 fits 10 Hz (100 ms) and 25 Hz (40 ms) with big margin, fits 20 ms
(50 Hz) for C1 alone; the full conv stack at 50 Hz needs the pipelined
sweep or K=8/16 (both on the later list). Dense misses 20 ms per layer —
which is itself the thesis point restated. Energy per tick: [meter].

## Power on the robot

ZedBoard wants 12 V, ~0.5 A measured baseline (~6 W). The robot rail ->
regulator question from the plan stands; alternative per the plan's
"expected trouble": bench-supply the FPGA and measure it separately from
the robot battery. Decide at R3 with the meter in hand.

## What this doc deliberately does not decide

Go1 vs Go2 (blocks SDK code); whether perception runs at 10/25/50/100 Hz
(that is the R7 sweep, not a design constant); Linux-on-Zynq (only if
lwIP disappoints).
