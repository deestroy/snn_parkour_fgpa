# Scripted Vivado build (host/vivado/build_engine.tcl)

One command replaces the click sequence in docs/vivado_session_next.md
and removes the three ways that sequence went wrong on 2026-09-06
(stale customisation, stale Design Runs table, bitstream re-written
under a different run's timing report).

From the Vivado Tcl Console with m4_conv open:

    set ENGINE 1; set ED_K 8; set DENSE_P 4
    source C:/Users/dhritiaravind/snn_parkour_fpga/host/vivado/build_engine.tcl

(adjust the path to wherever the repo copy lives on the VM). Or batch:

    vivado -mode batch -source build_engine.tcl -tclargs 0 4 8      ;# dense P=8
    vivado -mode batch -source build_engine.tcl -tclargs 1 8 4      ;# ED K=8

What it does and refuses to skip:
1. sets the five block-design parameters and reads them back;
2. checks both DMA data masters are address-mapped (assigns if not);
3. validate, save, regenerate, full synth+impl+bitstream with
   auto-incremental checkpoints OFF (deterministic runs);
4. reads WNS/TNS/WHS from the run and STOPS before exporting if WNS or
   WHS is negative (the timing reports are still copied out);
5. utilization (hierarchical), power, timing reports;
6. `write_hw_platform -include_bit` -> the .xsa;
7. optionally `bootgen` a BOOT.bin if FSBL_ELF / APP_ELF are filled in
   at the top of the script; otherwise Create Boot Image in Vitis with
   the bitstream path it prints;
8. `summary.txt` with parameters, timing, and paths.

Output: `C:/Users/dhritiaravind/m4_conv/builds/<engine>_<YYYYmmdd_HHMM>/`.
Copy that folder's BOOT.bin + design_1_wrapper.xsa to host/mac/build on
the Mac as before; the Mac-side pre-write checks are unchanged.

Not covered: the Vitis app rebuild (only needed when conv_server.c
changes) and the optional -O2 setting.
