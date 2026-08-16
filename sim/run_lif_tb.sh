#!/usr/bin/env bash
# M2 check: the Verilog LIF neuron vs the golden model, all four layers.
# Usage: bash sim/run_lif_tb.sh
set -euo pipefail
cd "$(dirname "$0")/.."

python3 sim/export_lif_vectors.py
mkdir -p sim/work

overall=0
for layer in c1 c2 c3 fc; do
    thr=64
    [ "$layer" = fc ] && thr=256
    vec="sim/vectors/lif_${layer}.hex"
    nvecs=$(( $(wc -l < "$vec") / 4 ))

    iverilog -g2012 -o "sim/work/tb_${layer}.vvp" \
        -Ptb_lif_neuron.THRESHOLD="$thr" \
        hdl/common/lif_update.v hdl/common/lif_neuron.v sim/tb_lif_neuron.v

    out=$(vvp "sim/work/tb_${layer}.vvp" +vec="$vec" +nvecs="$nvecs")
    echo "[$layer] $out"
    echo "$out" | grep -q TB_PASS || overall=1
done

if [ "$overall" -eq 0 ]; then
    echo "ALL LAYERS PASS: HDL neuron is bit-identical to the golden model."
else
    echo "FAILURE: at least one layer mismatched. The HDL is wrong until this passes."
fi
exit "$overall"
