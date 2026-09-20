# build_queue.tcl -- run several build_engine.tcl configurations back to
# back, unattended (overnight). Each entry is a Tcl script fragment that
# sets the per-run variables; build_engine.tcl consumes them. A failed
# build (timing, missing file) is logged and the queue continues.
#     source C:/Users/dhritiaravind/snn_parkour_fpga/host/vivado/build_queue.tcl
# Edit QUEUE below to choose what runs. Results: m4_conv2/builds/<tag>/
# and the queue log next to them.
set QUEUE {
    {set ENGINE 1; set ED_K 4; set DENSE_P 4; set DATASET 1; set N_ENGINES 4}   ;# g1 ED engine = 21 BRAM tiles: x8 (168) does not fit, x4 (84+2) does
    {set ENGINE 0; set ED_K 4; set DENSE_P 4; set DATASET 1; set N_ENGINES 4}   ;# g1 dense engine = 7.3k LUT / 17k FF: x8 overflows, x4 = 29k LUT / 68k FF
    {set ENGINE 1; set ED_K 4; set DENSE_P 4; set STRATEGY Performance_Explore}
    {set ENGINE 1; set ED_K 4; set DENSE_P 4; set STRATEGY Congestion_SpreadLogic_high}
    {set ENGINE 0; set ED_K 4; set DENSE_P 4; set STRATEGY Performance_Explore}
    {set ENGINE 0; set ED_K 4; set DENSE_P 4; set STRATEGY Congestion_SpreadLogic_high}
}
set qdir "C:/Users/dhritiaravind/m4_conv2/builds"
file mkdir $qdir
set qlog [open "$qdir/queue_[clock format [clock seconds] -format %Y%m%d_%H%M].log" w]
set here [file dirname [info script]]
foreach entry $QUEUE {
    puts $qlog "[clock format [clock seconds] -format %H:%M:%S] START $entry"; flush $qlog
    puts "\[queue\] $entry"
    foreach v {ENGINE ED_K DENSE_P DATASET N_ENGINES STRATEGY REUSE_RUN} { catch {unset $v} }
    eval $entry
    if {[catch {uplevel #0 [list source "$here/build_engine.tcl"]} msg]} {
        puts $qlog "[clock format [clock seconds] -format %H:%M:%S] FAILED: $msg"
        puts "\[queue\] FAILED: $msg"
    } else {
        puts $qlog "[clock format [clock seconds] -format %H:%M:%S] DONE"
    }
    flush $qlog
    foreach v {ENGINE ED_K DENSE_P DATASET N_ENGINES STRATEGY REUSE_RUN} { catch {unset $v} }
}
close $qlog
puts "\[queue\] finished; log in $qdir"
