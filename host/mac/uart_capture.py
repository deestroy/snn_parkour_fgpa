"""Capture the ZedBoard's UART to a file (and stdout) for N seconds.
Usage: python3 host/mac/uart_capture.py [seconds] [outfile]"""
import sys, time, serial
PORT = "/dev/cu.usbmodem0201258920271"
secs = float(sys.argv[1]) if len(sys.argv) > 1 else 30
out = open(sys.argv[2], "wb") if len(sys.argv) > 2 else None
p = serial.Serial(PORT, 115200, timeout=0.2)
t0 = time.time()
while time.time() - t0 < secs:
    b = p.read(4096)
    if b:
        sys.stdout.write(b.decode("ascii", "replace")); sys.stdout.flush()
        if out: out.write(b); out.flush()
