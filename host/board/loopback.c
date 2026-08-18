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

#define N_WORDS      (12288u)              /* 48 KB each way. TEMPORARY: shrunk
                                              from 100000 to fit OCM while DDR
                                              bring-up is unresolved. Revert
                                              per docs/decisions.md D0015.  */
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

static uint32_t xorshift32(uint32_t *s) {
    uint32_t x = *s; x ^= x << 13; x ^= x >> 17; x ^= x << 5; return *s = x;
}

static int wait_idle(int direction, const char *what) {
    uint32_t n = 0;
    while (XAxiDma_Busy(&dma, direction)) {
        if (++n > TIMEOUT_LOOP) {
            xil_printf("TIMEOUT waiting for %s\r\n", what);
            return XST_FAILURE;
        }
    }
    return XST_SUCCESS;
}

int main(void) {
    XAxiDma_Config *cfg;
    uint32_t seed = 0x2545F491u, i, bad = 0;

    xil_printf("\r\n=== snn_parkour_fpga : M4 stage A loopback (bare metal) ===\r\n");

    cfg = XAxiDma_LookupConfig(DMA_DEV_ID);
    if (!cfg) { xil_printf("FAIL: no DMA config for 0x%08x\r\n", (unsigned)DMA_DEV_ID); return 1; }
    if (XAxiDma_CfgInitialize(&dma, cfg) != XST_SUCCESS) {
        xil_printf("FAIL: DMA init\r\n"); return 1;
    }
    if (XAxiDma_HasSg(&dma)) {
        xil_printf("FAIL: DMA built in scatter-gather mode; untick SG in Vivado\r\n");
        return 1;
    }
    /* polled mode: no interrupts to wire up */
    XAxiDma_IntrDisable(&dma, XAXIDMA_IRQ_ALL_MASK, XAXIDMA_DEVICE_TO_DMA);
    XAxiDma_IntrDisable(&dma, XAXIDMA_IRQ_ALL_MASK, XAXIDMA_DMA_TO_DEVICE);

    for (i = 0; i < N_WORDS; i++) { tx_buf[i] = xorshift32(&seed); rx_buf[i] = 0; }

    Xil_DCacheFlushRange((UINTPTR)tx_buf, N_WORDS * 4);   /* to DDR before DMA reads */
    Xil_DCacheFlushRange((UINTPTR)rx_buf, N_WORDS * 4);   /* push the zeros out too  */

    /* arm receive FIRST, then send -- same order as the PYNQ script      */
    if (XAxiDma_SimpleTransfer(&dma, (UINTPTR)rx_buf, N_WORDS * 4,
                               XAXIDMA_DEVICE_TO_DMA) != XST_SUCCESS) {
        xil_printf("FAIL: rx transfer setup\r\n"); return 1;
    }
    if (XAxiDma_SimpleTransfer(&dma, (UINTPTR)tx_buf, N_WORDS * 4,
                               XAXIDMA_DMA_TO_DEVICE) != XST_SUCCESS) {
        xil_printf("FAIL: tx transfer setup\r\n"); return 1;
    }

    /* hang here -> DMA can't reach DDR (HP0 not enabled / not connected) */
    if (wait_idle(XAXIDMA_DMA_TO_DEVICE, "send (MM2S)") != XST_SUCCESS) return 1;
    /* hang here -> stream never came back (wiring / TLAST)               */
    if (wait_idle(XAXIDMA_DEVICE_TO_DMA, "receive (S2MM)") != XST_SUCCESS) return 1;

    Xil_DCacheInvalidateRange((UINTPTR)rx_buf, N_WORDS * 4); /* see what DMA wrote */

    for (i = 0; i < N_WORDS; i++)
        if (rx_buf[i] != tx_buf[i]) {
            if (bad < 5)
                xil_printf("  mismatch[%u]: got %08x expected %08x\r\n",
                           i, rx_buf[i], tx_buf[i]);
            bad++;
        }

    if (bad == 0)
        xil_printf("LOOPBACK PASS: %u words round-tripped bit-identical\r\n", N_WORDS);
    else
        xil_printf("LOOPBACK FAIL: %u of %u words differ\r\n", bad, N_WORDS);

    return bad ? 1 : 0;
}
