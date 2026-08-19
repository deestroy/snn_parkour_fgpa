#!/usr/bin/env bash
# M4 Stage B check: AXIS wrapper + engine vs golden word streams.
# Usage: bash sim/run_axis_tb.sh [c1]   (c1 only for now; c2/c3 when chained)
set -eu
cd "$(dirname "$0")/.."

layer="${1:-c1}"
ENGINE="${ENGINE:-0}"   # 0 dense, 1 event-driven
K="${K:-1}"
NOGAP="${NOGAP:-0}"     # 1: no gaps/backpressure (latency measurement)
CYCLES="${CYCLES:-}"    # optional: write per-sample cycle counts to this file
case "$layer" in
    c1) ci=2; hi=34; wi_=34; co=16; ho=17; wo_=17 ;;
    *) echo "only c1 wired for the axis TB so far"; exit 2 ;;
esac

python3 sim/export_conv_vectors.py --layer "$layer" > /dev/null
python3 sim/export_ed_vectors.py --layer "$layer" > /dev/null
python3 sim/export_axis_vectors.py --layer "$layer"

in_bits=$(( ci * hi * wi_ ))
neurons=$(( co * ho * wo_ ))
wi=$(( (in_bits + 31) / 32 ))
wo=$(( (neurons + 31) / 32 ))

mkdir -p sim/work
iverilog -g2012 -I hdl/dense -o sim/work/tb_axis.vvp \
    -Ptb_axis_conv.ENGINE=$ENGINE -Ptb_axis_conv.ED_K=$K \
    hdl/common/lif_update.v hdl/dense/conv_layer.v hdl/dense/conv_layer_c1.v \
    hdl/eventdriven/ed_scatter.v hdl/eventdriven/ed_scatter_c1.v hdl/eventdriven/ed_conv_layer.v \
    hdl/dense/axis_conv.v hdl/dense/axis_conv_top.v \
    sim/tb_axis_conv.v

vvp sim/work/tb_axis.vvp \
    +in="sim/vectors/axis_${layer}_in.hex" \
    +out="sim/vectors/axis_${layer}_out.hex" \
    +nsamples=16 +wi="$wi" +wo="$wo" +seed=7 +nogap=$NOGAP ${CYCLES:++cycles=$CYCLES} \
    | grep -E "TB_|MISMATCH" | head -8
