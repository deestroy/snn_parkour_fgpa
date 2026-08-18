#!/usr/bin/env bash
# Run a Vitis-built FSBL on the ZedBoard from the Mac and capture its UART
# verdict on DDR. The FSBL does its OWN ps7_init (the C version, with
# silicon-rev workarounds), so this loader deliberately skips ours: reset,
# release PROG_B, load the FSBL ELF into OCM, run, listen.
#
# Usage: bash host/mac/run_fsbl.sh host/mac/build/fsbl.elf
# Vitis: File > New Component > Application > template "Zynq FSBL" on
#        zed_platform > Build > copy zynq_fsbl.elf here as fsbl.elf.
#        (Its default lscript already targets OCM; do not edit it.)
set -eu
here="$(cd "$(dirname "$0")" && pwd)"; cd "$here/../.."
elf="${1:?fsbl elf}"; [ -f "$elf" ] || { echo "missing $elf"; exit 1; }
entry=$(python3 -c "import struct,sys; d=open(sys.argv[1],'rb').read(0x1c); print('0x%08x'%struct.unpack('<I',d[0x18:0x1c])[0])" "$elf")
S=host/mac/build/logs
mkdir -p "$S"; pkill -f uart_capture 2>/dev/null || true; sleep 1
(python3 host/mac/uart_capture.py 40 "$S/fsbl_uart.txt" > /dev/null 2>&1 &); sleep 4
openocd -f board/digilent_zedboard.cfg -f "$here/zynq_load.tcl" -c "
  init; targets zynq.cpu0; reset halt; sleep 300
  set ctrl [expr {\"0x[string range [mrd 0xF8007000] end-8 end]\"}]
  mww 0xF8007000 [expr {\$ctrl & ~(1 << 30)}]; sleep 5
  mww 0xF8007000 [expr {\$ctrl | (1 << 30)}]; sleep 50
  load_image $elf; resume $entry
  echo {== FSBL running; UART capture has it ==}; shutdown" 2>&1 | grep -E "==|Error" || true
sleep 20; echo "=========== FSBL UART ==========="; cat -v "$S/fsbl_uart.txt"; echo; echo "================================="
