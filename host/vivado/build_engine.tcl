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
set JOBS      2   ;# this VM's launcher is flaky with many parallel jobs
# Boot-image inputs (optional). Leave "" to skip bootgen and use Vitis by hand.
set FSBL_ELF  ""      ;# e.g. C:/Users/dhritiaravind/vitis_m4_loopback_zed/zed_board/export/zed_board/sw/.../fsbl.elf
set APP_ELF   ""      ;# e.g. C:/Users/dhritiaravind/vitis_m4_loopback_zed/conv_server/build/conv_server.elf
set BOOTGEN   "C:/Xilinx/Vitis/2024.1/bin/bootgen.bat"
# Mac folder redirected into this RDP session (Microsoft Remote Desktop ->
# edit PC -> Folders). It shows up in the VM as \\tsclient\<folder name>.
# Leave "" to skip; then copy builds/<tag>/ by hand.
set MAC_DIR   ""      ;# e.g. //tsclient/build

# parameters: from -tclargs if given, else from variables set before `source`
if {[info exists argv] && [llength $argv] >= 3} {
    lassign $argv ENGINE ED_K DENSE_P
}
foreach v {ENGINE ED_K DENSE_P} {
    if {![info exists $v]} { error "set $v before sourcing (e.g. set ENGINE 1; set ED_K 8; set DENSE_P 4)" }
}
set BAKED 1
set NENG  1
# REUSE_RUN 1: do NOT rebuild -- take the already-completed impl_1 (must be
# "write_bitstream Complete" and not out of date) and only do the checks,
# reports and export.  For re-exporting after a post-build script error.
if {![info exists REUSE_RUN]} { set REUSE_RUN 0 }
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
if {!$REUSE_RUN} {
    set_property -dict [list \
        CONFIG.ENGINE        $ENGINE \
        CONFIG.ED_K          $ED_K \
        CONFIG.DENSE_P       $DENSE_P \
        CONFIG.BAKED_WEIGHTS $BAKED \
        CONFIG.N_ENGINES     $NENG ] $cell
}
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
        if {$REUSE_RUN} { error "$sp unassigned -- the completed run cannot be reused" }
        say "  $sp has no address assignment -- running assign_bd_address"
        assign_bd_address
        set segs [get_bd_addr_segs -quiet -of_objects [get_bd_addr_spaces axi_dma_0/$sp]]
        if {[llength $segs] == 0} { error "$sp still unassigned" }
    }
    say "  $sp -> $segs"
}
# excluded segments matter only INSIDE the DMA masters' address spaces (a
# global -excluded query also lists every slave's own segment as seen from
# spaces that legitimately don't map it -- the first run tripped on that)
foreach sp {Data_MM2S Data_S2MM} {
    set excl [get_bd_addr_segs -quiet -excluded -of_objects [get_bd_addr_spaces axi_dma_0/$sp]]
    if {[llength $excl]} { error "$sp has excluded segments: $excl" }
}

if {$REUSE_RUN} {
    say "REUSE_RUN: block design left untouched (no validate/save/generate)"
} else {
validate_bd_design
# This VM intermittently reports "Spawn failed: No error" from the helper
# process Vivado forks AFTER writing the .bd (seen 2026-09-17). Treat the
# save as successful iff the file on disk is fresh.
set bd_path [get_property NAME $bd]
if {[catch {save_bd_design} msg]} { say "save_bd_design reported: $msg" }
if {[clock seconds] - [file mtime $bd_path] > 120} { error "design_1.bd was NOT rewritten (mtime stale) -- save really failed" }
say "  design_1.bd written [clock format [file mtime $bd_path] -format %H:%M:%S]"
if {[catch {generate_target all $bd} msg]} {
    say "generate_target reported: $msg -- retrying once"
    after 5000
    generate_target all $bd
}
}

# ---------------------------------------------------------------- build
# Two ways to build. (A) the project runs, which spawn child Vivado
# processes -- this VM's launcher fails intermittently ("Spawn failed: No
# error", or a run left at "Scripts Generated"), so (A) is tried briefly
# and (B) takes over: the same synth/opt/place/route/bitstream commands run
# INSIDE this process, spawning nothing.  Results are identical in kind;
# (B) synthesises the block design globally (no OOC checkpoints).
set PART [get_property PART [current_project]]
set used_inprocess 0

# open_run / synth_design refuse to start while a design is open, and the
# GUI keeps every implemented design the user opened (impl_1, impl_1_2, ...)
# -- stale views of earlier implementations, safe to close.
proc close_all_designs {} {
    foreach d [get_designs -quiet] { current_design $d; close_design }
}
close_all_designs

