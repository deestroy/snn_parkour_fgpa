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
from host.snn_link import (Link, CMD_PING, CMD_RUN_CONV, RSP_OK,  # noqa: E402
                           RSP_ERR)

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
    def __init__(self):
        self.golden = GoldenNetwork()

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
                    link.send(CMD_RUN_CONV | RSP_OK, self.run_conv(words))
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
    ok = run_samples(Link(client_end), label="mock (golden model)")
    return 0 if ok else 1


if __name__ == "__main__":
    if "--selftest" in sys.argv:
        raise SystemExit(selftest())
    print("use --selftest, or import MockConvServer")
