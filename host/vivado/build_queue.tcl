# build_queue.tcl -- run several build_engine.tcl configurations back to
# back, unattended (overnight). Each entry is a Tcl script fragment that
# sets the per-run variables; build_engine.tcl consumes them. A failed
# build (timing, missing file) is logged and the queue continues.
#     source C:/Users/dhritiaravind/snn_parkour_fpga/host/vivado/build_queue.tcl
# CURRENT QUEUE (2026-09-20): the C0025 energy-vs-K sweep, build list and
# priority order from measure/k_energy_prereg_2026-09-20.md. All ED,
# N-MNIST, baked. K=4 and K=8 at R=1 and K=4 at R=8 already exist in
# host/mac/build/archive/ and are NOT rebuilt. Entry 3 (K=16 at R=8) is
# expected to be marginal on BRAM; if it fails to place, the queue carries
# on and R=4 is the fallback -- rerun that one alone with N_ENGINES 4.
# If VM time is short, the prereg says stopping after entry 3 still answers
# the question. Every one needs a correctness pass before it is metered.
#
# Edit QUEUE below to choose what runs. Results: m4_conv2/builds/<tag>/
# and the queue log next to them. NO comments inside the braces of QUEUE
# (a ";# ..." there becomes list items -- it broke the first run).
# DVS-Gesture replicated at N=4: the g1 ED engine is 21 BRAM tiles (x8 =
# 168 > 140) and the g1 dense engine 7.3k LUT / 17k FF (x8 overflows).
set QUEUE {
    {set ENGINE 1; set ED_K 16; set DENSE_P 4}
    {set ENGINE 1; set ED_K 1;  set DENSE_P 4}
    {set ENGINE 1; set ED_K 16; set DENSE_P 4; set N_ENGINES 8}
    {set ENGINE 1; set ED_K 8;  set DENSE_P 4; set N_ENGINES 8}
    {set ENGINE 1; set ED_K 2;  set DENSE_P 4}
}

set qdir "C:/Users/dhritiaravind/m4_conv2/builds"
file mkdir $qdir
set qlog [open "$qdir/queue_[clock format [clock seconds] -format %Y%m%d_%H%M].log" w]
set here [file dirname [info script]]
foreach entry $QUEUE {
    if {![string match "set *" [string trim $entry]]} { puts $qlog "SKIP non-entry: $entry"; continue }
    puts $qlog "[clock format [clock seconds] -format %H:%M:%S] START $entry"; flush $qlog
    puts "\[queue\] $entry"
    foreach v {ENGINE ED_K DENSE_P DATASET N_ENGINES STRATEGY REUSE_RUN} { catch {uplevel #0 [list unset $v]} }
    if {[catch {uplevel #0 $entry} msg]} { puts $qlog "FAILED to set variables: $msg"; continue }
    if {[catch {uplevel #0 [list source "$here/build_engine.tcl"]} msg]} {
        puts $qlog "[clock format [clock seconds] -format %H:%M:%S] FAILED: $msg"
        puts "\[queue\] FAILED: $msg"
    } else {
        puts $qlog "[clock format [clock seconds] -format %H:%M:%S] DONE"
    }
    flush $qlog
    foreach v {ENGINE ED_K DENSE_P DATASET N_ENGINES STRATEGY REUSE_RUN} { catch {uplevel #0 [list unset $v]} }
}
close $qlog
puts "\[queue\] finished; log in $qdir"
