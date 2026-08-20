#!/usr/bin/env bash
# Check: event-driven FC layer vs golden fc traces (D0023). Env: K (default 4)
set -eu
cd "$(dirname "$0")/.."
K="${K:-4}"
python3 sim/export_fc_vectors.py > /dev/null
mkdir -p sim/work
iverilog -g2012 -o sim/work/tb_ed_fc.vvp -Ptb_ed_fc.K_BANKS=$K \
    hdl/common/lif_update.v hdl/eventdriven/ed_fc_layer.v sim/tb_ed_fc.v
vvp sim/work/tb_ed_fc.vvp +spk=sim/vectors/ed_fc_spk.txt \
    +s=sim/vectors/fc_s.bin +v=sim/vectors/fc_v.hex +nsamples=16 \
    | grep -E "TB_|MISMATCH" | head -8
