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
#   optional before `source`:  set N_ENGINES 8   (C0003 replication; tag gets _x8)
#                              set REUSE_RUN 1   (re-export a finished run, no rebuild)
# or from a Vivado Tcl shell / batch:
#     vivado -mode batch -source build_engine.tcl -tclargs ENGINE ED_K DENSE_P
#     e.g.  vivado -mode batch -source build_engine.tcl -tclargs 0 4 8    (dense P=8)
#
# While it runs the Tcl console is busy (wait_on_run) -- 5-15 minutes.
# Do not click Generate Bitstream or touch the block design meanwhile.

# ---------------------------------------------------------------- settings
# Project: the clean m4_conv2 (docs/vivado_new_project.md). To build the
# old m4_conv once more:  set PROJECT C:/Users/dhritiaravind/m4_conv/m4_conv.xpr
# before `source` (consumed per run).
if {[info exists PROJECT]} { set PROJ $PROJECT; unset PROJECT } else { set PROJ "C:/Users/dhritiaravind/m4_conv2/m4_conv2.xpr" }
set BD_CELL   "axis_conv_top_0"
set JOBS      2   ;# this VM's launcher is flaky with many parallel jobs
# Boot-image inputs. Each is a list of candidate paths; the first that
# exists is used, and its size must match the known-good file (the ELFs
# inside the BOOT.bin validated on silicon 2026-09-17: fsbl.elf 607,080
# bytes, conv_server.elf build 4 389,840 bytes). Update the size when the
# app is rebuilt. Set FSBL_ELF {} to skip bootgen and use Vitis by hand.
set FSBL_ELF {
    C:/Users/dhritiaravind/vitis_m4_loopback_zed/zed_board/export/zed_board/sw/zed_board/boot/fsbl.elf
    C:/Users/dhritiaravind/vitis_m4_loopback_zed/zed_board/zynq_fsbl/build/fsbl.elf
    C:/Users/dhritiaravind/vitis_m4_loopback_zed/zed_board/zynq_fsbl/fsbl.elf
}
set FSBL_SIZE 607080
set APP_ELF  {
    C:/Users/dhritiaravind/vitis_m4_loopback_zed/conv_server/build/conv_server.elf
}
set APP_SIZE 389864       ;# build 5 (DATASET=0), 2026-09-18
# DATASET=1 bitstreams need the server built with -DDATASET=1 (build 5,
# 1,024/2,048-word frames). Keep it as a separate file so the N-MNIST
# builds keep their own. Size 0 = not yet known: accept any, print it.
set APP_ELF_G1 {
    C:/Users/dhritiaravind/vitis_m4_loopback_zed/conv_server/build/conv_server_g1.elf
}
set APP_SIZE_G1 389864    ;# build 5 -DDATASET=1, 2026-09-18 (same size as DATASET=0: PING word 2 tells them apart)
# bootgen ships with both Vivado and Vitis; first that exists wins.
set BOOTGEN {
    C:/Xilinx/Vivado/2024.1/bin/bootgen.bat
    C:/Xilinx/Vitis/2024.1/bin/bootgen.bat
    C:/AMD/Vivado/2024.1/bin/bootgen.bat
    C:/AMD/Vitis/2024.1/bin/bootgen.bat
}
# Mac folder redirected into this RDP session (Microsoft Remote Desktop ->
# edit PC -> Folders). It shows up in the VM as \\tsclient\<folder name>.
# Leave "" to skip; then copy builds/<tag>/ by hand.
set MAC_DIR   "//tsclient/Users/dhritiaravind/git_projects/snn_parkour_fpga/host/mac/build"

# parameters: from -tclargs if given, else from variables set before `source`
if {[info exists argv] && [llength $argv] >= 3} {
    lassign $argv ENGINE ED_K DENSE_P
}
foreach v {ENGINE ED_K DENSE_P} {
    if {![info exists $v]} { error "set $v before sourcing (e.g. set ENGINE 1; set ED_K 8; set DENSE_P 4)" }
}
set BAKED 1
# DATASET (C0012): 0 = N-MNIST C1 (default), 1 = DVS-Gesture C1. Set before `source`.
if {[info exists DATASET]} { set DS $DATASET; unset DATASET } else { set DS 0 }
# N_ENGINES (C0003 replication for the meter): set before `source`, default 1.
# Consumed and unset like REUSE_RUN so it cannot leak into the next build.
if {[info exists N_ENGINES]} { set NENG $N_ENGINES; unset N_ENGINES } else { set NENG 1 }
# REUSE_RUN 1: do NOT rebuild -- take the already-completed impl_1 (must be
# "write_bitstream Complete" and not out of date) and only do the checks,
# reports and export.  For re-exporting after a post-build script error.
# The flag is consumed here and UNSET so it cannot leak into the next
# `source` in the same Tcl console (it did: a dense P=8 build inherited
# REUSE_RUN=1 from the ED K=8 re-export and refused on the read-back).
if {[info exists REUSE_RUN]} { set REUSE [expr {$REUSE_RUN ? 1 : 0}]; unset REUSE_RUN } else { set REUSE 0 }
if {$ENGINE} { set tag "ed_k${ED_K}" } else { set tag "dense_p${DENSE_P}" }
if {$DS == 1} { set tag "${tag}_dvsg" }
if {$NENG > 1} { append tag "_x${NENG}" }
set tag "${tag}_[clock format [clock seconds] -format %Y%m%d_%H%M]"
set proj_dir [file dirname $PROJ]
set out "$proj_dir/builds/$tag"
file mkdir $out
proc say {msg} { puts "\[build_engine\] $msg" }
say "configuration: ENGINE=$ENGINE ED_K=$ED_K DENSE_P=$DENSE_P BAKED=$BAKED N_ENGINES=$NENG DATASET=$DS REUSE_RUN=$REUSE -> $out"

