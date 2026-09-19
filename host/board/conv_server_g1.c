/* conv_server_g1.c -- the DVS-Gesture (DATASET=1) build of conv_server, as
 * its OWN Vitis application component so it can never be confused with the
 * N-MNIST build (2026-09-19: a renamed copy of the DATASET=0 ELF reached the
 * card as "conv_server_g1.elf"; the client's PING check refused it).
 *
 * Vitis workspace layout this relies on (vitis_m4_loopback_zed):
 *     conv_server/src/conv_server.c      the one server source (build 5+)
 *     conv_server_g1/src/conv_server_g1.c   THIS file, and nothing else
 * The include below reaches the real source by relative path, so there is
 * exactly one copy of the server code; DATASET is fixed here, not in any
 * IDE setting. Copy host/board/conv_server.c to conv_server/src/ as before
 * whenever it changes; this file never needs to change.
 */
#define DATASET 1
#include "../../conv_server/src/conv_server.c"
