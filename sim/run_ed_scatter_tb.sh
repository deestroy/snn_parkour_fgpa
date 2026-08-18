#!/usr/bin/env bash
# M6 step 2 check: scatter unit vs the Python engine's post-scatter I dump.
set -eu
cd "$(dirname "$0")/.."
layer="${1:-c1}"
case "$layer" in
    c1) ci=2;  hi=34; wi=34; co=16; ho=17; wo=17 ;;
    c2) ci=16; hi=17; wi=17; co=32; ho=9;  wo=9  ;;
    c3) ci=32; hi=9;  wi=9;  co=64; ho=5;  wo=5  ;;
    *) echo "unknown layer"; exit 2 ;;
esac
python3 sim/export_ed_vectors.py --layer "$layer" > /dev/null
mkdir -p sim/work
iverilog -g2012 -o "sim/work/tb_eds_${layer}.vvp" \
    -Ptb_ed_scatter.C_IN=$ci -Ptb_ed_scatter.H_IN=$hi -Ptb_ed_scatter.W_IN=$wi \
    -Ptb_ed_scatter.C_OUT=$co -Ptb_ed_scatter.H_OUT=$ho -Ptb_ed_scatter.W_OUT=$wo \
    -Ptb_ed_scatter.WT_FILE="\"sim/vectors/ed_${layer}_wt.hex\"" \
    hdl/eventdriven/ed_scatter.v sim/tb_ed_scatter.v
vvp "sim/work/tb_eds_${layer}.vvp" +spk="sim/vectors/ed_${layer}_spk.txt" \
    +i="sim/vectors/ed_${layer}_i.hex" +nsamples=16 | grep -E "TB_|MISMATCH" | head -8
