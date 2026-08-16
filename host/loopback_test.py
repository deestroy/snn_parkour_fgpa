"""M4 Stage A check: DMA loopback through the fabric. Runs ON THE BOARD.

Upload loopback.bit, loopback.hwh and this file to Jupyter on the PYNQ-Z2,
then in a notebook cell:   %run loopback_test.py

Sends 100k random words to the fabric and back through the loopback FIFO and
demands the buffer returns bit-identical. Passing means the entire
VM-to-silicon pipeline works; nothing of our design is being tested yet.

UNTESTED disclosure: this script cannot run anywhere except a real booted
board, so unlike everything else in this repo it was written blind. If it
errors in a way the messages below don't explain, that is my bug, not yours.
"""

import time

import numpy as np

N_WORDS = 100_000
OVERLAY = "loopback.bit"


def main():
    try:
        from pynq import Overlay, allocate
    except ImportError:
        raise SystemExit("pynq not importable -- is this running on the "
                         "board's Jupyter, not a laptop?")

    print("loading %s ..." % OVERLAY)
    ol = Overlay(OVERLAY)  # needs loopback.hwh beside it, same basename

    dma_names = [k for k in ol.ip_dict if "dma" in k.lower()]
    if not dma_names:
        raise SystemExit("no DMA in this overlay -- ip_dict has: %s"
                         % list(ol.ip_dict))
    dma = getattr(ol, dma_names[0])
    print("using DMA block: %s" % dma_names[0])

    tx = allocate(shape=(N_WORDS,), dtype=np.uint32)
    rx = allocate(shape=(N_WORDS,), dtype=np.uint32)
    tx[:] = np.random.randint(0, 2**32, size=N_WORDS, dtype=np.uint32)
    rx[:] = 0

    t0 = time.time()
    dma.recvchannel.transfer(rx)   # arm receive FIRST, then send
    dma.sendchannel.transfer(tx)
    dma.sendchannel.wait()         # hang here -> DMA can't reach DDR (HP0?)
    dma.recvchannel.wait()         # hang here -> stream never came back
    dt = time.time() - t0

    if np.array_equal(np.asarray(tx), np.asarray(rx)):
        mb = N_WORDS * 4 / 1e6
        print("LOOPBACK PASS: %d words round-tripped bit-identical "
              "(%.1f MB in %.3f s, %.0f MB/s)" % (N_WORDS, mb, dt, mb / dt))
    else:
        bad = int((np.asarray(tx) != np.asarray(rx)).sum())
        print("LOOPBACK FAIL: %d of %d words differ" % (bad, N_WORDS))

    tx.freebuffer()
    rx.freebuffer()


main()
