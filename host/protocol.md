# Board <-> host UART protocol (M4 Stage B onward)

One request/response per exchange, over the ZedBoard's USB UART at 115200
8N1. All multi-byte fields little-endian. Designed for a bare-metal C server
in OCM (host/board/conv_server.c) and a Python client on the Mac
(host/uart_client.py). Both cite this file.

## Frame (same shape both directions)

| offset | size | field | notes |
|---|---|---|---|
| 0 | 4 | magic | `0x5A4E4E53` ("SNNZ" as bytes `53 4E 4E 5A`) |
| 4 | 1 | cmd | request: 0x01 = RUN_CONV, 0x02 = PING, 0x03 = BURST. response: 0x81 / 0x82 / 0x83; 0xFF = error |
| 5 | 1 | flags | reserved, 0 |
| 6 | 2 | n_words | 32-bit words of payload that follow |
| 8 | 4*n | payload | packed spike words (LSB-first bit packing, as axis_conv.v) |
| 8+4n | 4 | crc32 | CRC-32 (IEEE, same as zlib.crc32) over bytes [0, 8+4n) |

## RUN_CONV (0x01)

Request payload: T * WORDS_IN packed input words for ONE sample (C1: 4*73 =
292 words). Board streams them through the AXIS engine via DMA and returns
T * WORDS_OUT packed output words (C1: 4*145 = 580 words) as cmd 0x81.

Error response (0xFF): payload is one word, an error code:
1 = bad magic, 2 = bad crc, 3 = wrong n_words, 4 = DMA timeout,
5 = DMA setup failed, 6 = no sample loaded (BURST before any RUN_CONV).

## PING (0x02)

Empty payload; response 0x82 with payload = 2 words: [build id, N_WORDS cap].
Used by the client to confirm the link and the server's buffer size before
sending anything.

## BURST (0x03) — M5/M7 measurement mode

Request payload: 1 word [N] (classic: replay the LAST sample N times) or
2 words [N, 1] (SWEEP, C0018: cycle through ALL loaded samples,
iteration i runs sample i mod n_loaded — the measured power is then the
input distribution's, not one sample's). The server holds up to 16
samples, appended by each RUN_CONV. Precondition: at least one RUN_CONV
has completed.

State between iterations: the engine's membranes are NOT cleared between
burst iterations (the wrapper's per-sample S_CLR runs at each sample
START inside the engine stream: every iteration begins with the same
clear the golden model performs per sample). `mismatches` counts
iterations whose output CRC differed from the FIRST iteration of the
same sample — determinism per sample, identical for both engines. The board runs THAT sample through DMA + engine N times back to
back with no UART traffic, timing the whole loop with the Cortex-A9 global
timer, then replies (0x83) with 6 words:

| word | field | meaning |
|---|---|---|
| 0 | n_done | iterations completed |
| 1 | ticks_lo | elapsed timer ticks, low 32 |
| 2 | ticks_hi | elapsed timer ticks, high 32 |
| 3 | ticks_per_s | timer frequency (COUNTS_PER_SECOND; 333,333,333 on the ZedBoard) |
| 4 | mismatches | iterations whose output CRC differed from that sample's first iteration |
| 5 | crc32_last | CRC-32 (zlib) of the last iteration's output words |

Why it exists. During RUN_CONV the engine is busy for microseconds per
~300 ms of UART, so a meter on the board sees only the ARM's idle floor.
BURST drives the engine at ~100 % duty for a chosen duration, which is
the condition under which "power while running minus power while idle"
is the engine's power. From one reply: latency per inference = ticks /
n_done / ticks_per_s (system latency: engine + DMA + loop overhead; the
engine-only cycles are known exactly from simulation), and with the
meter's idle->burst delta, energy per inference = delta_W * elapsed_s /
n_done. mismatches must be 0 (the engine is deterministic) and crc32_last
must equal the golden CRC for that sample -- the client checks both.

Errors as above; DMA errors abort the loop and report the count so far in
n_done of an error-free reply only if the loop finished -- otherwise the
usual 0xFF error is sent.

## Sizing

Server buffers are static: rx and tx each 65535 words (256 KB, in DDR). C1's 292/580
fit with vast room; every layer of the network fits. If something ever needs
more, the 16-bit n_words field is the real ceiling -- the PING reply tells the client the cap.

## Why framed + CRC

A UART has no framing. A single dropped byte would otherwise shift every
later word by one and produce a "mismatch" that looks like an engine bug.
Magic + length + CRC make that impossible to misread: the frame is either
accepted intact or rejected as a transport error, never silently corrupted.
