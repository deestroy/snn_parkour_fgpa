# Board pass: DVS-Gesture C1, dense P=4 (DATASET=1) on silicon (2026-09-19) — the within-dataset crossover, both engines measured

Build: ENGINE=0, DENSE_P=4, DATASET=1, N_ENGINES=1, BAKED_WEIGHTS=1,
m4_conv2/builds/dense_p4_dvsg_20260919_1447 (bitstream 2026-09-19
14:52:59, WNS +1.091 / WHS +0.045), conv_layer_p at **C0035 rev 3**
(registered output bit-file write) — the first rev 3 bitstream on
silicon. Server build 5 DATASET=1 (conv_server_g1 component). The
previous attempt of this build (dense_p4_dvsg_20260919_1405, rev 2)
failed timing at WNS -0.696 on the LIF -> obits path and was never
exported. Pre-registered: experiments/dvsgesture/silicon_prereg_20260919.md.

## Correctness

PING: build 5, DVS-Gesture C1. **8/8 clips bit-identical** (16,384
words), 700 burst inferences and an 800-inference sweep with zero CRC
mismatches. Rev 3's one-cycle-later bit-file write is invisible to the
word reader, as argued; the ladder's 30/30 is now backed by silicon.

## Latency (engine-only, build-5 words 8..9; 100 iterations/clip)

**3,706.4-3,706.5 us on every clip** and on the sweep: spread 0.1 us,
the timer's resolution. Server overhead 414.5 us. Die 34.6-37.2 degC.
vs sim 3,604.4 us: **+102.0 us**, the dense per-pass offset on
3,072-word frames (ED's on the same frames: +92.9 us).

## The K = P = 4 verdict on DVS-Gesture, both engines on silicon

| clip | gesture | dense P=4 us | ED K=4 us | dense / ED | faster |
|---|---|---|---|---|---|
| 0 | 0 | 3706.4 | 2084.6 | 1.778x | ED |
| 1 | 6 | 3706.4 | 4663.9 | 0.795x | dense |
| 2 | 1 | 3706.4 | 2553.1 | 1.452x | ED |
| 3 | 7 | 3706.4 | 2515.7 | 1.473x | ED |
| 4 | 10 | 3706.4 | 2965.9 | 1.250x | ED |
| 5 | 9 | 3706.4 | 4096.2 | 0.905x | dense |
| 6 | 8 | 3706.4 | 2383.4 | 1.555x | ED |
| 7 | 2 | 3706.4 | 2503.4 | 1.481x | ED |

Mean: dense 3,706.5 vs ED 2,970.8 -> **ED 1.248x at the mean** (sim
1.25x). **ED wins 6 of 8 clips and loses the two densest** (clips 1 and
5, at 4,664 and 4,096 us). The activity crossover the simulations
placed INSIDE this dataset is on silicon: for a fixed matched
parallelism, whether event-driven wins is decided clip by clip by
input density, with the break-even at about 3.6 ms of ED work, i.e.
between clip 4 (2,966 us) and clip 5 (4,096 us).

Against the pre-registration: 8/8 held; zero spread held; ED 1.25x at
the mean held; 6 of 8 held; the offset held in kind (constant per
engine, larger than N-MNIST's) but not in size (neither hypothesis).

## The offsets, all four now measured

| engine | N-MNIST (872 words) | DVS-Gesture (3,072 words) |
|---|---|---|
| dense | +8.3 us | +102.0 us |
| ED | +10.7 us | +92.9 us |

Both grow with frame size, by ~12x for 3.5x the words, so the offset
is not a constant and not proportional to words on this comparison
basis. Two known confounds before anyone models it: the DVS-Gesture
sim column excludes the wrapper's word streaming (the N-MNIST column
included ~1.9k wrapper cycles), and the server's cache maintenance on
the DMA buffers scales with buffer size. A wrapper-inclusive cycle
count from the harness for g1, and a server-side timestamp around the
DMA setup, would separate them; until then the offsets stand as
measured and the verdicts, which carry the same offsets on both sides,
do not depend on the split.

## Raw client lines

```
[board] PING ok: build 5, cap 65535 words, dataset DVS-Gesture C1
  sample  0 (digit 0): ok
  sample  1 (digit 6): ok
  sample  2 (digit 1): ok
  sample  3 (digit 7): ok
  sample  4 (digit 10): ok
  sample  5 (digit 9): ok
  sample  6 (digit 8): ok
  sample  7 (digit 2): ok

BOARD PASS: 8 samples, 16384 words, bit-identical to the golden model (8.58 s, 1073 ms/sample incl. UART)
M4's done-when is met: correct results back from real hardware.
[board] BURST sample 0: 100 iterations in 0.412 s -> 4121.0 us/inference (243 inf/s), 0 mismatches, crc 67bd453a  [engine 3706.4 us + server 414.6 us]  die 34.8->34.6 degC
[board]   wall-clock 0.419 s vs board 0.412 s (tick-rate cross-check; wall includes UART overhead)
[board] BURST sample 1: 100 iterations in 0.412 s -> 4121.0 us/inference (243 inf/s), 0 mismatches, crc e57194f7  [engine 3706.5 us + server 414.5 us]  die 35.8->35.5 degC
[board] BURST sample 2: 100 iterations in 0.412 s -> 4121.0 us/inference (243 inf/s), 0 mismatches, crc b01c1c9f  [engine 3706.4 us + server 414.6 us]  die 35.9->35.8 degC
[board] BURST sample 3: 100 iterations in 0.412 s -> 4121.0 us/inference (243 inf/s), 0 mismatches, crc de0a1f48  [engine 3706.5 us + server 414.5 us]  die 35.9->35.9 degC
[board] BURST sample 4: 100 iterations in 0.412 s -> 4121.0 us/inference (243 inf/s), 0 mismatches, crc a1c621d0  [engine 3706.5 us + server 414.5 us]  die 35.9->36.1 degC
[board] BURST sample 5: 100 iterations in 0.412 s -> 4121.0 us/inference (243 inf/s), 0 mismatches, crc 18947469  [engine 3706.4 us + server 414.6 us]  die 36.1->36.1 degC
[board] BURST sample 6: 100 iterations in 0.412 s -> 4121.0 us/inference (243 inf/s), 0 mismatches, crc 069987e3  [engine 3706.4 us + server 414.5 us]  die 36.1->36.0 degC
[board] BURST sample 7: 100 iterations in 0.412 s -> 4121.0 us/inference (243 inf/s), 0 mismatches, crc 14bf7591  [engine 3706.4 us + server 414.6 us]  die 36.1->36.2 degC
[board] BURST sample 0: 800 iterations in 3.297 s -> 4121.0 us/inference (243 inf/s), 0 mismatches, crc 14bf7591  [engine 3706.5 us + server 414.5 us]  die 36.7->37.2 degC
```
