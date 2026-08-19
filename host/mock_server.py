"""A software stand-in for conv_server.c: speaks the same protocol, computes
the answer with the golden model instead of the FPGA.

Two jobs:
  1. Prove the client end-to-end before the board exists (framing, CRC,
     packing, error paths) -- `python3 host/mock_server.py --selftest`.
  2. Later, A/B the real board against it: same client, two servers, the
     outputs must be identical.

Serves over a pty so the client talks to it exactly as it would to
/dev/cu.usbmodem…, or in-process via a pair of pipes for the selftest.
"""

import os
import sys
import threading

import numpy as np

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, REPO)
sys.path.insert(0, os.path.join(REPO, "sim"))
from golden.network import GoldenNetwork  # noqa: E402
from export_axis_vectors import pack_words  # noqa: E402
from host.snn_link import (Link, CMD_PING, CMD_RUN_CONV, CMD_BURST,  # noqa: E402
                           RSP_OK, RSP_ERR, crc_words)

T, C_IN, H_IN, W_IN = 4, 2, 34, 34
C_OUT, H_OUT, W_OUT = 16, 17, 17
WORDS_IN = (C_IN * H_IN * W_IN + 31) // 32       # 73
WORDS_OUT = (C_OUT * H_OUT * W_OUT + 31) // 32   # 145
CAP = 1024


def unpack_words(words: np.ndarray, n_bits: int) -> np.ndarray:
    b = np.asarray(words, dtype="<u4").view(np.uint8)
    bits = np.unpackbits(b, bitorder="little")
    return bits[:n_bits]


class MockConvServer:
    # a plausible stand-in for the fabric: dense C1 ~340k cycles at 100 MHz
    MOCK_LATENCY_S = 3.4e-3
    MOCK_TICKS_PER_S = 333333333

    def __init__(self):
        self.golden = GoldenNetwork()
        self.last_out = None          # BURST replays the last RUN_CONV

    def run_conv(self, words: np.ndarray) -> np.ndarray:
        assert words.size == T * WORDS_IN
        frames = np.zeros((1, T, C_IN, H_IN, W_IN), np.uint8)
        for t in range(T):
            bits = unpack_words(words[t * WORDS_IN:(t + 1) * WORDS_IN],
                                C_IN * H_IN * W_IN)
            frames[0, t] = bits.reshape(C_IN, H_IN, W_IN)
        _, trace = self.golden.forward(frames, record=True)
        out = []
        for t in range(T):
            out.append(pack_words(trace["c1_S"][t][0].ravel().astype(np.uint8)))
        return np.concatenate(out).astype("<u4")

    def serve(self, link: Link) -> None:
        link.send(CMD_PING | RSP_OK, np.array([1, CAP], "<u4"))  # announce
        while True:
            try:
                cmd, words = link.recv()
            except TimeoutError:
                return                       # peer gone
            except IOError:
                # CRC failure: reject the frame and keep serving, exactly as
                # conv_server.c does. (First mock version returned here and
                # left the client hanging -- caught by fault injection.)
                link.send(RSP_ERR, np.array([2], "<u4"))
                continue
            if cmd == CMD_PING:
                link.send(CMD_PING | RSP_OK, np.array([1, CAP], "<u4"))
            elif cmd == CMD_RUN_CONV:
                if words.size != T * WORDS_IN:
                    link.send(RSP_ERR, np.array([3], "<u4"))
                else:
                    self.last_out = self.run_conv(words)
                    link.send(CMD_RUN_CONV | RSP_OK, self.last_out)
            elif cmd == CMD_BURST:
                if words.size != 1 or int(words[0]) == 0:
                    link.send(RSP_ERR, np.array([3], "<u4"))
                elif self.last_out is None:
                    link.send(RSP_ERR, np.array([6], "<u4"))
                else:
                    # the mock does not re-run N times: it is deterministic by
                    # construction, so mismatches = 0; it reports the ticks the
                    # fabric would plausibly take, so the client's arithmetic
                    # and checks are exercised end to end
                    n = int(words[0])
                    ticks = int(n * self.MOCK_LATENCY_S * self.MOCK_TICKS_PER_S)
                    rep = np.array([n, ticks & 0xFFFFFFFF, ticks >> 32,
                                    self.MOCK_TICKS_PER_S, 0,
                                    crc_words(self.last_out)], "<u4")
                    link.send(CMD_BURST | RSP_OK, rep)
            else:
                link.send(RSP_ERR, np.array([1], "<u4"))


class _PipeEnd:
    """One end of a bidirectional in-process pipe with read(n)/write()."""
    def __init__(self, r, w):
        self.r, self.w = r, w
    def read(self, n):
        return os.read(self.r, n)
    def write(self, b):
        os.write(self.w, b)
    def flush(self):
        pass


def in_process_pair():
    a_r, b_w = os.pipe()   # server writes b_w -> client reads a_r
    b_r, a_w = os.pipe()   # client writes a_w -> server reads b_r
    client = _PipeEnd(a_r, a_w)
    server = _PipeEnd(b_r, b_w)
    return client, server


def selftest() -> int:
    from host.uart_client import run_samples
    client_end, server_end = in_process_pair()
    srv = MockConvServer()
    th = threading.Thread(target=srv.serve, args=(Link(server_end),), daemon=True)
    th.start()
    from host.uart_client import run_burst
    link = Link(client_end)
    ok = run_samples(link, label="mock (golden model)")
    ok = run_burst(link, n=1000, sample=0, label="mock") and ok
    return 0 if ok else 1


if __name__ == "__main__":
    if "--selftest" in sys.argv:
        raise SystemExit(selftest())
    print("use --selftest, or import MockConvServer")
