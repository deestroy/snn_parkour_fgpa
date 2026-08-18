#!/usr/bin/env bash
# Run every check in the repo. One command, one verdict.
# Usage: bash check_all.sh          (~3 min on the Mac; board not required)
set -u
cd "$(dirname "$0")"
pass=0; fail=0
run() {   # run <name> <cmd...> ; PASS if the command's output contains PASS
    local name="$1"; shift
    local out; out=$("$@" 2>&1)
    if echo "$out" | grep -qE "PASS|passes|bit-identical|0 mismatches"; then
        printf "  %-42s ok\n" "$name"; pass=$((pass+1))
    else
        printf "  %-42s FAIL\n" "$name"; echo "$out" | tail -5 | sed 's/^/      /'; fail=$((fail+1))
    fi
}
echo "== snn_parkour_fpga: full check =="
run "M0 LIF demo (golden vs snnTorch)"        python3 train/00_lif_demo.py
run "M0 model check (shapes/budget/reset)"    python3 train/02_model_check.py
run "M2 LIF neuron HDL"                       bash sim/run_lif_tb.sh
run "M3 dense conv c1/c2/c3"                  bash sim/run_conv_tb.sh c1 c2 c3
run "M3 dense FC"                             bash sim/run_fc_tb.sh
run "M4 AXIS wrapper (hostile handshake)"     bash sim/run_axis_tb.sh c1
run "M6 harness (dense engine as DUT)"        bash sim/run_ed_tb.sh c1
run "M6 python engine K=1/K=4"                python3 -c "
import sys; sys.path.insert(0,'.')
from golden.eventdriven import verify_event_driven as v
r1=v('c1',k=1); r4=v('c1',k=4)
print('%d+%d checks, %d mismatches' % (r1['checked'], r4['checked'], r1['mismatches']+r4['mismatches']))"
run "Stage B host side vs golden mock"        python3 host/mock_server.py --selftest
run "M5 protocol vs mock meter"               python3 measure/protocol.py --mock
run "RTL lint (verilator -Wall)"              bash -c 'verilator --lint-only -Wall -Wno-DECLFILENAME -Wno-UNUSEDPARAM -Wno-UNUSEDSIGNAL --top-module axis_conv_top hdl/common/lif_update.v hdl/dense/conv_layer.v hdl/dense/axis_conv.v hdl/dense/axis_conv_top.v && echo LINT PASS'
echo "== $pass passed, $fail failed =="
[ "$fail" -eq 0 ]
