# Vivado power estimates per build (report_power on the routed design, default vectorless activity)

Collected 2026-09-19 from the VM's builds/<tag>/power.rpt, written by
host/vivado/build_engine.tcl at the end of every scripted build with
`report_power -file ...` on the routed design and NO switching-activity
input: Vivado's default vectorless propagation (report: clock nodes
'High', I/O 'High', internal nodes 'Medium -- user specified less than
25 % of internal nodes'), identical for every build. Every report carries
Vivado warning 33-332 (switching activity implies high-fanout reset nets
asserted for long periods; estimate may be inaccurate). These are the
THESIS ESTIMATE COLUMN, to be set against the meter (M5); they are not
measurements. The 2026-09-05 ED K=4 N=1 report (1.727 W total, ~49 mW
fabric; experiments/board_ed_k4_20260905.md) was a GUI build with the
same default setting; the 2026-09-06 dense P=4 N=1 GUI report was not
preserved; dense_p4_20260919_2323 (rev 3, same RTL apart from the
registered bit-file write) is its replacement estimate.

Fabric = clocks + slice logic + signals + BRAM (+ DSP, always 0). PS7 is
the ARM subsystem's estimate and dominates every total.

| build tag | what | WNS | total W | dynamic | static | clocks | logic | signals | BRAM | DSP | PS7 | fabric mW |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| dense_p4_20260919_2323 | dense P=4 N-MNIST, rev 3, m4_conv2 (pass 12) | 0.768 | 1.750 | 1.606 | 0.144 | 0.021 | 0.013 | 0.026 | 0.013 | 0.000 | 1.533 | 73.0 |
| dense_p4_dvsg_20260919_1447 | dense P=4 DVS-Gesture, rev 3 (pass 11) | 1.091 | 1.814 | 1.668 | 0.146 | 0.036 | 0.012 | 0.064 | 0.023 | — | 1.533 | 135.0 |
| dense_p4_x8_20260917_2312 | dense P=4 x8 N-MNIST (pass 8) | 0.041 | 2.196 | 2.034 | 0.162 | 0.057 | 0.093 | 0.250 | 0.101 | — | 1.533 | 501.0 |
| dense_p4_x8_20260918_1004 | (superseded/intermediate run) | 0.041 | 2.196 | 2.034 | 0.162 | 0.057 | 0.093 | 0.250 | 0.101 | — | 1.533 | 501.0 |
| dense_p4_x8_20260918_1011 | (superseded/intermediate run) | 0.041 | 2.196 | 2.034 | 0.162 | 0.057 | 0.093 | 0.250 | 0.101 | — | 1.533 | 501.0 |
| dense_p8_20260917_2221 | dense P=8 N-MNIST (pass 6) | 0.101 | 1.761 | 1.617 | 0.144 | 0.021 | 0.012 | 0.034 | 0.016 | — | 1.533 | 83.0 |
| ed_k4_20260918_1213 | (superseded/intermediate run) | 0.475 | 1.721 | 1.581 | 0.140 | 0.015 | 0.007 | 0.010 | 0.016 | — | 1.533 | 48.0 |
| ed_k4_20260918_1232 | (superseded/intermediate run) | 0.475 | 1.721 | 1.581 | 0.140 | 0.015 | 0.007 | 0.010 | 0.016 | — | 1.533 | 48.0 |
| ed_k4_20260918_1300 | ED K=4 N-MNIST, C0044, m4_conv2 (pass 9) | 0.475 | 1.724 | 1.581 | 0.144 | 0.015 | 0.007 | 0.010 | 0.016 | — | 1.533 | 48.0 |
| ed_k4_dvsg_20260919_1324 | ED K=4 DVS-Gesture (pass 10) | 0.190 | 1.750 | 1.604 | 0.145 | 0.017 | 0.010 | 0.015 | 0.030 | — | 1.533 | 72.0 |
| ed_k4_x8_20260917_2251 | ED K=4 x8 N-MNIST (pass 7) | 0.430 | 1.933 | 1.775 | 0.157 | 0.031 | 0.032 | 0.045 | 0.133 | — | 1.533 | 241.0 |
| ed_k8_20260917_2106 | ED K=8 N-MNIST (pass 5) | 0.332 | 1.731 | 1.587 | 0.144 | 0.017 | 0.008 | 0.012 | 0.017 | — | 1.533 | 54.0 |
| ed_k4_dvsg_x4_20260920_0010 | ED K=4 DVS-Gesture x4 (pass 13) | 0.119 | 1.926 | 1.769 | 0.157 | 0.027 | 0.032 | 0.049 | 0.128 | 0.000 | 1.533 | 236.0 |
| dense_p4_dvsg_x2_20260920_1127 | dense P=4 DVS-Gesture x2 (pass pending) | 0.842 | 1.956 | 1.805 | 0.151 | 0.053 | 0.036 | 0.136 | 0.045 | 0.000 | 1.533 | 270.0 |
| ed_k4_performance_explore_20260920_0018 | ED K=4 N-MNIST, strategy Performance_Explore (C0019, not on board) | 0.346 | 1.733 | 1.589 | 0.144 | 0.016 | 0.007 | 0.010 | 0.024 | 0.000 | 1.533 | 57.0 |
| ed_k4_congestion_spreadlogic_high_20260920_0021 | ED K=4 N-MNIST, strategy Congestion_SpreadLogic_high (C0019, not on board) | 0.499 | 1.727 | 1.583 | 0.144 | 0.017 | 0.007 | 0.010 | 0.016 | 0.000 | 1.533 | 50.0 |
| dense_p4_performance_explore_20260920_0023 | dense P=4 N-MNIST, strategy Performance_Explore (C0019, not on board) | 0.388 | 1.750 | 1.607 | 0.144 | 0.021 | 0.013 | 0.026 | 0.013 | 0.000 | 1.533 | 73.0 |
| dense_p4_congestion_spreadlogic_high_20260920_0026 | dense P=4 N-MNIST, strategy Congestion_SpreadLogic_high (C0019, not on board) | 0.354 | 1.753 | 1.609 | 0.144 | 0.022 | 0.013 | 0.028 | 0.013 | 0.000 | 1.533 | 76.0 |

Rows marked superseded are earlier attempts of the same configuration
(a wrong-top build, a build without the board preset, launcher failures)
kept only because their reports existed; cite the named rows.

Files: <tag>_power.rpt and <tag>_summary.txt for the named builds.
