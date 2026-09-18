# Board pass: dense P=4 with N_ENGINES=8 (C0003 replication) on silicon (2026-09-17)

Build: ENGINE=0, DENSE_P=4, N_ENGINES=8, BAKED_WEIGHTS=1, built by
host/vivado/build_engine.tcl (builds/dense_p4_x8_20260917_2312;
bitstream 2026-09-17 23:22:37; WNS +0.041 / WHS +0.034 — the thinnest
margin of any build). Server build 4. Pre-registered:
experiments/dense_p4_x8_prereg_20260917.md (commit 9742c96).

**Pre-write check caught a wrong delivery first.** The first BOOT.bin
copied for this pass had been created with the previous build's
bitstream (the Create Boot Image dialog still pointed at the
ed_k4_x8 .bit) and the .xsa was the previous one too; the .hwh read
ENGINE=1 and the partition matched the ED bitstream. Rejected, rebuilt,
re-checked (ENGINE=0, N_ENGINES=8, bitstream 23:22:37), then written.
Without the check this pass would have measured ED K=4 and called it
dense. Recorded as the reason the boot image must move into the script.

## Correctness

PING build 4 (first attempt: no serial port yet — board still
enumerating; passed ~30 s later). 16/16 N-MNIST check samples
bit-identical, then 200-iteration bursts on every sample (3,200
inferences) and a 1,600-inference sweep: zero CRC mismatches. Eight
near-identical cores in the utilization report (DONT_TOUCH held).

## Latency (engine-only, build-4 words 8..9; 200 iterations/sample)

**1048.9 us on every one of the 16 samples and on the sweep** — the
N=1 P=4 record (2026-09-06) exactly, zero spread. Server overhead
117.5 us. Die 40.2 -> 42.2 degC, the warmest of tonight's four passes
(N=1 passes ran 34-38 degC; ED x8 39.6-41.3). Suggestive only; the
meter decides.

## Resources (utilization_hier.rpt, routed) — the deliverable

| | N=8 whole design | per engine (g_rep[i].core) | predicted | N=1 P=4 whole design (2026-09-06) |
|---|---|---|---|---|
| LUTs | **27,829 (52 % of 53,200)**; 27,611 logic + 16 LUTRAM + 202 SRL | 3,164-3,170 | 24-27k | 5,760 |
| Registers | 45,023 (42 %) | 5,176-5,224 | ~40k | 8,679 |
| Block RAM tiles | 34 RAMB36 + 24 RAMB18 = **46 (33 %)** | 4 + 3/2 = 5.5 | ~38 | 6.5 |
| DSP | 0 | 0 | 0 | 0 |
| WNS / WHS | +0.041 / +0.034 | | 0 to +0.3 | +0.299 / +0.012 |

Two predictions missed in detail: LUTs 3 % above the top of the range
(under the 30k falsification line) and BRAM 46 tiles against ~38 — each
dense engine takes 5.5 tiles under global synthesis, not the 4.5 I
inferred by subtracting the DMA from the N=1 hierarchical report. The
qualitative claim held: the dense engine's replication budget is LUTs
(half the chip), ED's is BRAM (61 %).

## The two replicated bitstreams, side by side (for the meter session)

| | ED K=4 x8 | dense P=4 x8 |
|---|---|---|
| per-engine latency (unchanged by replication) | 688.5 us mean, 554.8-815.8 | 1048.9 us flat |
| LUTs / FFs (whole design) | 11,733 / 7,539 | 27,829 / 45,023 |
| BRAM tiles | 86 | 46 |
| WNS | +0.430 | +0.041 |
| bitstream | builds/ed_k4_x8_20260917_2251 | builds/dense_p4_x8_20260917_2312 |

Both archived on the Mac under host/mac/build/archive/<tag>/ with the
N=1 K=8 and P=8 deliveries (local, git-ignored).

## C0003 status after this pass

Both engines build and pass at N=1 and N=8 with WNS >= 0: the build
half of C0003's done-when is met. Remaining: the metered N=1-vs-N=8
per-engine scaling ratio for at least one design.

## Raw client lines

