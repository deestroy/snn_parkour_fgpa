/*
 * M4 Stage B: bare-metal server for the C1 conv engine on the ZedBoard.
 *
 * Loop forever: read a frame from the UART (see host/protocol.md), if it is
 * RUN_CONV push the payload through AXI DMA -> axis_conv_top -> AXI DMA and
 * return the result frame; if PING, answer with capacity. All I/O paced and
 * checksummed; a bad frame gets an error frame, never silence.
 *
 * Runs from OCM (D0015 workaround): buffers are static and small. If DDR
 * ever comes up, only the linker script and the caps here need to change.
 *
 * Built like loopback.c: paste over the app's source, keep lscript.ld
 * pointing at ps7_ram_0. Same #ifdef SDT DMA lookup, same paced UART.
 *
 * UNTESTED on hardware until the Stage B bitstream exists. The Mac client
 * has been exercised against a Python mock of this server (see
 * host/mock_server.py) so the protocol and packing are known-good; what
 * remains untested is this C and the engine on silicon.
 */

#include <stdint.h>
#include "xparameters.h"
#include "xaxidma.h"
#include "xil_cache.h"
#include "xstatus.h"

/* ---------------------------------------------------------------- config */
#define BUILD_ID       0x00000001u
#define CAP_WORDS      1024u                    /* per direction, OCM-sized */
#define TIMEOUT_LOOP   (50000000u)

#ifdef SDT
#  define DMA_DEV_ID  XPAR_XAXIDMA_0_BASEADDR
#else
#  define DMA_DEV_ID  XPAR_AXIDMA_0_DEVICE_ID
#endif

#define MAGIC          0x5A4E4E53u
#define CMD_RUN_CONV   0x01
#define CMD_PING       0x02
#define RSP_OK_BIT     0x80
#define RSP_ERR        0xFF
#define ERR_MAGIC 1
#define ERR_CRC   2
#define ERR_NWORDS 3
#define ERR_DMA_TIMEOUT 4
#define ERR_DMA_SETUP 5

/* C1 geometry -- must match axis_conv_top's parameters */
#define T_STEPS        4u
#define WORDS_IN_TS    73u                      /* ceil(2*34*34 / 32)     */
#define WORDS_OUT_TS   145u                     /* ceil(16*17*17 / 32)    */
#define REQ_WORDS      (T_STEPS * WORDS_IN_TS)  /* 292                    */
#define RSP_WORDS      (T_STEPS * WORDS_OUT_TS) /* 580                    */

/* ---------------------------------------------------------- paced UART */
#define UART1_BASE   0xE0001000u
#define UART_SR      (*(volatile uint32_t *)(UART1_BASE + 0x2C))
#define UART_FIFO    (*(volatile uint32_t *)(UART1_BASE + 0x30))
#define SR_TXEMPTY   (1u << 3)
#define SR_RXEMPTY   (1u << 1)

static void putc_safe(uint8_t c) {
    while (!(UART_SR & SR_TXEMPTY)) { }
    UART_FIFO = c;
    while (!(UART_SR & SR_TXEMPTY)) { }
}
static uint8_t getc_block(void) {
    while (UART_SR & SR_RXEMPTY) { }
    return (uint8_t)(UART_FIFO & 0xFF);
}
static void put_u32(uint32_t v) {
    putc_safe(v & 0xFF); putc_safe((v >> 8) & 0xFF);
    putc_safe((v >> 16) & 0xFF); putc_safe((v >> 24) & 0xFF);
}
static uint32_t get_u32(void) {
    uint32_t v = getc_block();
    v |= (uint32_t)getc_block() << 8;
    v |= (uint32_t)getc_block() << 16;
    v |= (uint32_t)getc_block() << 24;
    return v;
}

/* --------------------------------------------------------------- CRC32 */
static uint32_t crc_table[256];
static void crc_init(void) {
    for (uint32_t i = 0; i < 256; i++) {
        uint32_t c = i;
        for (int k = 0; k < 8; k++) c = (c & 1) ? 0xEDB88320u ^ (c >> 1) : c >> 1;
        crc_table[i] = c;
    }
}
static uint32_t crc_update(uint32_t crc, const uint8_t *p, uint32_t n) {
    crc = ~crc;
    while (n--) crc = crc_table[(crc ^ *p++) & 0xFF] ^ (crc >> 8);
    return ~crc;
}
static uint32_t crc_word(uint32_t crc, uint32_t w) {
    uint8_t b[4] = { w & 0xFF, (w >> 8) & 0xFF, (w >> 16) & 0xFF, (w >> 24) & 0xFF };
    return crc_update(crc, b, 4);
}

/* ---------------------------------------------------------------- frames */
static uint32_t rx_words[CAP_WORDS] __attribute__((aligned(64)));
static uint32_t tx_words[CAP_WORDS] __attribute__((aligned(64)));
static XAxiDma dma;