# ---------------------------------------------------------------- project
# Open the target project -- and refuse to build whichever OTHER project
# happens to be open in the GUI (m4_conv vs m4_conv2 both exist).
if {[catch {set cur_dir [get_property DIRECTORY [current_project]]}]} {
    open_project $PROJ
} elseif {[file normalize $cur_dir] ne [file normalize [file dirname $PROJ]]} {
    error "project [current_project] is open but the script targets $PROJ -- run close_project first, or set PROJECT to the open one"
}
# deterministic runs: the auto-incremental reference checkpoint made two
# implementations of the same netlist differ by 300k config bytes
set_property AUTO_INCREMENTAL_CHECKPOINT 0 [get_runs synth_1]
set_property AUTO_INCREMENTAL_CHECKPOINT 0 [get_runs impl_1]

# ---------------------------------------------------------------- block design
set bd [get_files -quiet design_1.bd]
if {$bd eq ""} { error "design_1.bd not in project" }
open_bd_design $bd
# The top must be the block design's wrapper. A fresh project (m4_conv2,
# 2026-09-18) implemented axis_conv_top on its own -- no PS, no clock,
# "WNS inf", a bitstream of nothing. Create the wrapper if missing and set
# it as top every run.
set wrapper [get_files -quiet *design_1_wrapper.v]
if {$wrapper eq ""} {
    say "  no design_1_wrapper.v -- creating the HDL wrapper"
    set wrapper [make_wrapper -files $bd -top -import]
}
if {[get_property TOP [current_fileset]] ne "design_1_wrapper"} {
    say "  top was [get_property TOP [current_fileset]] -- setting design_1_wrapper as top"
    set_property top design_1_wrapper [current_fileset]
    update_compile_order -fileset sources_1
}
set cell [get_bd_cells $BD_CELL]
# Global synthesis: no out-of-context child run for the RTL block. With the
# default (Hierarchical) mode Vivado spawns a separate synthesis for
# design_1_axis_conv_top_0_0 and the main run reads its checkpoint; on this
# VM that child silently never ran (2026-09-17, dense P=8: "module
# 'design_1_axis_conv_top_0_0' not found"). One run, one process.
if {[get_property synth_checkpoint_mode $bd] ne "None"} {
    say "  synth_checkpoint_mode -> None (was [get_property synth_checkpoint_mode $bd])"
    set_property synth_checkpoint_mode None $bd
    set force_regen 1
} else { set force_regen 0 }
if {!$REUSE} {
    set_property -dict [list \
        CONFIG.ENGINE        $ENGINE \
        CONFIG.ED_K          $ED_K \
        CONFIG.DENSE_P       $DENSE_P \
        CONFIG.BAKED_WEIGHTS $BAKED \
        CONFIG.N_ENGINES     $NENG \
        CONFIG.DATASET       $DS ] $cell
}
# read back -- this is the check that caught the ENGINE=0 stale-customisation build
foreach {p want} [list ENGINE $ENGINE ED_K $ED_K DENSE_P $DENSE_P BAKED_WEIGHTS $BAKED N_ENGINES $NENG DATASET $DS] {
    set got [get_property CONFIG.$p $cell]
    if {$got != $want} { error "parameter $p reads back $got, wanted $want" }
    say "  CONFIG.$p = $got"
}

# Processing-system sanity: the ZedBoard preset and the three settings it
# resets. A fresh project (2026-09-18) built with Vivado's default DDR part
# (MT41J128M8) -- the configuration that silently lost DDR data in August.
# Checked before any synthesis time is spent.
set ps [get_bd_cells processing_system7_0]
foreach {prop want} {
    CONFIG.PCW_UIPARAM_DDR_PARTNO   "MT41J128M16 HA-15E"
    CONFIG.PCW_USE_S_AXI_HP0        1
    CONFIG.PCW_UART1_PERIPHERAL_ENABLE 1
    CONFIG.PCW_SD0_PERIPHERAL_ENABLE 1
    CONFIG.PCW_QSPI_PERIPHERAL_ENABLE 1
} {
    set got [get_property $prop $ps]
    if {$got ne $want} { error "PS $prop = '$got', expected '$want' -- apply Presets > ZedBoard on the ZYNQ7 block, then re-tick S AXI HP0 and set FCLK_CLK0 = 100 MHz" }
}
set fclk [get_property CONFIG.PCW_FPGA0_PERIPHERAL_FREQMHZ $ps]
if {abs($fclk - 100.0) > 0.01} { error "PS FCLK_CLK0 = $fclk MHz, expected 100 -- Clock Configuration > PL Fabric Clocks" }
say "  PS: ZedBoard DDR part, HP0, UART1, SD0, QSPI, FCLK0=100 MHz -- ok"

