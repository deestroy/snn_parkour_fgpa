#!/usr/bin/env bash
# M4 Stage B, one command: program the conv-engine bitstream + server,
# then run the golden comparison client. Expects in host/mac/build/:
#   design_1_wrapper.bit  design_1_wrapper.xsa  conv_server.elf
# Usage: bash host/mac/stage_b.sh
set -eu
here="$(cd "$(dirname "$0")" && pwd)"; cd "$here/../.."
b=host/mac/build
for f in $b/design_1_wrapper.bit $b/design_1_wrapper.xsa $b/conv_server.elf; do
    [ -f "$f" ] || { echo "missing $f"; exit 1; }
done
# integrity: RDP/Drive copies have delivered all-zero files before
for f in $b/design_1_wrapper.bit $b/conv_server.elf; do
    nz=$(tr -d '\000' < "$f" | wc -c | tr -d ' ')
    [ "$nz" -gt 1000 ] || { echo "$f looks empty (all zeros) - re-copy it"; exit 1; }
done
unzip -o -j $b/design_1_wrapper.xsa ps7_init.tcl -d host/mac/ > /dev/null
python3 -c "import struct,sys; d=open('$b/conv_server.elf','rb').read(); e=struct.unpack('<I',d[0x18:0x1c])[0]; print('conv_server.elf entry 0x%08x (%s)'%(e,'OCM' if e<0x30000 else 'NOT OCM - relink lscript.ld'))"
pkill -f uart_capture 2>/dev/null || true
echo "== programming =="
bash host/mac/program.sh $b/design_1_wrapper.bit $b/conv_server.elf host/mac/ps7_init.tcl 2>&1 | grep -E "^==|Error" || true
sleep 2
echo "== client =="
python3 host/uart_client.py
