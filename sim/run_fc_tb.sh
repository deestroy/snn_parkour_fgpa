#!/usr/bin/env bash
# Check: FC engine (pool folded in) vs golden fc traces.
set -eu
cd "$(dirname "$0")/.."

python3 sim/export_fc_vectors.py > /dev/null
mkdir -p sim/work

iverilog -g2012 -o sim/work/tb_fc.vvp \
    hdl/common/lif_update.v hdl/dense/fc_layer.v sim/tb_fc_layer.v

vvp sim/work/tb_fc.vvp \
    +in=sim/vectors/fc_in.bin +s=sim/vectors/fc_s.bin \
    +v=sim/vectors/fc_v.hex +nsamples=16 \
    | grep -E "TB_|MISMATCH" | head -8