# DMA address map: both data masters must be mapped, nothing excluded
foreach sp {Data_MM2S Data_S2MM} {
    set segs [get_bd_addr_segs -quiet -of_objects [get_bd_addr_spaces axi_dma_0/$sp]]
    if {[llength $segs] == 0} {
        if {$REUSE} { error "$sp unassigned -- the completed run cannot be reused" }
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

if {$REUSE} {
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
if {$force_regen} { reset_target all $bd }
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
    foreach r [get_runs -quiet *axis_conv_top*synth*] { reset_run $r }   ;# none once checkpoint mode is None
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

if {$REUSE} {
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
if {![string is double -strict $wns] || [string match -nocase "*inf*" $wns] || $wns > 1000} {
    if {$used_inprocess} { close_design }
    error "WNS=$wns means NO timing constraints reached the run (wrong top, or the block design's clock is missing) -- nothing exported"
}
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

# ---------------------------------------------------------------- bootgen
# Picks the first existing candidate and insists on the known size, so a
# stale or wrong ELF (or the wrong bitstream -- $bit is this run's) can
# never reach the card unnoticed. This replaced the Vitis dialog after a
# BOOT.bin was hand-built from the previous build's bitstream (2026-09-17).
proc pick_file {cands want_size what} {
    foreach c $cands {
        if {[file exists $c]} {
            set sz [file size $c]
            if {$want_size > 0 && $sz != $want_size} {
                error "$what at $c is $sz bytes, expected $want_size -- wrong or stale file; fix the path or update the size in the settings"
            }
            return $c
        }
    }
    return ""
}
set fsbl [pick_file $FSBL_ELF $FSBL_SIZE "FSBL"]
if {$DS == 1} {
    set app [pick_file $APP_ELF_G1 $APP_SIZE_G1 "conv_server_g1.elf (DATASET=1 server)"]
    if {$app ne ""} { say "bootgen: DATASET=1 server, [file size $app] bytes (record this as APP_SIZE_G1)" }
} else {
    set app [pick_file $APP_ELF  $APP_SIZE  "conv_server.elf"]
}
set bg   [pick_file $BOOTGEN  0          "bootgen"]
if {$fsbl ne "" && $app ne "" && $bg ne ""} {
    say "bootgen: FSBL $fsbl"
    say "bootgen: APP  $app"
    say "bootgen: BIT  $bit"
    set bif [open $out/boot.bif w]
    puts $bif "the_ROM_image:\n{\n  \[bootloader\] $fsbl\n  $bit\n  $app\n}"
    close $bif
    if {[catch {exec $bg -arch zynq -image $out/boot.bif -o $out/BOOT.bin -w on} msg]} {
        say "bootgen FAILED: $msg -- Create Boot Image in Vitis with $bit"
    } else {
        say "BOOT.bin written: $out/BOOT.bin ([file size $out/BOOT.bin] bytes)"
    }
} else {
    say "bootgen skipped (missing: [expr {$fsbl eq "" ? "FSBL " : ""}][expr {$app eq "" ? "APP " : ""}][expr {$bg eq "" ? "bootgen" : ""}]) -- Create Boot Image in Vitis with $bit"
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
# Through cmd.exe: Vivado's Tcl sees \\tsclient\Users but not the folders
# under it (file isdirectory -> 0, glob -> empty; 2026-09-18), while
# cmd's copy handles the redirected share fine.
if {$MAC_DIR ne ""} {
    set mac_native [file nativename $MAC_DIR]
    if {[catch {exec cmd /c dir /b $mac_native} r]} {
        say "MAC_DIR $mac_native not reachable from this Vivado ($r) -- copy $out by hand"
    } else {
        set dst_native "$mac_native\\$tag"
        catch {exec cmd /c mkdir $dst_native}
        set n 0
        foreach f [list $xsa $bit $out/summary.txt $out/BOOT.bin $out/design_1_wrapper_timing_summary_routed.rpt $out/power.rpt $out/utilization_hier.rpt] {
            if {[file exists $f]} {
                if {[catch {exec cmd /c copy /Y [file nativename $f] $dst_native} msg]} {
                    say "copy of [file tail $f] failed: $msg"
                } else { incr n }
            }
        }
        say "copied $n files to the Mac: $dst_native"
    }
}
