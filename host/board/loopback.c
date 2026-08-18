/*
 * M4 Stage A: DMA loopback, bare metal on the ZedBoard's ARM.
 *
 * Fabric = AXI DMA -> AXIS FIFO -> AXI DMA (no custom RTL). Send N words,
 * receive N words, demand they match. Passing proves the toolchain, board,
 * DMA plumbing and cache handling before our engine goes anywhere near
 * silicon.
 *
 * Vitis: create a "Hello World" application from the exported .xsa, then
 * REPLACE its helloworld.c with this file. Everything it needs comes with
 * the platform's BSP (xaxidma, xil_printf, xil_cache).
 *
 * The two Xil_DCache* calls are load-bearing. The ARM caches DDR; the DMA
 * reads/writes DDR directly. Without the flush the DMA sends stale data;
 * without the invalidate the CPU checks stale data. Both look like "DMA
 * corrupted my buffer" and neither is.
 *
 * UNTESTED disclosure: written without a Vitis install to compile against.
 * The first thing to do with it is press Build and report any errors.
 */

#include <stdio.h>
#include <stdint.h>
#include "xparameters.h"
#include "xaxidma.h"
#include "xil_printf.h"
#include "xil_cache.h"
#include "xstatus.h"

#define N_WORDS      (100000u)             /* 400 KB each way, in DDR.
                                              (Was 12288 while DDR looked
                                              dead; it wasn't -- the block
                                              design had the wrong DDR part.
                                              D0015, resolved 2026-08-18.) */
#define TIMEOUT_LOOP (50000000u)           /* spin bound before we give up */

/* Vitis 2024.x Unified IDE builds with -DSDT (System Device Tree). In that
 * flow drivers are found by BASE ADDRESS, not the old numeric DEVICE_ID:
 * XPAR_AXIDMA_0_DEVICE_ID no longer exists. Older classic-Vitis platforms
 * still define DEVICE_ID, so support both. */
#ifdef SDT
#  define DMA_DEV_ID  XPAR_XAXIDMA_0_BASEADDR   /* note the X: SDT naming */
#else
#  define DMA_DEV_ID  XPAR_AXIDMA_0_DEVICE_ID
#endif

static uint32_t tx_buf[N_WORDS] __attribute__((aligned(64)));
static uint32_t rx_buf[N_WORDS] __attribute__((aligned(64)));

static XAxiDma dma;

/* Own console writer, replacing xil_printf's outbyte.
 *
 * Observed on this ZedBoard (silicon rev 1.0): the BSP's outbyte loses
 * exactly every second character -- it polls TXFULL and writes while the
 * previous byte is still in the single-deep path, overwriting it. Bytes
 * pushed by hand from the debugger with no pacing all arrive, so the
 * hardware is fine; the flag semantics on this rev are not what the BSP
 * expects. Waiting for TXEMPTY before every byte is slow (~90 us/char) but
 * cannot lose data, and we only print a few hundred bytes. */
#define UART1_BASE   0xE0001000u
#define UART_SR      (*(volatile uint32_t *)(UART1_BASE + 0x2C))
#define UART_FIFO    (*(volatile uint32_t *)(UART1_BASE + 0x30))
#define SR_TXEMPTY   (1u << 3)

static void putc_safe(char c) {
    while (!(UART_SR & SR_TXEMPTY)) { }
    UART_FIFO = (uint32_t)(uint8_t)c;
    while (!(UART_SR & SR_TXEMPTY)) { }
}
static void puts_safe(const char *s) {
    while (*s) { if (*s == '\n') putc_safe('\r'); putc_safe(*s++); }
}
static void puthex_safe(uint32_t v) {
    static const char h[] = "0123456789abcdef";
    for (int i = 28; i >= 0; i -= 4) putc_safe(h[(v >> i) & 0xF]);
}
static void putdec_safe(uint32_t v) {
    char b[11]; int n = 0;
    do { b[n++] = '0' + v % 10; v /= 10; } while (v);
    while (n) putc_safe(b[--n]);
}

static uint32_t xorshift32(uint32_t *s) {
    uint32_t x = *s; x ^= x << 13; x ^= x >> 17; x ^= x << 5; return *s = x;
}

static int wait_idle(int direction, const char *what) {
    uint32_t n = 0;
    while (XAxiDma_Busy(&dma, direction)) {
        if (++n > TIMEOUT_LOOP) {
            puts_safe("TIMEOUT waiting for "); puts_safe(what); puts_safe("\n");
            return XST_FAILURE;
        }
    }
    return XST_SUCCESS;
}

