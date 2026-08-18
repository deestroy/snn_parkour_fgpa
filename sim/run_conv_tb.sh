#!/usr/bin/env bash
# M3 check: the dense conv engine vs golden traces.
# Usage: bash sim/run_conv_tb.sh [c1|c2|c3 ...]  (default: c1)
# (plain POSIX-ish bash: macOS ships bash 3.2, no associative arrays)
set -eu
cd "$(dirname "$0")/.."

if [ "$#" -eq 0 ]; then set -- c1; fi
mkdir -p sim/work
overall=0

for layer in "$@"; do
    case "$layer" in
        c1) ci=2;  hi=34; wi=34; co=16; ho=17; wo=17 ;;
        c2) ci=16; hi=17; wi=17; co=32; ho=9;  wo=9  ;;
        c3) ci=32; hi=9;  wi=9;  co=64; ho=5;  wo=5  ;;
        *) echo "unknown layer $layer"; exit 2 ;;
    esac
    python3 sim/export_conv_vectors.py --layer "$layer" > /dev/null

    iverilog -g2012 -I hdl/dense -o "sim/work/tb_conv_${layer}.vvp" \
        -Ptb_conv_layer.C_IN="$ci"  -Ptb_conv_layer.H_IN="$hi"  -Ptb_conv_layer.W_IN="$wi" \
        -Ptb_conv_layer.C_OUT="$co" -Ptb_conv_layer.H_OUT="$ho" -Ptb_conv_layer.W_OUT="$wo" \
        -Ptb_conv_layer.WEIGHT_FILE="\"sim/vectors/conv_${layer}_w.hex\"" \
        hdl/common/lif_update.v hdl/dense/conv_layer.v sim/tb_conv_layer.v

    out=$(vvp "sim/work/tb_conv_${layer}.vvp" \
        +in="sim/vectors/conv_${layer}_in.bin" \
        +s="sim/vectors/conv_${layer}_s.bin" \
        +v="sim/vectors/conv_${layer}_v.hex" \
        +nsamples=16 | grep -E "TB_|MISMATCH" | head -8)
    echo "[$layer] $out"
    echo "$out" | grep -q TB_PASS || overall=1
done

[ "$overall" -eq 0 ] && echo "DENSE ENGINE PASSES on: $*" \
                     || echo "FAILURE: engine does not match the golden model."
exit "$overall"
