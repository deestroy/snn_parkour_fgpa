# build_engine.tcl -- one-command Vivado build of an axis_conv_top configuration.
#
# Does, in order, exactly what the manual session list does:
#   set the block-design parameters -> check them back -> check the DMA
#   address map (3 assignments) -> validate -> regenerate -> full rebuild
#   (synthesis, implementation, bitstream) -> read WNS/WHS/TNS from the run
#   -> STOP if WNS < 0 -> utilization + power + timing reports -> export
#   the .xsa with bitstream -> (optional) bootgen a BOOT.bin -> write a
#   summary.txt.  Everything lands in  <project>/builds/<tag>/ .
#
# Run from the Vivado Tcl Console with the project open:
#     set ENGINE 1; set ED_K 8; set DENSE_P 4; source C:/Users/dhritiaravind/snn_parkour_fpga/host/vivado/build_engine.tcl
# or from a Vivado Tcl shell / batch:
#     vivado -mode batch -source build_engine.tcl -tclargs ENGINE ED_K DENSE_P
#     e.g.  vivado -mode batch -source build_engine.tcl -tclargs 0 4 8    (dense P=8)
#
# While it runs the Tcl console is busy (wait_on_run) -- 5-15 minutes.
# Do not click Generate Bitstream or touch the block design meanwhile.

# ---------------------------------------------------------------- settings
set PROJECT   "C:/Users/dhritiaravind/m4_conv/m4_conv.xpr"
set BD_CELL   "axis_conv_top_0"
set JOBS      4
# Boot-image inputs (optional). Leave "" to skip bootgen and use Vitis by hand.
set FSBL_ELF  ""      ;# e.g. C:/Users/dhritiaravind/vitis_m4_loopback_zed/zed_board/export/zed_board/sw/.../fsbl.elf
set APP_ELF   ""      ;# e.g. C:/Users/dhritiaravind/vitis_m4_loopback_zed/conv_server/build/conv_server.elf
set BOOTGEN   "C:/Xilinx/Vitis/2024.1/bin/bootgen.bat"

# parameters: from -tclargs if given, else from variables set before `source`
if {[info exists argv] && [llength $argv] >= 3} {
    lassign $argv ENGINE ED_K DENSE_P
}
foreach v {ENGINE ED_K DENSE_P} {
    if {![info exists $v]} { error "set $v before sourcing (e.g. set ENGINE 1; set ED_K 8; set DENSE_P 4)" }
}
set BAKED 1
set NENG  1
if {$ENGINE} { set tag "ed_k${ED_K}" } else { set tag "dense_p${DENSE_P}" }
set tag "${tag}_[clock format [clock seconds] -format %Y%m%d_%H%M]"
set proj_dir [file dirname $PROJECT]
set out "$proj_dir/builds/$tag"
file mkdir $out
proc say {msg} { puts "\[build_engine\] $msg" }
say "configuration: ENGINE=$ENGINE ED_K=$ED_K DENSE_P=$DENSE_P BAKED=$BAKED N_ENGINES=$NENG -> $out"

# ---------------------------------------------------------------- project
if {[catch {current_project}]} { open_project $PROJECT }
# deterministic runs: the auto-incremental reference checkpoint made two
# implementations of the same netlist differ by 300k config bytes
set_property AUTO_INCREMENTAL_CHECKPOINT 0 [get_runs synth_1]
set_property AUTO_INCREMENTAL_CHECKPOINT 0 [get_runs impl_1]

# ---------------------------------------------------------------- block design
set bd [get_files -quiet design_1.bd]
if {$bd eq ""} { error "design_1.bd not in project" }
open_bd_design $bd
set cell [get_bd_cells $BD_CELL]
set_property -dict [list \
    CONFIG.ENGINE        $ENGINE \
    CONFIG.ED_K          $ED_K \
    CONFIG.DENSE_P       $DENSE_P \
    CONFIG.BAKED_WEIGHTS $BAKED \
    CONFIG.N_ENGINES     $NENG ] $cell