int main(void) {
    XAxiDma_Config *cfg;
    uint32_t seed = 0x2545F491u, i, bad = 0;

    int st;
    puts_safe("\n=== snn_parkour_fpga : M4 stage A loopback (bare metal) ===\n");

    cfg = XAxiDma_LookupConfig(DMA_DEV_ID);
    if (!cfg) { puts_safe("FAIL: no DMA config for 0x"); puthex_safe((uint32_t)DMA_DEV_ID); puts_safe("\n"); return 1; }
    puts_safe("DMA at 0x"); puthex_safe((uint32_t)cfg->BaseAddr);
    puts_safe("  SG="); putdec_safe(cfg->HasSg);
    puts_safe(" mm2s="); putdec_safe(cfg->HasMm2S);
    puts_safe(" s2mm="); putdec_safe(cfg->HasS2Mm); puts_safe("\n");
    /* raw peek before the driver touches it: MM2S_DMASR / S2MM_DMASR */
    puts_safe("MM2S_DMASR=0x"); puthex_safe(*(volatile uint32_t *)(cfg->BaseAddr + 0x04));
    puts_safe(" S2MM_DMASR=0x"); puthex_safe(*(volatile uint32_t *)(cfg->BaseAddr + 0x34)); puts_safe("\n");

    st = XAxiDma_CfgInitialize(&dma, cfg);
    if (st != XST_SUCCESS) {
        puts_safe("FAIL: DMA init, status "); putdec_safe((uint32_t)st);
        puts_safe("  (MM2S_DMASR=0x"); puthex_safe(*(volatile uint32_t *)(cfg->BaseAddr + 0x04));
        puts_safe(")\n"); return 1;
    }
    if (XAxiDma_HasSg(&dma)) {
        puts_safe("FAIL: DMA built in scatter-gather mode; untick SG in Vivado\n");
        return 1;
    }
    puts_safe("DMA init ok\n");
    /* polled mode: no interrupts to wire up */
    XAxiDma_IntrDisable(&dma, XAXIDMA_IRQ_ALL_MASK, XAXIDMA_DEVICE_TO_DMA);
    XAxiDma_IntrDisable(&dma, XAXIDMA_IRQ_ALL_MASK, XAXIDMA_DMA_TO_DEVICE);

    for (i = 0; i < N_WORDS; i++) { tx_buf[i] = xorshift32(&seed); rx_buf[i] = 0; }

    Xil_DCacheFlushRange((UINTPTR)tx_buf, N_WORDS * 4);   /* to DDR before DMA reads */
    Xil_DCacheFlushRange((UINTPTR)rx_buf, N_WORDS * 4);   /* push the zeros out too  */

    /* arm receive FIRST, then send -- same order as the PYNQ script      */
    if (XAxiDma_SimpleTransfer(&dma, (UINTPTR)rx_buf, N_WORDS * 4,
                               XAXIDMA_DEVICE_TO_DMA) != XST_SUCCESS) {
        puts_safe("FAIL: rx transfer setup\n"); return 1;
    }
    if (XAxiDma_SimpleTransfer(&dma, (UINTPTR)tx_buf, N_WORDS * 4,
                               XAXIDMA_DMA_TO_DEVICE) != XST_SUCCESS) {
        puts_safe("FAIL: tx transfer setup\n"); return 1;
    }

    /* hang here -> DMA can't reach DDR (HP0 not enabled / not connected) */
    if (wait_idle(XAXIDMA_DMA_TO_DEVICE, "send (MM2S)") != XST_SUCCESS) return 1;
    /* hang here -> stream never came back (wiring / TLAST)               */
    if (wait_idle(XAXIDMA_DEVICE_TO_DMA, "receive (S2MM)") != XST_SUCCESS) return 1;

    Xil_DCacheInvalidateRange((UINTPTR)rx_buf, N_WORDS * 4); /* see what DMA wrote */

    for (i = 0; i < N_WORDS; i++)
        if (rx_buf[i] != tx_buf[i]) {
            if (bad < 5) {
                puts_safe("  mismatch["); putdec_safe(i); puts_safe("]: got 0x");
                puthex_safe(rx_buf[i]); puts_safe(" expected 0x"); puthex_safe(tx_buf[i]);
                puts_safe("\n");
            }
            bad++;
        }

    if (bad == 0) {
        puts_safe("LOOPBACK PASS: "); putdec_safe(N_WORDS);
        puts_safe(" words round-tripped bit-identical\n");
    } else {
        puts_safe("LOOPBACK FAIL: "); putdec_safe(bad); puts_safe(" of ");
        putdec_safe(N_WORDS); puts_safe(" words differ\n");
    }

    return bad ? 1 : 0;
}
