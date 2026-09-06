#!/usr/bin/env bash
# Synthesis-safety lint: static guards for constructs that simulate fine in
# iverilog but do NOT survive Vivado synthesis (both found on silicon,
# 2026-09-06, dense P=4 returning all zeros while bit-identical in sim):
#
#   1. two-stage initialization -- an initial block that reads another
#      array's initial contents (typically ordered with a "#0;"). Vivado
#      does not honour that ordering; the dependent ROM came out all-zero.
#      Rule: every ROM is initialized in ONE step ($readmemh or inlined),
#      and the hardware reads THAT array directly.
#   2. (ADVISORY) cross-scope hierarchical references into generate
#      blocks (g_bank[3].obits[...]) from outside the block. NOT banned:
#      axis_conv_top's g_rep[0].rep_* references are on silicon in the
#      validated ED build, so Vivado 2024.1 does resolve them. Listed so a
#      reviewer sees every one; prefer a flattened module-level wire.
#
# Scope: the files that reach synthesis (hdl/), excluding sim/.
set -u
cd "$(dirname "$0")/.."
fail=0
files=$(find hdl -name '*.v')

# 1. "#0;" anywhere in synthesized RTL is only ever an init-ordering hack
hits=$(grep -n '#0;' $files || true)
if [ -n "$hits" ]; then
    echo "LINT FAIL: #0 ordering hack in synthesized RTL (two-stage init):"
    echo "$hits"; fail=1
fi

# 2. hierarchical reference through a generate-block instance name:
#    identifier[...].identifier  -- e.g. g_bank[LANE].obits[LOCAL]
hits=$(grep -nE '\b[A-Za-z_][A-Za-z0-9_]*\[[^]]+\]\.[A-Za-z_]' $files || true)
if [ -n "$hits" ]; then
    echo "advisory: cross-scope hierarchical references (silicon-proven construct, listed for review):"
    echo "$hits"
fi

if [ $fail -eq 0 ]; then
    echo "SYNTH-SAFETY LINT PASS ($(echo $files | wc -w | tr -d ' ') files: no two-stage init)"
fi
exit $fail