```
[board] PING ok: build 4, cap 65535 words
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
[board] BURST sample 0: 200 iterations in 0.233 s -> 1166.4 us/inference (857 inf/s), 0 mismatches, crc 8c0547d6  [engine 1048.9 us + server 117.5 us]  die 40.2->40.5 degC
[board]   wall-clock 0.240 s vs board 0.233 s (tick-rate cross-check; wall includes UART overhead)
[board] BURST sample 1: 200 iterations in 0.233 s -> 1166.4 us/inference (857 inf/s), 0 mismatches, crc 64496222  [engine 1048.9 us + server 117.5 us]  die 40.7->41.0 degC
[board] BURST sample 2: 200 iterations in 0.233 s -> 1166.4 us/inference (857 inf/s), 0 mismatches, crc eb268d5e  [engine 1048.9 us + server 117.5 us]  die 40.8->41.1 degC
[board] BURST sample 3: 200 iterations in 0.233 s -> 1166.4 us/inference (857 inf/s), 0 mismatches, crc 59cf14da  [engine 1048.9 us + server 117.5 us]  die 41.0->41.2 degC
[board] BURST sample 4: 200 iterations in 0.233 s -> 1166.4 us/inference (857 inf/s), 0 mismatches, crc fed59c62  [engine 1048.9 us + server 117.5 us]  die 40.9->41.2 degC
[board] BURST sample 5: 200 iterations in 0.233 s -> 1166.4 us/inference (857 inf/s), 0 mismatches, crc 27180e7b  [engine 1048.9 us + server 117.5 us]  die 41.0->41.3 degC
[board] BURST sample 6: 200 iterations in 0.233 s -> 1166.4 us/inference (857 inf/s), 0 mismatches, crc 7d47a3f4  [engine 1048.9 us + server 117.5 us]  die 41.1->41.3 degC
[board] BURST sample 7: 200 iterations in 0.233 s -> 1166.4 us/inference (857 inf/s), 0 mismatches, crc 9e652337  [engine 1048.9 us + server 117.5 us]  die 41.1->41.3 degC
[board] BURST sample 8: 200 iterations in 0.233 s -> 1166.4 us/inference (857 inf/s), 0 mismatches, crc a7fa0875  [engine 1048.9 us + server 117.5 us]  die 41.1->41.3 degC
[board] BURST sample 9: 200 iterations in 0.233 s -> 1166.4 us/inference (857 inf/s), 0 mismatches, crc dd2a4b20  [engine 1048.9 us + server 117.5 us]  die 41.1->41.4 degC
[board] BURST sample 10: 200 iterations in 0.233 s -> 1166.4 us/inference (857 inf/s), 0 mismatches, crc 583bccab  [engine 1048.9 us + server 117.5 us]  die 41.2->41.3 degC
[board] BURST sample 11: 200 iterations in 0.233 s -> 1166.4 us/inference (857 inf/s), 0 mismatches, crc a59c6c4c  [engine 1048.9 us + server 117.5 us]  die 41.2->41.5 degC
[board] BURST sample 12: 200 iterations in 0.233 s -> 1166.4 us/inference (857 inf/s), 0 mismatches, crc 89f456f7  [engine 1048.9 us + server 117.5 us]  die 41.2->41.3 degC
[board] BURST sample 13: 200 iterations in 0.233 s -> 1166.4 us/inference (857 inf/s), 0 mismatches, crc 04e329e3  [engine 1048.9 us + server 117.5 us]  die 41.2->41.6 degC
[board] BURST sample 14: 200 iterations in 0.233 s -> 1166.4 us/inference (857 inf/s), 0 mismatches, crc 4aa3061e  [engine 1048.9 us + server 117.5 us]  die 41.3->41.6 degC
[board] BURST sample 15: 200 iterations in 0.233 s -> 1166.4 us/inference (857 inf/s), 0 mismatches, crc 89e867eb  [engine 1048.9 us + server 117.5 us]  die 41.4->41.5 degC
[board] BURST sample 0: 1600 iterations in 1.866 s -> 1166.4 us/inference (857 inf/s), 0 mismatches, crc 89e867eb  [engine 1048.9 us + server 117.5 us]  die 41.5->42.2 degC
```
