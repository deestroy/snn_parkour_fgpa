"""M4 final check: the C1 engine on real silicon vs the golden model.

Upload conv.bit, conv.hwh, conv_test_data.npz and this file to the board's
Jupyter, then:   %run conv_test.py

Streams 16 golden N-MNIST samples through the fabric (292 words in, 580
words out per sample) and compares every received word against the golden
model's spike maps. This is the same comparison the simulation testbench
makes -- passing here means the bitstream on this exact chip reproduces the
golden model bit for bit, which is M4's done-when.

UNTESTED disclosure: like loopback_test.py, this can only run on a real
board and was written blind. The simulation twin it mirrors
(sim/tb_axis_conv.v) passes; physics is the remaining variable.
"""

import time

import numpy as np

OVERLAY = "conv.bit"
DATA = "conv_test_data.npz"


def main():
    try:
        from pynq import Overlay, allocate
    except ImportError:
        raise SystemExit("pynq not importable -- run this on the board.")

    d = np.load(DATA)
    tx_words, rx_words, labels = d["tx_words"], d["rx_words"], d["labels"]
    n_samples, n_tx = tx_words.shape
    n_rx = rx_words.shape[1]

    print("loading %s ..." % OVERLAY)
    ol = Overlay(OVERLAY)
    dma_names = [k for k in ol.ip_dict if "dma" in k.lower()]
    if not dma_names:
        raise SystemExit("no DMA in overlay; ip_dict: %s" % list(ol.ip_dict))
    dma = getattr(ol, dma_names[0])

    tx = allocate(shape=(n_tx,), dtype=np.uint32)
    rx = allocate(shape=(n_rx,), dtype=np.uint32)

    fails = 0
    t0 = time.time()
    for s in range(n_samples):
        tx[:] = tx_words[s]
        rx[:] = 0
        dma.recvchannel.transfer(rx)
        dma.sendchannel.transfer(tx)
        dma.sendchannel.wait()   # hang: DMA can't reach DDR (HP0 missing?)
        dma.recvchannel.wait()   # hang: engine never produced 580 words
        bad = int((np.asarray(rx) != rx_words[s]).sum())
        status = "ok" if bad == 0 else "%d/%d words WRONG" % (bad, n_rx)
        print("  sample %2d (digit %d): %s" % (s, int(labels[s]), status))
        fails += bad
    dt = time.time() - t0

    if fails == 0:
        print("\nHARDWARE PASS: %d samples, %d words, bit-identical to the"
              " golden model on real silicon. (%.2f s, %.1f ms/sample"
              " including Python overhead)"
              % (n_samples, n_samples * n_rx, dt, 1000 * dt / n_samples))
        print("M4's done-when is met.")
    else:
        print("\nHARDWARE FAIL: %d word mismatches. The same vectors pass in"
              " simulation, so suspect: clocking, the weight hex not making"
              " it into synthesis, or DMA buffer sizes." % fails)

    tx.freebuffer()
    rx.freebuffer()


main()
