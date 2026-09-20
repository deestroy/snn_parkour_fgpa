# Board pass: DVS-Gesture C1, dense P=4 replicated x2 (C0003) on silicon (2026-09-20, 12:02)

Build: ENGINE=0, DENSE_P=4, DATASET=1, N_ENGINES=2, m4_conv2/builds/
dense_p4_dvsg_x2_20260920_1127 (bitstream 2026-09-20 11:33:11, WNS +0.842
/ WHS +0.028), rev 3 engine. N=4 did not place ("Placer could not place
all instances": 4 x 16,384 decoded-enable output-bit flops); N=2 is
the replicated dense build for this dataset. Server build 5 DATASET=1.
Estimate 1.956 W total, fabric 270 mW, 21 BRAM tiles.

## Result

PING build 5, DVS-Gesture C1. **8/8 bit-identical**, 700 burst
inferences and an 800-inference sweep clean. **3,706.4-3,706.5 us on
every clip** and on the sweep -- equal to the N=1 dense pass
(2026-09-19). Server 414.6 us. Die 33.5-35.5 degC.

With pass 13 (ED K=4 x4), the replicated pair for DVS-Gesture is on
silicon: ED x4 (86 tiles, 1.926 W est.) and dense x2 (21 tiles, 1.956 W
est.), per-engine latency unchanged by replication in both. The meter
session's rows 9 and 10 (measure/metering_prereg_2026-09-19.md).

## Raw client lines

```
Traceback (most recent call last):
  File "/Users/dhritiaravind/git_projects/snn_parkour_fpga/host/uart_client.py", line 150, in <module>
    raise SystemExit(main())
  File "/Users/dhritiaravind/git_projects/snn_parkour_fpga/host/uart_client.py", line 137, in main
    ok = run_samples(link, label="board", dataset=args.dataset)
  File "/Users/dhritiaravind/git_projects/snn_parkour_fpga/host/uart_client.py", line 43, in run_samples
    info = link.call(CMD_PING, np.zeros(0, "<u4"))
  File "/Users/dhritiaravind/git_projects/snn_parkour_fpga/host/snn_link.py", line 119, in call
    rcmd, words = self.recv()
  File "/Users/dhritiaravind/git_projects/snn_parkour_fpga/host/snn_link.py", line 97, in recv
    win = (win + self._read_exact(1))[-4:]
  File "/Users/dhritiaravind/git_projects/snn_parkour_fpga/host/snn_link.py", line 88, in _read_exact
    raise TimeoutError("link: no data (%d/%d bytes)" % (len(buf), n))
TimeoutError: link: no data (0/1 bytes)
--- retry
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
[board] BURST sample 0: 100 iterations in 0.412 s -> 4121.0 us/inference (243 inf/s), 0 mismatches, crc 67bd453a  [engine 3706.4 us + server 414.6 us]  die 33.5->33.6 degC
[board]   wall-clock 0.419 s vs board 0.412 s (tick-rate cross-check; wall includes UART overhead)
[board] BURST sample 1: 100 iterations in 0.412 s -> 4121.0 us/inference (243 inf/s), 0 mismatches, crc e57194f7  [engine 3706.4 us + server 414.6 us]  die 33.5->33.6 degC
[board] BURST sample 2: 100 iterations in 0.412 s -> 4121.0 us/inference (243 inf/s), 0 mismatches, crc b01c1c9f  [engine 3706.4 us + server 414.5 us]  die 33.3->33.6 degC
[board] BURST sample 3: 100 iterations in 0.412 s -> 4121.0 us/inference (243 inf/s), 0 mismatches, crc de0a1f48  [engine 3706.5 us + server 414.5 us]  die 33.8->33.9 degC
[board] BURST sample 4: 100 iterations in 0.412 s -> 4121.0 us/inference (243 inf/s), 0 mismatches, crc a1c621d0  [engine 3706.4 us + server 414.6 us]  die 34.0->34.0 degC
[board] BURST sample 5: 100 iterations in 0.412 s -> 4121.0 us/inference (243 inf/s), 0 mismatches, crc 18947469  [engine 3706.4 us + server 414.5 us]  die 34.1->34.2 degC
[board] BURST sample 6: 100 iterations in 0.412 s -> 4121.0 us/inference (243 inf/s), 0 mismatches, crc 069987e3  [engine 3706.5 us + server 414.5 us]  die 34.2->34.3 degC
[board] BURST sample 7: 100 iterations in 0.412 s -> 4121.0 us/inference (243 inf/s), 0 mismatches, crc 14bf7591  [engine 3706.5 us + server 414.5 us]  die 34.1->34.4 degC
[board] BURST sample 0: 800 iterations in 3.297 s -> 4121.0 us/inference (243 inf/s), 0 mismatches, crc 14bf7591  [engine 3706.5 us + server 414.5 us]  die 35.0->35.5 degC
```
