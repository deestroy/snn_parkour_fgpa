"""Frame codec for the board<->host UART protocol (host/protocol.md).

Pure functions plus a small transport class so both the real client and the
mock server share exactly one implementation of framing and CRC. Any drift
between what the Mac sends and what the C server expects shows up here first.
"""

import struct
import zlib
from typing import Optional, Tuple

import numpy as np

MAGIC = 0x5A4E4E53
CMD_RUN_CONV = 0x01
CMD_PING = 0x02
CMD_BURST = 0x03
RSP_OK = 0x80
RSP_ERR = 0xFF
ERR_NAMES = {1: "bad magic", 2: "bad crc", 3: "wrong n_words",
             4: "DMA timeout", 5: "DMA setup failed", 6: "no sample loaded"}


def crc_words(words) -> int:
    """CRC-32 of packed words as the board computes it (LSB-first bytes)."""
    return zlib.crc32(np.asarray(words, dtype="<u4").tobytes()) & 0xFFFFFFFF


class BurstResult:
    """Decoded BURST reply (protocol.md): system latency per inference and
    the two self-checks the client must verify."""
    def __init__(self, words):
        self.n = int(words[0])
        self.ticks = int(words[1]) | (int(words[2]) << 32)
        self.ticks_per_s = int(words[3])
        self.mismatches = int(words[4])
        self.crc_last = int(words[5])
        self.elapsed_s = self.ticks / self.ticks_per_s
        self.latency_s = self.elapsed_s / max(self.n, 1)

    def __str__(self):
        return ("%d iterations in %.3f s -> %.1f us/inference (%.0f inf/s), "
                "%d mismatches, crc %08x"
                % (self.n, self.elapsed_s, 1e6 * self.latency_s,
                   self.n / self.elapsed_s if self.elapsed_s else 0.0,
                   self.mismatches, self.crc_last))


def encode(cmd: int, payload: np.ndarray) -> bytes:
    payload = np.asarray(payload, dtype="<u4")
    hdr = struct.pack("<IBBH", MAGIC, cmd, 0, payload.size)
    body = hdr + payload.tobytes()
    return body + struct.pack("<I", zlib.crc32(body) & 0xFFFFFFFF)


class Link:
    """Byte-stream transport (anything with .read(n)->bytes and .write(b))."""

    def __init__(self, stream, timeout_s: float = 5.0):
        self.s = stream
        self.timeout = timeout_s

    def send(self, cmd: int, payload) -> None:
        self.s.write(encode(cmd, payload))
        if hasattr(self.s, "flush"):
            self.s.flush()

    def _read_exact(self, n: int) -> bytes:
        buf = b""
        while len(buf) < n:
            chunk = self.s.read(n - len(buf))
            if not chunk:
                raise TimeoutError("link: no data (%d/%d bytes)" % (len(buf), n))
            buf += chunk
        return buf

    def recv(self) -> Tuple[int, np.ndarray]:
        """Hunt for magic, then read one frame. Returns (cmd, payload words).
        Raises on CRC failure -- the transport is either intact or rejected."""
        win = b""
        while True:
            win = (win + self._read_exact(1))[-4:]
            if win == b"SNNZ":
                break
        rest = self._read_exact(4)
        cmd, flags, n = struct.unpack("<BBH", rest)
        body = win + rest
        data = self._read_exact(4 * n)
        crc_rx, = struct.unpack("<I", self._read_exact(4))
        crc = zlib.crc32(body + data) & 0xFFFFFFFF
        if crc != crc_rx:
            raise IOError("link: crc mismatch (got %08x want %08x)" % (crc_rx, crc))
        return cmd, np.frombuffer(data, dtype="<u4").copy()

    def call(self, cmd: int, payload, max_skip: int = 4) -> np.ndarray:
        """Request/response. Raises with the server's error name on RSP_ERR.

        A freshly booted server sends an unsolicited PING-response announce;
        a client that starts mid-stream may also see a stale reply. Skip up
        to max_skip frames that are not the answer to THIS command -- the
        mock server caught exactly this desync on the first selftest."""
        self.send(cmd, payload)
        for _ in range(max_skip + 1):
            rcmd, words = self.recv()
            if rcmd == RSP_ERR:
                code = int(words[0]) if words.size else -1
                err = RuntimeError("board error: %s" % ERR_NAMES.get(code, code))
                err.code = code
                raise err
            if rcmd == (cmd | RSP_OK):
                return words
        raise RuntimeError("no matching response for cmd 0x%02x" % cmd)

    def drain(self, quiet_s: float = 0.2) -> int:
        """Discard any frames already in flight (stale replies, announces).
        Call after an error, before the next request. Returns count dropped.
        Requires the stream to time out on read; the in-process pipe and
        pyserial both do."""
        n = 0
        old = getattr(self.s, "timeout", None)
        try:
            if old is not None:
                self.s.timeout = quiet_s
            while True:
                try:
                    self.recv(); n += 1
                except (TimeoutError, IOError):
                    break
        finally:
            if old is not None:
                self.s.timeout = old
        return n
