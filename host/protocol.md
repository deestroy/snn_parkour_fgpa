# Board <-> host UART protocol (M4 Stage B onward)

One request/response per exchange, over the ZedBoard's USB UART at 115200
8N1. All multi-byte fields little-endian. Designed for a bare-metal C server
in OCM (host/board/conv_server.c) and a Python client on the Mac
(host/uart_client.py). Both cite this file.

## Frame (same shape both directions)

| offset | size | field | notes |
|---|---|---|---|
| 0 | 4 | magic | `0x5A4E4E53` ("SNNZ" as bytes `53 4E 4E 5A`) |
| 4 | 1 | cmd | request: 0x01 = RUN_CONV, 0x02 = PING. response: 0x81 / 0x82; 0xFF = error |
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
5 = DMA setup failed.

## PING (0x02)

Empty payload; response 0x82 with payload = 2 words: [build id, N_WORDS cap].
Used by the client to confirm the link and the server's buffer size before
sending anything.

## Sizing (OCM constraint, D0015)

Server buffers are static: rx and tx each 65535 words (256 KB, in DDR). C1's 292/580
fit with vast room; every layer of the network fits. If something ever needs
more, the 16-bit n_words field is the real ceiling -- the PING reply tells the client the cap.

## Why framed + CRC

A UART has no framing. A single dropped byte would otherwise shift every
later word by one and produce a "mismatch" that looks like an engine bug.
Magic + length + CRC make that impossible to misread: the frame is either
accepted intact or rejected as a transport error, never silently corrupted.
