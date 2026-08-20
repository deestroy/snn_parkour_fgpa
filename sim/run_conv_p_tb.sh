#!/usr/bin/env bash
# C0029 check: P-wide dense engine vs golden traces. Env: P (default 4), THRESH, layer arg.
set -eu
cd "$(dirname "$0")/.."
layer="${1:-c1}"; P="${P:-4}"; THRESH="${THRESH:-64}"
case "$layer" in
    c1) ci=2;  hi=34; wi=34; co=16; ho=17; wo=17; ns=16 ;;
    c2) ci=16; hi=17; wi=17; co=32; ho=9;  wo=9 ; ns=16 ;;
    c3) ci=32; hi=9;  wi=9;  co=64; ho=5;  wo=5 ; ns=16 ;;
    r1) ci=2;  hi=64; wi=64; co=16; ho=32; wo=32; ns=8 ;;
    *) echo "unknown layer"; exit 2 ;;
esac
if [ "$layer" = r1 ]; then
    if [ "${R1_REAL:-0}" = 1 ]; then python3 sim/export_fpga_student_vectors.py > /dev/null
    else python3 sim/export_robot_vectors.py > /dev/null; fi
else
    python3 sim/export_conv_vectors.py --layer "$layer" > /dev/null
fi
mkdir -p sim/work
iverilog -g2012 -o "sim/work/tb_conv_p_${layer}.vvp" \
    -Ptb_conv_p.C_IN=$ci -Ptb_conv_p.H_IN=$hi -Ptb_conv_p.W_IN=$wi \
    -Ptb_conv_p.C_OUT=$co -Ptb_conv_p.H_OUT=$ho -Ptb_conv_p.W_OUT=$wo \
    -Ptb_conv_p.P=$P -Ptb_conv_p.THRESHOLD=$THRESH \
    -Ptb_conv_p.WEIGHT_FILE="\"sim/vectors/conv_${layer}_w.hex\"" \
    hdl/common/lif_update.v hdl/dense/conv_layer_p.v sim/tb_conv_p.v
vvp "sim/work/tb_conv_p_${layer}.vvp" \
    +in="sim/vectors/conv_${layer}_in.bin" +s="sim/vectors/conv_${layer}_s.bin" \
    +v="sim/vectors/conv_${layer}_v.hex" +nsamples=$ns | grep -E "TB_|MISMATCH" | head -8