static void send_frame(uint8_t cmd, const uint32_t *payload, uint32_t n) {
    uint8_t hdr[8] = { 0x53, 0x4E, 0x4E, 0x5A, cmd, 0, n & 0xFF, (n >> 8) & 0xFF };
    uint32_t crc = crc_update(0, hdr, 8);
    for (int i = 0; i < 8; i++) putc_safe(hdr[i]);
    for (uint32_t i = 0; i < n; i++) { put_u32(payload[i]); crc = crc_word(crc, payload[i]); }
    put_u32(crc);
}
static void send_error(uint32_t code) {
    send_frame(RSP_ERR, &code, 1);
}

/* Read one frame into rx_words. Returns cmd, or 0 on transport error
 * (after sending the error frame). Resyncs on magic byte by byte. */
static uint8_t recv_frame(uint32_t *n_out) {
    /* hunt for magic */
    uint32_t win = 0;
    for (;;) {
        win = (win >> 8) | ((uint32_t)getc_block() << 24);
        if (win == MAGIC) break;
    }
    uint8_t cmd = getc_block();
    uint8_t flags = getc_block();
    uint32_t n = getc_block();
    n |= (uint32_t)getc_block() << 8;
    uint8_t hdr[8] = { 0x53, 0x4E, 0x4E, 0x5A, cmd, flags, n & 0xFF, (n >> 8) & 0xFF };
    uint32_t crc = crc_update(0, hdr, 8);
    if (n > CAP_WORDS) {
        /* drain and reject */
        for (uint32_t i = 0; i < n * 4 + 4; i++) getc_block();
        send_error(ERR_NWORDS); return 0;
    }
    for (uint32_t i = 0; i < n; i++) { rx_words[i] = get_u32(); crc = crc_word(crc, rx_words[i]); }
    uint32_t got = get_u32();
    if (got != crc) { send_error(ERR_CRC); return 0; }
    *n_out = n;
    return cmd;
}

/* ------------------------------------------------------------------ DMA */
static int wait_idle(int dir) {
    uint32_t n = 0;
    while (XAxiDma_Busy(&dma, dir)) if (++n > TIMEOUT_LOOP) return XST_FAILURE;
    return XST_SUCCESS;
}

static int run_conv(uint32_t n_in) {
    if (n_in != REQ_WORDS) { send_error(ERR_NWORDS); return -1; }
    Xil_DCacheFlushRange((UINTPTR)rx_words, REQ_WORDS * 4);
    Xil_DCacheFlushRange((UINTPTR)tx_words, RSP_WORDS * 4);
    if (XAxiDma_SimpleTransfer(&dma, (UINTPTR)tx_words, RSP_WORDS * 4,
                               XAXIDMA_DEVICE_TO_DMA) != XST_SUCCESS ||
        XAxiDma_SimpleTransfer(&dma, (UINTPTR)rx_words, REQ_WORDS * 4,
                               XAXIDMA_DMA_TO_DEVICE) != XST_SUCCESS) {
        send_error(ERR_DMA_SETUP); return -1;
    }
    if (wait_idle(XAXIDMA_DMA_TO_DEVICE) != XST_SUCCESS ||
        wait_idle(XAXIDMA_DEVICE_TO_DMA) != XST_SUCCESS) {
        send_error(ERR_DMA_TIMEOUT); return -1;
    }
    Xil_DCacheInvalidateRange((UINTPTR)tx_words, RSP_WORDS * 4);
    send_frame(CMD_RUN_CONV | RSP_OK_BIT, tx_words, RSP_WORDS);
    return 0;
}

int main(void) {
    crc_init();
    XAxiDma_Config *cfg = XAxiDma_LookupConfig(DMA_DEV_ID);
    if (!cfg || XAxiDma_CfgInitialize(&dma, cfg) != XST_SUCCESS || XAxiDma_HasSg(&dma)) {
        for (;;) send_error(ERR_DMA_SETUP);   /* loud, forever */
    }
    XAxiDma_IntrDisable(&dma, XAXIDMA_IRQ_ALL_MASK, XAXIDMA_DEVICE_TO_DMA);
    XAxiDma_IntrDisable(&dma, XAXIDMA_IRQ_ALL_MASK, XAXIDMA_DMA_TO_DEVICE);

    /* announce: an unsolicited PING response so the host sees us come up */
    { uint32_t info[2] = { BUILD_ID, CAP_WORDS }; send_frame(CMD_PING | RSP_OK_BIT, info, 2); }

    for (;;) {
        uint32_t n = 0;
        uint8_t cmd = recv_frame(&n);
        if (cmd == CMD_PING) {
            uint32_t info[2] = { BUILD_ID, CAP_WORDS };
            send_frame(CMD_PING | RSP_OK_BIT, info, 2);
        } else if (cmd == CMD_RUN_CONV) {
            run_conv(n);
        } else if (cmd != 0) {
            send_error(ERR_MAGIC);
        }
    }
}