proc try_project_runs {jobs} {
    reset_run synth_1
    foreach r [get_runs -quiet *axis_conv_top*synth*] { reset_run $r }
    for {set attempt 1} {$attempt <= 3} {incr attempt} {
        if {[catch {launch_runs impl_1 -to_step write_bitstream -jobs $jobs} msg]} {
            say "launch_runs attempt $attempt: $msg"
        }
        after 15000
        set st [get_property STATUS [get_runs impl_1]]
        set sst [get_property STATUS [get_runs synth_1]]
        say "launch attempt $attempt: synth_1='$sst' impl_1='$st'"
        if {[string match "Running*" $sst] || [string match "Running*" $st] || \
            [string match "*Complete*" $st] || [string match "Queued*" $st]} {
            wait_on_run impl_1
            set st [get_property STATUS [get_runs impl_1]]
            if {[string match "*write_bitstream Complete*" $st]} { return 1 }
            say "impl_1 ended with status '$st'"
            return 0
        }
        reset_run impl_1
        set jobs 1
    }
    return 0
}

if {$REUSE_RUN} {
    set st [get_property STATUS [get_runs impl_1]]
    if {![string match "*write_bitstream Complete*" $st]} { error "REUSE_RUN: impl_1 status is '$st', not complete" }
    if {[get_property NEEDS_REFRESH [get_runs synth_1]] || [get_property NEEDS_REFRESH [get_runs impl_1]]} {
        error "REUSE_RUN: the run is OUT OF DATE relative to the sources/block design -- rebuild (REUSE_RUN 0)"
    }
    say "REUSE_RUN: impl_1 is complete and current -- skipping the rebuild"
    set built 1
} else {
    set built [try_project_runs $JOBS]
}

if {$built} {
    say "project runs completed"
    set wns [get_property STATS.WNS [get_runs impl_1]]
    set tns [get_property STATS.TNS [get_runs impl_1]]
    set whs [get_property STATS.WHS [get_runs impl_1]]
    set impl_dir [get_property DIRECTORY [get_runs impl_1]]
    foreach f [glob -nocomplain $impl_dir/*timing_summary_routed.rpt $impl_dir/*utilization_placed.rpt $impl_dir/*power_routed.rpt] {
        file copy -force $f $out
    }
    set bit [lindex [glob -nocomplain $impl_dir/design_1_wrapper.bit] 0]
    if {$bit eq ""} { error "no design_1_wrapper.bit in $impl_dir" }
    file copy -force $bit $out
    close_all_designs
    open_run impl_1
} else {
    say "project runs unavailable on this machine -- building IN-PROCESS (no spawn)"
    set used_inprocess 1
    set_property synth_checkpoint_mode None $bd
    generate_target all $bd
    set wrapper [get_files -quiet *design_1_wrapper.v]
    if {$wrapper eq ""} { set wrapper [make_wrapper -files $bd -top -import] }
    update_compile_order -fileset sources_1
    synth_design -top design_1_wrapper -part $PART
    opt_design
    place_design
    phys_opt_design
    route_design
    report_timing_summary -max_paths 10 -file $out/design_1_wrapper_timing_summary_routed.rpt
    report_utilization -file $out/design_1_wrapper_utilization_placed.rpt
    set wns [get_property SLACK [lindex [get_timing_paths -max_paths 1 -nworst 1 -setup] 0]]
    set whs [get_property SLACK [lindex [get_timing_paths -max_paths 1 -nworst 1 -hold]  0]]
    set tns "n/a (in-process; see timing report)"
    set bit "$out/design_1_wrapper.bit"
    write_bitstream -force $bit
}

# ---------------------------------------------------------------- timing gate
say "WNS=$wns TNS=$tns WHS=$whs"
if {$wns < 0 || $whs < 0} {
    say "TIMING FAILED -- nothing exported. Top paths are in $out/*timing_summary_routed.rpt"
    if {$used_inprocess} { close_design }
    error "WNS=$wns WHS=$whs"
}

# ---------------------------------------------------------------- reports + export
report_utilization -hierarchical -file $out/utilization_hier.rpt
report_power -file $out/power.rpt
set xsa "$out/design_1_wrapper.xsa"
write_hw_platform -fixed -include_bit -force $xsa
say "exported $xsa"
close_design

# ---------------------------------------------------------------- optional bootgen
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

# ---------------------------------------------------------------- optional: drop it straight onto the Mac
if {$MAC_DIR ne ""} {
    if {![file isdirectory $MAC_DIR]} {
        say "MAC_DIR $MAC_DIR not reachable (RDP folder redirection off?) -- copy by hand"
    } else {
        set dst "$MAC_DIR/$tag"
        file mkdir $dst
        foreach f [list $xsa $bit $out/summary.txt $out/BOOT.bin $out/design_1_wrapper_timing_summary_routed.rpt $out/power.rpt $out/utilization_hier.rpt] {
            if {[file exists $f]} { file copy -force $f $dst }
        }
        say "copied to the Mac: $dst"
    }
}
