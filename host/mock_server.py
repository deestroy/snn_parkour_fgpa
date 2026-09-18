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
CAP = 4096


def unpack_words(words: np.ndarray, n_bits: int) -> np.ndarray:
    b = np.asarray(words, dtype="<u4").view(np.uint8)
    bits = np.unpackbits(b, bitorder="little")
    return bits[:n_bits]


class MockConvServer:
    # a plausible stand-in for the fabric: dense C1 ~340k cycles at 100 MHz
    MOCK_LATENCY_S = 3.4e-3
    MOCK_TICKS_PER_S = 333333333

    def __init__(self, dataset: str = "c1"):
        self.dataset = 1 if dataset == "g1" else 0
        self.golden = GoldenNetwork()
        self.last_out = None          # BURST replays the last RUN_CONV
        self.loaded = []              # outputs of loaded samples, in order (C0018)
        self.table = None
        if self.dataset == 1:
            # DVS-Gesture C1: answer from the harness-validated word streams
            # (the golden g1 conv lives in sim/export_dvsgesture_vectors.py;
            # the mock only has to exercise the client's plumbing at the
            # 1,024/2,048-word frame size and the PING dataset word)
            d = np.load(os.path.join(REPO, "host", "conv_test_data_g1.npz"))
            self.table = {d["tx_words"][i].tobytes(): d["rx_words"][i].astype("<u4")
                          for i in range(d["tx_words"].shape[0])}

    def run_conv(self, words: np.ndarray) -> np.ndarray:
        if self.table is not None:
            key = np.asarray(words, "<u4").tobytes()
            if key not in self.table:
                raise ValueError("g1 mock: unknown input frame")
            return self.table[key]
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
        link.send(CMD_PING | RSP_OK, np.array([5, CAP, self.dataset], "<u4"))  # announce (build-5 shape)
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
                link.send(CMD_PING | RSP_OK, np.array([1, CAP, 0], "<u4"))
            elif cmd == CMD_RUN_CONV:
                n_in = T * WORDS_IN if self.table is None else 4 * 256   # g1: 4 ts x 256 words
                if words.size != n_in:
                    link.send(RSP_ERR, np.array([3], "<u4"))
                else:
                    self.last_out = self.run_conv(words)
                    self.loaded.append(self.last_out)
                    self.loaded = self.loaded[-16:]
                    link.send(CMD_RUN_CONV | RSP_OK, self.last_out)
            elif cmd == CMD_BURST:
                if words.size not in (1, 2) or int(words[0]) == 0:
                    link.send(RSP_ERR, np.array([3], "<u4"))
                elif self.last_out is None:
                    link.send(RSP_ERR, np.array([6], "<u4"))
                else:
                    # deterministic by construction -> mismatches = 0; sleeps
                    # for the time it claims so the wall-clock cross-check is
                    # exercised. Sweep mode: crc_last is the LAST iteration's
                    # sample, i.e. sample (n-1) mod len(loaded).
                    n = int(words[0])
                    sweep = words.size == 2 and int(words[1]) == 1
                    import time
                    time.sleep(n * self.MOCK_LATENCY_S)
                    ticks = int(n * self.MOCK_LATENCY_S * self.MOCK_TICKS_PER_S)
                    if sweep and self.loaded:
                        out = self.loaded[(n - 1) % len(self.loaded)]
                    else:
                        out = self.last_out
                    # build 4 reply shape: temps (mock has no XADC -> 0) and
                    # engine-only ticks, mocked at 90 % of the loop time
                    eng = int(ticks * 0.9)
                    rep = np.array([n, ticks & 0xFFFFFFFF, ticks >> 32,
                                    self.MOCK_TICKS_PER_S, 0,
                                    crc_words(out), 0, 0,
                                    eng & 0xFFFFFFFF, eng >> 32], "<u4")
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


def selftest(dataset: str = "c1") -> int:
    from host.uart_client import run_samples, run_burst
    client_end, server_end = in_process_pair()
    srv = MockConvServer(dataset)
    th = threading.Thread(target=srv.serve, args=(Link(server_end),), daemon=True)
    th.start()
    link = Link(client_end)
    n = 16 if dataset == "c1" else 8
    ok = run_samples(link, label="mock (golden model)", dataset=dataset)
    ok = run_burst(link, n=400, sample=0, label="mock", dataset=dataset) and ok
    ok = run_burst(link, n=100, label="mock", sweep=True, preload=[i % n for i in range(16)], dataset=dataset) and ok
    # the intended failure: a DATASET=0 server must be refused by the g1 check set (and vice versa)
    other = "g1" if dataset == "c1" else "c1"
    c2, s2 = in_process_pair()
    threading.Thread(target=MockConvServer(dataset).serve, args=(Link(s2),), daemon=True).start()
    refused = not run_samples(Link(c2), label="mock (mismatch)", dataset=other)
    print("dataset-mismatch refusal: %s" % ("ok" if refused else "NOT REFUSED"))
    return 0 if (ok and refused) else 1


if __name__ == "__main__":
    if "--selftest" in sys.argv:
        ds = sys.argv[sys.argv.index("--dataset") + 1] if "--dataset" in sys.argv else "c1"
        raise SystemExit(selftest(ds))
    print("use --selftest, or import MockConvServer")
