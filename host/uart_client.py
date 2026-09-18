"""M4 Stage B client: stream golden C1 samples to the board over UART and
compare every returned word against the golden model.

Run:  python3 host/uart_client.py                       # real board
      python3 host/uart_client.py --port /dev/cu.usbmodemXXXX
      python3 host/mock_server.py --selftest            # same code, no board

HARDWARE PASS here means: for every sample, the FPGA's C1 engine returned
the same 580 packed spike words the golden model produces -- the M4 done-when
("correct results back from real hardware"), with the comparison made on the
Mac against the file that the simulation testbench also passed.
"""

import argparse
import os
import sys
import time

import numpy as np

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, REPO)
from host.snn_link import (Link, CMD_PING, CMD_RUN_CONV, CMD_BURST,  # noqa: E402
                           BurstResult, crc_words)

DEFAULT_PORT = "/dev/cu.usbmodem0201258920271"
DATA = os.path.join(REPO, "host", "conv_test_data.npz")
# DATASET (C0012): 0 = N-MNIST C1 (16 samples, 292/580 words), 1 = DVS-Gesture
# C1 (8 samples, 1,024/2,048 words). The server (build 5+) reports its
# DATASET in PING word 2; a mismatch is refused before any sample is sent.
DATASETS = {"c1": (0, DATA, "N-MNIST C1"),
            "g1": (1, os.path.join(REPO, "host", "conv_test_data_g1.npz"), "DVS-Gesture C1")}


def run_samples(link: Link, label: str = "board", dataset: str = "c1") -> bool:
    want_ds, data, ds_name = DATASETS[dataset]
    d = np.load(data)
    tx, rx, labels = d["tx_words"], d["rx_words"], d["labels"]
    n_samples, n_tx = tx.shape

    # any unsolicited announce frame from a fresh boot is harmless: call()
    # hunts for the PING response it asked for
    info = link.call(CMD_PING, np.zeros(0, "<u4"))
    got_ds = int(info[2]) if info.size > 2 else 0
    ds = ("N-MNIST C1", "DVS-Gesture C1")[got_ds] if info.size > 2 else "N-MNIST C1 (build <5)"
    print("[%s] PING ok: build %d, cap %d words, dataset %s" % (label, info[0], info[1], ds))
    if got_ds != want_ds:
        print("FAIL: server is a DATASET=%d build but the check set is %s (DATASET=%d)"
              " -- wrong BOOT.bin/server for this bitstream, nothing sent" % (got_ds, ds_name, want_ds))
        return False
    if info[1] < max(n_tx, rx.shape[1]):
        print("FAIL: server cap %d < needed %d" % (info[1], max(n_tx, rx.shape[1])))
        return False

    fails = 0
    t0 = time.time()
    for s in range(n_samples):
        got = link.call(CMD_RUN_CONV, tx[s])
        if got.size != rx.shape[1]:
            print("  sample %2d: wrong length %d" % (s, got.size)); fails += 1; continue
        bad = int((got != rx[s]).sum())
        print("  sample %2d (digit %d): %s"
              % (s, int(labels[s]), "ok" if bad == 0 else "%d/%d words WRONG" % (bad, got.size)))
        fails += bad
    dt = time.time() - t0

    if fails == 0:
        print("\n%s PASS: %d samples, %d words, bit-identical to the golden model"
              " (%.2f s, %.0f ms/sample incl. UART)"
              % (label.upper() if label == "board" else "MOCK",
                 n_samples, n_samples * rx.shape[1], dt, 1000 * dt / n_samples))
        return True
    print("\nFAIL: %d word mismatches" % fails)
    return False


def run_burst(link: Link, n: int, sample: int = 0, label: str = "board",
              sweep: bool = False, preload=None, dataset: str = "c1") -> bool:
    """M5/M7 measurement mode: load ONE golden sample, then have the board
    replay it n times back to back (protocol.md BURST). Verifies the last
    output's CRC against golden and that every iteration matched the first,
    then reports system latency per inference. Blocks for as long as the
    burst runs -- choose n for the duration the meter needs."""
    d = np.load(DATASETS[dataset][1])
    tx, rx = d["tx_words"], d["rx_words"]
    load = preload if preload is not None else [sample]
    for s_i in load:
        got = link.call(CMD_RUN_CONV, tx[s_i])
        if got.size != rx.shape[1] or int((got != rx[s_i]).sum()):
            print("[%s] burst: sample %d did not match golden on load" % (label, s_i))
            return False
    est = 8e-3 * n                       # generous timeout: 8 ms/inference (DVS-Gesture worst ~4.6 ms)
    old = getattr(link.s, "timeout", None)
    if old is not None:
        link.s.timeout = max(old, est + 5.0)
    try:
        t0 = time.time()
        payload = np.array([n, 1], "<u4") if sweep else np.array([n], "<u4")
        r = BurstResult(link.call(CMD_BURST, payload))
        wall = time.time() - t0
    finally:
        if old is not None:
            link.s.timeout = old
    exp_last = rx[load[(n - 1) % len(load)]] if sweep else rx[sample]
    ok = (r.n == n and r.mismatches == 0 and r.crc_last == crc_words(exp_last))
    print("[%s] BURST sample %d: %s%s" % (label, sample, r,
          "" if ok else "  <-- CHECK FAILED (n/mismatch/crc)"))
    # the board's tick rate is a constant in conv_server.c; wall-clock on
    # the Mac (which includes ~0.1 s of UART/turnaround) must agree with it
    print("[%s]   wall-clock %.3f s vs board %.3f s (tick-rate cross-check; "
          "wall includes UART overhead)" % (label, wall, r.elapsed_s))
    if r.elapsed_s > 1.0 and abs(wall - r.elapsed_s) > 0.05 * r.elapsed_s + 0.5:
        print("[%s]   WARNING: tick rate looks wrong" % label); ok = False
    return ok


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--port", default=DEFAULT_PORT)
    ap.add_argument("--baud", type=int, default=115200)
    ap.add_argument("--burst", type=int, default=0,
                    help="after the 16-sample check, replay sample --sample N times and report latency")
    ap.add_argument("--sample", type=int, default=0)
    ap.add_argument("--burst-sweep", action="store_true",
                    help="cycle ALL 16 samples during the burst (C0018)")
    ap.add_argument("--burst-only", action="store_true",
                    help="skip the 16-sample check (meter runs)")
    ap.add_argument("--dataset", default="c1", choices=sorted(DATASETS),
                    help="c1 = N-MNIST C1 (DATASET=0, default); g1 = DVS-Gesture C1 (DATASET=1)")
    args = ap.parse_args()
    import serial
    ser = serial.Serial(args.port, args.baud, timeout=2.0)
    link = Link(ser)
    ok = True
    n_samples = int(np.load(DATASETS[args.dataset][1])["tx_words"].shape[0])
    if not args.burst_only:
        ok = run_samples(link, label="board", dataset=args.dataset)
        if ok:
            print("M4's done-when is met: correct results back from real hardware.")
    if ok and args.burst:
        ok = run_burst(link, n=args.burst, sample=args.sample, label="board",
                       sweep=args.burst_sweep, dataset=args.dataset,
                       # the server keeps 16 slots and sweeps them oldest-first; fill
                       # all 16 in load order (8-sample sets are loaded twice)
                       preload=[i % n_samples for i in range(16)] if args.burst_sweep else None)
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
