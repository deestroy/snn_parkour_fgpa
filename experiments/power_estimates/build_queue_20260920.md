# Overnight build queue, 2026-09-20 (provenance for the estimate rows)

`host/vivado/build_queue.tcl` run unattended on the VM at 00:10. The
per-build folders live on the VM (`m4_conv2/builds/<tag>/`) and their
reports are in this directory; the queue's own log is on the VM in
`m4_conv2/builds/queue_20260920_0010.log` and is transcribed here
because `host/mac/build/` (the delivery directory) is git-ignored.

```
00:10:08 START set ENGINE 1; set ED_K 4; set DENSE_P 4; set DATASET 1; set N_ENGINES 4
00:13:33 DONE
00:13:33 START set ENGINE 0; set ED_K 4; set DENSE_P 4; set DATASET 1; set N_ENGINES 4
00:18:42 FAILED: ERROR: [Common 17-39] 'wait_on_runs' failed due to earlier errors.
00:18:42 START set ENGINE 1; set ED_K 4; set DENSE_P 4; set STRATEGY Performance_Explore
00:21:18 DONE
00:21:18 START set ENGINE 1; set ED_K 4; set DENSE_P 4; set STRATEGY Congestion_SpreadLogic_high
00:23:53 DONE
00:23:53 START set ENGINE 0; set ED_K 4; set DENSE_P 4; set STRATEGY Performance_Explore
00:26:54 DONE
00:26:54 START set ENGINE 0; set ED_K 4; set DENSE_P 4; set STRATEGY Congestion_SpreadLogic_high
00:29:58 DONE
```

The one failure, re-run alone at 11:25 to capture the message the run
logs had by then overwritten:

```
71 Infos, 35 Warnings, 0 Critical Warnings and 3 Errors encountered.
place_design failed
ERROR: [Common 17-69] Command failed: Placer could not place all instances
```

Dense P=4 at DATASET=1 with N_ENGINES=4 is 4 x 16,384 output-bit flops,
each with a decoded enable; the placer cannot pack them even though the
raw flop count is ~64 % of the device. The replicated dense build for
DVS-Gesture is therefore N=2 (pass 14). Two earlier queue attempts
(00:01, 00:03) aborted on a Tcl comment inside the QUEUE brace list,
fixed the same night; their ed_k4_dvsg_x4 folders are duplicates of the
00:10 one and are not cited anywhere.
