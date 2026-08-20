# FPGA-in-the-loop link budget (from measured year-one numbers)

Written 2026-08-19. Decides-in-advance the R4 question: how does the
ZedBoard join the robot's control loop, and does the loop close in time?
All engine numbers below are MEASURED (BURST mode, timing-clean bitstreams);
link numbers are computed from the protocol as implemented.

## The budget

Policy rate 50 Hz -> the whole perception step has a 20 ms budget
(camera -> preprocess -> encoder (FPGA) -> policy -> command), and the
literature runs perception at 10 Hz (100 ms) with control at 50 Hz using
the latest latent. Two budgets to satisfy: 100 ms comfortable, 20 ms
ambitious (the "exploit the camera's 90 fps" result the plan wants).

## What the robot must ship to the FPGA per perception tick

The robot-era network input is 48x64x2 binary spikes x T=4 timesteps
(CLAUDE.md target table) = 49,152 bits = 1,536 32-bit words in;
C1-equivalent output back. NOTE: today's engines are built/verified at
N-MNIST geometry (34x34x2); the engines are fully parameterised, so the
retarget is a re-synthesis with new parameters + a retrained network —
planned, not done.

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

## Compute inside the budget (measured)

C1 at N-MNIST geometry: dense 4.41 ms, ED K=4 1.51 ms. Robot geometry is
48x64 = 2.65x the pixels of 34x34: scaling the sweep+scatter linearly
predicts ED K=4 ~4 ms/inference for C1, conv stack ~9-12 ms — inside 20 ms
but not by much at 50 Hz perception; comfortable at 10-25 Hz. The
pipelined-sweep and word-parallel-wrapper items on the "later" list are
exactly the levers if 50 Hz perception is pursued. Energy per tick:
[meter, then re-measure at robot geometry].

## Power on the robot

ZedBoard wants 12 V, ~0.5 A measured baseline (~6 W). The robot rail ->
regulator question from the plan stands; alternative per the plan's
"expected trouble": bench-supply the FPGA and measure it separately from
the robot battery. Decide at R3 with the meter in hand.

## What this doc deliberately does not decide

Go1 vs Go2 (blocks SDK code); whether perception runs at 10/25/50/100 Hz
(that is the R7 sweep, not a design constant); Linux-on-Zynq (only if
lwIP disappoints).
