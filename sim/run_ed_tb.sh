#!/usr/bin/env bash
# M6 harness check: the event-driven interface testbench, DUT selectable.
# Usage: bash sim/run_ed_tb.sh [c1|c2|c3] [dut_module=ed_iface_shim]
set -eu
cd "$(dirname "$0")/.."
layer="${1:-c1}"; dut="${2:-ed_iface_shim}"
K="${K:-1}"          # banks: K=1 (default) or K=4
case "$layer" in
    c1) ci=2;  hi=34; wi=34; co=16; ho=17; wo=17 ;;
    c2) ci=16; hi=17; wi=17; co=32; ho=9;  wo=9  ;;
    c3) ci=32; hi=9;  wi=9;  co=64; ho=5;  wo=5  ;;
    *) echo "unknown layer"; exit 2 ;;
esac
python3 sim/export_conv_vectors.py --layer "$layer" > /dev/null   # dense weight hex (shim)
python3 sim/export_ed_vectors.py --layer "$layer" > /dev/null     # address lists + expected + W_T
mkdir -p sim/work
srcs="hdl/common/lif_update.v hdl/dense/conv_layer.v hdl/eventdriven/ed_iface_shim.v hdl/eventdriven/ed_scatter.v"
[ -f hdl/eventdriven/ed_conv_layer.v ] && srcs="$srcs hdl/eventdriven/ed_conv_layer.v"
extra=""; [ "$dut" = ed_conv_layer ] && extra="-DED_HAS_WT"
iverilog -g2012 -I hdl/dense -DED_DUT="$dut" $extra -o "sim/work/tb_ed_${layer}.vvp" \
    -Ptb_ed_conv.C_IN=$ci -Ptb_ed_conv.H_IN=$hi -Ptb_ed_conv.W_IN=$wi \
    -Ptb_ed_conv.C_OUT=$co -Ptb_ed_conv.H_OUT=$ho -Ptb_ed_conv.W_OUT=$wo \
    -Ptb_ed_conv.WEIGHT_FILE="\"sim/vectors/conv_${layer}_w.hex\"" \
    -Ptb_ed_conv.K_BANKS=$K -Ptb_ed_conv.WT_FILE="\"sim/vectors/ed_${layer}_wt.hex\"" \
    $srcs sim/tb_ed_conv.v
vvp "sim/work/tb_ed_${layer}.vvp" +spk="sim/vectors/ed_${layer}_spk.txt" \
    +s="sim/vectors/ed_${layer}_s.bin" +v="sim/vectors/ed_${layer}_v.hex" +nsamples=16 \
    | grep -E "TB_|MISMATCH" | head -8
