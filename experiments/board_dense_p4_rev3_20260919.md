# Board pass: dense P=4 N=1 N-MNIST with C0035 rev 3 (2026-09-19, 23:48)

Build: ENGINE=0, DENSE_P=4, DATASET=0, N_ENGINES=1, m4_conv2/builds/
dense_p4_20260919_2323 (bitstream 23:26:05, WNS +0.768 / WHS +0.015;
the rev 2 build of this configuration closed at +0.299 on 2026-09-06).
Server build 5, DATASET=0 (PING: "build 5, dataset N-MNIST C1").
Purpose: rev 3 (registered output bit-file write) validated on N-MNIST,
and the single-engine dense power estimate for the metering
pre-registration (experiments/power_estimates/, 73 mW fabric).

## Result

16/16 bit-identical; 200-iteration bursts on all 16 samples and a
1,600-inference sweep, zero CRC mismatches; **1,048.9 us on every
sample and on the sweep** -- identical to the rev 2 record of
2026-09-06 (experiments/board_dense_p4_20260906.md) to 0.1 us. Rev 3
changes no cycle count on either dataset. Server overhead 117.6 us.
Die 32.5 degC (coolest pass on record; overnight, board just powered).

Rev 3 is now on silicon on both datasets (DVS-Gesture at 15:04, N-MNIST
here) with the same results as rev 2 where rev 2 existed, and 1.1 ns
of margin where rev 2 failed.

## Raw client lines

```
[board] PING ok: build 5, cap 65535 words, dataset N-MNIST C1
  sample  0 (digit 0): ok
  sample  1 (digit 0): ok
  sample  2 (digit 0): ok
  sample  3 (digit 0): ok
  sample  4 (digit 0): ok
  sample  5 (digit 1): ok
  sample  6 (digit 2): ok
  sample  7 (digit 3): ok
  sample  8 (digit 3): ok
  sample  9 (digit 3): ok
  sample 10 (digit 6): ok
  sample 11 (digit 7): ok
  sample 12 (digit 7): ok
  sample 13 (digit 7): ok
  sample 14 (digit 8): ok
  sample 15 (digit 8): ok

BOARD PASS: 16 samples, 9280 words, bit-identical to the golden model (4.90 s, 306 ms/sample incl. UART)
M4's done-when is met: correct results back from real hardware.
[board] BURST sample 0: 200 iterations in 0.233 s -> 1166.5 us/inference (857 inf/s), 0 mismatches, crc 8c0547d6  [engine 1048.9 us + server 117.6 us]  die 32.5->32.5 degC
[board]   wall-clock 0.240 s vs board 0.233 s (tick-rate cross-check; wall includes UART overhead)
[board] BURST sample 1: 200 iterations in 0.233 s -> 1166.5 us/inference (857 inf/s), 0 mismatches, crc 64496222  [engine 1048.9 us + server 117.6 us]  die 33.4->33.3 degC
[board] BURST sample 2: 200 iterations in 0.233 s -> 1166.5 us/inference (857 inf/s), 0 mismatches, crc eb268d5e  [engine 1048.9 us + server 117.6 us]  die 33.7->33.4 degC
[board] BURST sample 3: 200 iterations in 0.233 s -> 1166.5 us/inference (857 inf/s), 0 mismatches, crc 59cf14da  [engine 1048.9 us + server 117.6 us]  die 33.3->33.6 degC
[board] BURST sample 4: 200 iterations in 0.233 s -> 1166.5 us/inference (857 inf/s), 0 mismatches, crc fed59c62  [engine 1048.9 us + server 117.6 us]  die 33.7->33.4 degC
[board] BURST sample 5: 200 iterations in 0.233 s -> 1166.5 us/inference (857 inf/s), 0 mismatches, crc 27180e7b  [engine 1048.9 us + server 117.6 us]  die 33.7->33.7 degC
[board] BURST sample 6: 200 iterations in 0.233 s -> 1166.5 us/inference (857 inf/s), 0 mismatches, crc 7d47a3f4  [engine 1048.9 us + server 117.6 us]  die 33.7->33.8 degC
[board] BURST sample 7: 200 iterations in 0.233 s -> 1166.5 us/inference (857 inf/s), 0 mismatches, crc 9e652337  [engine 1048.9 us + server 117.6 us]  die 33.7->33.7 degC
[board] BURST sample 8: 200 iterations in 0.233 s -> 1166.5 us/inference (857 inf/s), 0 mismatches, crc a7fa0875  [engine 1048.9 us + server 117.6 us]  die 33.8->33.9 degC
[board] BURST sample 9: 200 iterations in 0.233 s -> 1166.5 us/inference (857 inf/s), 0 mismatches, crc dd2a4b20  [engine 1048.9 us + server 117.6 us]  die 33.9->33.7 degC
[board] BURST sample 10: 200 iterations in 0.233 s -> 1166.5 us/inference (857 inf/s), 0 mismatches, crc 583bccab  [engine 1048.9 us + server 117.6 us]  die 33.9->33.9 degC
[board] BURST sample 11: 200 iterations in 0.233 s -> 1166.5 us/inference (857 inf/s), 0 mismatches, crc a59c6c4c  [engine 1048.9 us + server 117.6 us]  die 34.0->33.9 degC
[board] BURST sample 12: 200 iterations in 0.233 s -> 1166.5 us/inference (857 inf/s), 0 mismatches, crc 89f456f7  [engine 1048.9 us + server 117.6 us]  die 33.9->34.1 degC
[board] BURST sample 13: 200 iterations in 0.233 s -> 1166.5 us/inference (857 inf/s), 0 mismatches, crc 04e329e3  [engine 1048.9 us + server 117.6 us]  die 33.7->33.9 degC
[board] BURST sample 14: 200 iterations in 0.233 s -> 1166.5 us/inference (857 inf/s), 0 mismatches, crc 4aa3061e  [engine 1048.9 us + server 117.6 us]  die 34.3->34.1 degC
[board] BURST sample 15: 200 iterations in 0.233 s -> 1166.5 us/inference (857 inf/s), 0 mismatches, crc 89e867eb  [engine 1048.9 us + server 117.6 us]  die 34.3->34.2 degC
[board] BURST sample 0: 1600 iterations in 1.866 s -> 1166.5 us/inference (857 inf/s), 0 mismatches, crc 89e867eb  [engine 1048.9 us + server 117.6 us]  die 34.5->34.7 degC
```