# read back -- this is the check that caught the ENGINE=0 stale-customisation build
foreach {p want} [list ENGINE $ENGINE ED_K $ED_K DENSE_P $DENSE_P BAKED_WEIGHTS $BAKED N_ENGINES $NENG] {
    set got [get_property CONFIG.$p $cell]
    if {$got != $want} { error "parameter $p reads back $got, wanted $want" }
    say "  CONFIG.$p = $got"
}

# DMA address map: both data masters must be mapped, nothing excluded
foreach sp {Data_MM2S Data_S2MM} {
    set segs [get_bd_addr_segs -quiet -of_objects [get_bd_addr_spaces axi_dma_0/$sp]]
    if {[llength $segs] == 0} {
        say "  $sp has no address assignment -- running assign_bd_address"
        assign_bd_address
        set segs [get_bd_addr_segs -quiet -of_objects [get_bd_addr_spaces axi_dma_0/$sp]]
        if {[llength $segs] == 0} { error "$sp still unassigned" }
    }
    say "  $sp -> $segs"
}
set excl [get_bd_addr_segs -quiet -excluded]
if {[llength $excl]} { error "excluded address segments present: $excl" }

validate_bd_design
save_bd_design
generate_target all $bd

# ---------------------------------------------------------------- build
reset_run synth_1
foreach r [get_runs -quiet *axis_conv_top*synth*] { reset_run $r }
launch_runs impl_1 -to_step write_bitstream -jobs $JOBS
say "runs launched; waiting (this blocks the console)..."
wait_on_run impl_1
set status [get_property STATUS [get_runs impl_1]]
say "impl_1 status: $status"
if {![string match "*write_bitstream Complete*" $status]} { error "implementation did not complete: $status" }

# ---------------------------------------------------------------- timing gate
set wns [get_property STATS.WNS [get_runs impl_1]]
set tns [get_property STATS.TNS [get_runs impl_1]]
set whs [get_property STATS.WHS [get_runs impl_1]]
say "WNS=$wns TNS=$tns WHS=$whs"
set impl_dir [get_property DIRECTORY [get_runs impl_1]]
foreach f [glob -nocomplain $impl_dir/*timing_summary_routed.rpt $impl_dir/*utilization_placed.rpt $impl_dir/*power_routed.rpt] {
    file copy -force $f $out
}
if {$wns < 0 || $whs < 0} {
    say "TIMING FAILED -- nothing exported. Top paths are in $out/*timing_summary_routed.rpt"
    error "WNS=$wns WHS=$whs"
}

# ---------------------------------------------------------------- reports + export
open_run impl_1
report_utilization -hierarchical -file $out/utilization_hier.rpt
report_power -file $out/power.rpt
close_design
set xsa "$out/design_1_wrapper.xsa"
write_hw_platform -fixed -include_bit -force $xsa
say "exported $xsa"

# ---------------------------------------------------------------- optional bootgen
set bit [glob -nocomplain $impl_dir/design_1_wrapper.bit]
if {$FSBL_ELF ne "" && $APP_ELF ne "" && [file exists $FSBL_ELF] && [file exists $APP_ELF] && [file exists $BOOTGEN]} {
    set bif [open $out/boot.bif w]
    puts $bif "the_ROM_image:\n{\n  \[bootloader\] $FSBL_ELF\n  $bit\n  $APP_ELF\n}"
    close $bif
    if {[catch {exec $BOOTGEN -arch zynq -image $out/boot.bif -o $out/BOOT.bin -w on} msg]} {
        say "bootgen failed: $msg"
    } else { say "BOOT.bin written to $out" }
} else {
    say "bootgen skipped (FSBL_ELF/APP_ELF not set) -- Create Boot Image in Vitis with $bit"
}

# ---------------------------------------------------------------- summary
set s [open $out/summary.txt w]
puts $s "tag        $tag"
puts $s "params     ENGINE=$ENGINE ED_K=$ED_K DENSE_P=$DENSE_P BAKED=$BAKED N_ENGINES=$NENG"
puts $s "timing     WNS=$wns TNS=$tns WHS=$whs"
puts $s "bitstream  $bit"
puts $s "xsa        $xsa"
puts $s "built      [clock format [clock seconds]]"
close $s
say "DONE -> copy $out (BOOT.bin/.xsa + summary.txt) to the Mac"
