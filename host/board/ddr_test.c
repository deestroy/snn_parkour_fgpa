/*
 * DDR self-test, run BY THE PROGRAM, not the debugger.
 *
 * Every DDR test so far went through JTAG (my Tcl init, then the FSBL, with
 * the debugger doing the reads/writes). That path misled us four times last
 * night, so its verdict on DDR is suspect. This program is linked into OCM
 * (loads and runs exactly like loopback.c did) and exercises DDR as ordinary
 * data from the CPU, the way any real program would. It reports over UART.
 *
 * If it prints DDR PASS: DDR is fine, the debugger was lying, and the
 * conv/loopback buffers can move back to DDR at full size.
 * If it prints DDR FAIL with a pattern: DDR is really faulty and the error
 * pattern (which bits, which addresses) says something about how.
 *
 * Build: like loopback.c (paste over the app source, lscript.ld -> ps7_ram_0).
 */

#include <stdint.h>
#include "xil_cache.h"

#define UART1_BASE   0xE0001000u
#define UART_SR      (*(volatile uint32_t *)(UART1_BASE + 0x2C))
#define UART_FIFO    (*(volatile uint32_t *)(UART1_BASE + 0x30))
#define SR_TXEMPTY   (1u << 3)

static void putc_safe(char c) {
    while (!(UART_SR & SR_TXEMPTY)) { }
    UART_FIFO = (uint32_t)(uint8_t)c;
    while (!(UART_SR & SR_TXEMPTY)) { }
}
static void puts_safe(const char *s) { while (*s) { if (*s=='\n') putc_safe('\r'); putc_safe(*s++); } }
static void puthex(uint32_t v) { static const char h[]="0123456789abcdef"; for (int i=28;i>=0;i-=4) putc_safe(h[(v>>i)&0xF]); }
static void putdec(uint32_t v) { char b[11]; int n=0; do { b[n++]='0'+v%10; v/=10; } while (v); while (n) putc_safe(b[--n]); }

/* Test regions: a few spots across the 512 MB. Small enough to be quick,
 * spread enough to catch an address-line fault. */
static const uint32_t bases[] = { 0x00100000u, 0x01000000u, 0x08000000u, 0x10000000u, 0x1FF00000u };
#define REGION_WORDS 4096u   /* 16 KB per region */

static uint32_t test_region(uint32_t base, uint32_t seed, uint32_t *first_bad, uint32_t *bad_bits) {
    volatile uint32_t *p = (volatile uint32_t *)base;
    uint32_t x = seed, errs = 0;
    for (uint32_t i = 0; i < REGION_WORDS; i++) { x ^= x << 13; x ^= x >> 17; x ^= x << 5; p[i] = x; }
    Xil_DCacheFlushRange(base, REGION_WORDS * 4);       /* force to DRAM   */
    Xil_DCacheInvalidateRange(base, REGION_WORDS * 4);  /* force re-read   */
    x = seed;
    for (uint32_t i = 0; i < REGION_WORDS; i++) {
        x ^= x << 13; x ^= x >> 17; x ^= x << 5;
        uint32_t got = p[i];
        if (got != x) {
            if (errs == 0) { *first_bad = base + 4*i; }
            *bad_bits |= (got ^ x);
            errs++;
        }
    }
    return errs;
}

int main(void) {
    puts_safe("\n=== DDR self-test (program-driven, from OCM) ===\n");
    /* sanity: OCM itself, so we know the test logic works */
    { uint32_t fb=0, bb=0; uint32_t e = test_region(0x00030000u - REGION_WORDS*4, 0x1234567u, &fb, &bb);
      puts_safe("OCM control region: "); putdec(e); puts_safe(" errors\n"); }

    uint32_t total = 0, allbits = 0;
    for (unsigned r = 0; r < sizeof(bases)/sizeof(bases[0]); r++) {
        uint32_t fb = 0, bb = 0;
        uint32_t e = test_region(bases[r], 0x9E3779B9u + r, &fb, &bb);
        puts_safe("DDR 0x"); puthex(bases[r]); puts_safe(": ");
        putdec(e); puts_safe("/"); putdec(REGION_WORDS); puts_safe(" words bad");
        if (e) { puts_safe("  first 0x"); puthex(fb); puts_safe("  bad-bit mask 0x"); puthex(bb); }
        puts_safe("\n");
        total += e; allbits |= bb;
    }
    /* walking-ones on one word: distinguishes stuck bits from dead lanes */
    { volatile uint32_t *p = (volatile uint32_t *)0x00200000u; uint32_t stuck = 0;
      for (int b = 0; b < 32; b++) { *p = 1u << b; Xil_DCacheFlushRange(0x00200000u, 4); Xil_DCacheInvalidateRange(0x00200000u, 4);
                                     if (*p != (1u << b)) stuck |= 1u << b; }
      puts_safe("walking-1 bits failing: 0x"); puthex(stuck); puts_safe("\n"); }

    if (total == 0) puts_safe("DDR PASS: all regions retain data. The debugger was lying; DDR is usable.\n");
    else { puts_safe("DDR FAIL: "); putdec(total); puts_safe(" bad words, cumulative bad-bit mask 0x"); puthex(allbits); puts_safe("\n"); }
    return 0;
}
