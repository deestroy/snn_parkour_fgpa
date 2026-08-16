#!/usr/bin/env bash
# M4 Stage B check: AXIS wrapper + engine vs golden word streams.
# Usage: bash sim/run_axis_tb.sh [c1]   (c1 only for now; c2/c3 when chained)
set -eu
cd "$(dirname "$0")/.."

layer="${1:-c1}"
case "$layer" in
    c1) ci=2; hi=34; wi_=34; co=16; ho=17; wo_=17 ;;
    *) echo "only c1 wired for the axis TB so far"; exit 2 ;;
esac

python3 sim/export_conv_vectors.py --layer "$layer" > /dev/null
python3 sim/export_axis_vectors.py --layer "$layer"

in_bits=$(( ci * hi * wi_ ))
neurons=$(( co * ho * wo_ ))
wi=$(( (in_bits + 31) / 32 ))
wo=$(( (neurons + 31) / 32 ))

mkdir -p sim/work
iverilog -g2012 -o sim/work/tb_axis.vvp \
    hdl/common/lif_update.v hdl/dense/conv_layer.v hdl/dense/axis_conv.v \
    sim/tb_axis_conv.v

vvp sim/work/tb_axis.vvp \
    +in="sim/vectors/axis_${layer}_in.hex" \
    +out="sim/vectors/axis_${layer}_out.hex" \
    +nsamples=16 +wi="$wi" +wo="$wo" +seed=7 \
    | grep -E "TB_|MISMATCH" | head -8
