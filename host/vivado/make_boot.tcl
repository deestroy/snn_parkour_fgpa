# make_boot.tcl -- (re)make BOOT.bin for an existing build folder without
# rebuilding anything. From the Vivado Tcl console:
#     set BUILD C:/Users/dhritiaravind/m4_conv2/builds/<tag>; set DATASET <0|1>
#     source C:/Users/dhritiaravind/snn_parkour_fpga/host/vivado/make_boot.tcl
# Uses the same FSBL / server / bootgen candidates and size checks as
# build_engine.tcl (kept in one place: this file is sourced by it too).
foreach v {BUILD DATASET} { if {![info exists $v]} { error "set $v before sourcing" } }
set FSBL_ELF {
    C:/Users/dhritiaravind/vitis_m4_loopback_zed/zed_board/zynq_fsbl/build/fsbl.elf
    C:/Users/dhritiaravind/vitis_m4_loopback_zed/zed_board/export/zed_board/sw/zed_board/boot/fsbl.elf
}
set FSBL_SIZE 607080
set APP_ELF    { C:/Users/dhritiaravind/vitis_m4_loopback_zed/conv_server/build/conv_server.elf }
set APP_SIZE   389864                 ;# build 5, DATASET=0 (2026-09-18)
set APP_ELF_G1 { C:/Users/dhritiaravind/vitis_m4_loopback_zed/conv_server_g1/build/conv_server_g1.elf }
set APP_SIZE_G1 0                     ;# separate component (2026-09-19); fill in once known
set BOOTGEN {
    C:/Xilinx/Vivado/2024.1/bin/bootgen.bat
    C:/Xilinx/Vitis/2024.1/bin/bootgen.bat
}
proc mb_pick {cands want_size what} {
    foreach c $cands {
        if {[file exists $c]} {
            set sz [file size $c]
            if {$want_size > 0 && $sz != $want_size} { error "$what at $c is $sz bytes, expected $want_size -- wrong or stale file" }
            return $c
        }
    }
    error "$what not found (looked at: $cands)"
}
set mb_fsbl [mb_pick $FSBL_ELF $FSBL_SIZE FSBL]
set mb_app  [expr {$DATASET == 1 ? [mb_pick $APP_ELF_G1 $APP_SIZE_G1 "conv_server_g1.elf (DATASET=1 component)"] : [mb_pick $APP_ELF $APP_SIZE conv_server.elf]}]
set mb_bg   [mb_pick $BOOTGEN 0 bootgen]
set mb_bit  "$BUILD/design_1_wrapper.bit"
if {![file exists $mb_bit]} { error "no design_1_wrapper.bit in $BUILD" }
puts "\[make_boot\] FSBL $mb_fsbl"
puts "\[make_boot\] APP  $mb_app ([file size $mb_app] bytes, DATASET=$DATASET)"
puts "\[make_boot\] BIT  $mb_bit"
set bif [open $BUILD/boot.bif w]
puts $bif "the_ROM_image:\n{\n  \[bootloader\] $mb_fsbl\n  $mb_bit\n  $mb_app\n}"
close $bif
exec $mb_bg -arch zynq -image $BUILD/boot.bif -o $BUILD/BOOT.bin -w on
puts "\[make_boot\] BOOT.bin written: $BUILD/BOOT.bin ([file size $BUILD/BOOT.bin] bytes)"
unset BUILD
