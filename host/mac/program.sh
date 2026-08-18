#!/usr/bin/env bash
# Program the ZedBoard from the Mac over its onboard Digilent JTAG, using
# OpenOCD -- no Vitis on this machine. Loads the bitstream into the fabric,
# initialises the processing system, loads the bare-metal ELF, runs it.
#
# Usage: bash host/mac/program.sh <design.bit> <app.elf> [ps7_init.tcl]
#
# Inputs, all produced on the Windows machine and copied here:
#   design.bit    Vivado bitstream (…runs/impl_1/design_1_wrapper.bit)
#   app.elf       Vitis application (…/loopback/build/loopback.elf or Debug/)
#   ps7_init.tcl  PS initialisation generated FOR YOUR BLOCK DESIGN. Lives
#                 inside the exported .xsa (which is a zip):
#                     unzip -j design_1_wrapper.xsa ps7_init.tcl -d host/mac/
#                 Defaults to host/mac/ps7_init.tcl if not given.
#
# In another terminal, BEFORE running this, open the serial console:
#   screen /dev/cu.usbmodem0201258920271 115200      (Ctrl-A then K to quit)
#
# Verified: OpenOCD 0.12 sees both TAPs (XC7Z020 fabric + Cortex-A9) on this
# board from this Mac. The program sequence is untested until the first
# .bit/.elf exist -- expect one iteration.
set -eu
here="$(cd "$(dirname "$0")" && pwd)"
bit="${1:?bitstream}"; elf="${2:?elf}"; ps7="${3:-$here/ps7_init.tcl}"
for f in "$bit" "$elf" "$ps7"; do [ -f "$f" ] || { echo "missing: $f"; exit 1; }; done

# ELF entry point: e_entry, 4 bytes little-endian at offset 0x18 (ELF32).
entry=$(python3 -c "import struct,sys; d=open(sys.argv[1],'rb').read(0x1c); \
assert d[:4]==b'\x7fELF' and d[4]==1, 'not an ELF32'; \
print('0x%08x' % struct.unpack('<I', d[0x18:0x1c])[0])" "$elf")
echo "ELF entry point: $entry"

exec openocd -f board/digilent_zedboard.cfg -f "$here/zynq_load.tcl" \
    -c "zynq_program {$ps7} {$bit} {$elf} $entry; shutdown"
