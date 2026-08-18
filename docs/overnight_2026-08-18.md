# Overnight report — night of 2026-08-17 → 18

Read this first. It covers everything that changed while you slept, every
retraction, and the one architectural consequence. Details and register
evidence are in `docs/decisions.md` (D0015 board-day log, parts 1–5 + DDR
note); this is the digest.

---

## The headline

**`LOOPBACK PASS: 12288 words round-tripped bit-identical`**

Your ZedBoard ran the loopback program, streamed 48 KB out through the
FPGA fabric via DMA and back, and every word matched. Programmed and
observed entirely from the Mac — no Vitis or Windows at run time.
**M4 Stage A's done-when is met.** The full console output:

```
=== snn_parkour_fpga : M4 stage A loopback (bare metal) ===
DMA at 0x40400000  SG=0 mm2s=1 s2mm=1
MM2S_DMASR=0x00000001 S2MM_DMASR=0x00000001
DMA init ok
LOOPBACK PASS: 12288 words round-tripped bit-identical
```

## What was actually wrong (one thing, five disguises)

`reset halt` asserts SRST. On Zynq, SRST leaves the PL's **PROGRAM_B line
held low** (`devcfg.CTRL[PCFG_PROG_B] = 0`) — the fabric is held cleared.
My loader then ran `pld load`, which streamed the bitstream into a fabric
that silently discarded it. Every symptom of the night followed from that:

| what we saw | what it actually was |
|---|---|
| CPU and debugger "see different DMA registers" | both reading an unconfigured PL; stable garbage differing by path |
| first PL write hangs the bus / wedges the DAP | no slave to return the write response |
| console lost every 2nd character | my own "disable the L2 filter" fix, which misrouted peripherals |
| "no UART enabled" → Vivado rebuild | reads through the running program's MMU; all zeros, all junk |
| "BSP outbyte drops bytes" | same L2-filter mistake in a different disguise |

The very first load of the evening had lit the DONE LED because it followed
a plain `halt`, not an SRST. I never registered the difference.

**Fix (in `host/mac/zynq_load.tcl`):** pulse `PCFG_PROG_B` low→high after
`ps7_init`, then `pld load`, then `ps7_post_config` — the xsct/FSBL order.
Verified with a DMA register write completing and reading back changed,
then the program running to PASS. Reproducible from a clean reset.

## Retractions (all recorded in decisions.md)

- **The L2 address filter was innocent.** UG585 confirms its reset value
  (start 0x40000000 enabled, end 0xFFF00000) is correct: DDR → M0,
  everything else → M1. Neither `boot.S`, the FSBL, nor `ps7_init` touch it.
  My "disable it" change broke peripheral routing; reverted.
- **UART was enabled all along.** The Vivado UART1 round trip was
  unnecessary (harmless — the design is certainly correct now).
- **The BSP's `xil_printf` was not dropping bytes.** My paced UART writer
  in `loopback.c` is kept anyway: it gives the program a
  library-independent diagnostics path and is simple.
- **The `bsp.yaml` stdout → `ps7_uart_1` change WAS real and necessary** —
  the ELF really did reference UART0 before it. Keep it.

## Everything that changed in the repo (all committed, nothing pushed)

| file | change |
|---|---|
| `host/mac/zynq_load.tcl` | PROG_B release; Xilinx ordering (init → PROG_B → bitstream → post_config → ELF); L2-filter write removed; `mrd` shim shape fixed |
| `host/board/loopback.c` | own paced UART writer replacing `xil_printf`; prints DMA config + raw status before init; `N_WORDS = 12288` (OCM, see below) |
| `host/mac/uart_capture.py` | new: capture the board's UART to a file for N seconds |
| `host/mac/program.sh` | unchanged in substance |
| `docs/decisions.md` | D0015 board-day log parts 1–5, DDR note; every retraction |
| `docs/m4_vivado_walkthrough.md` | UART-1 verification step in §3 (still worth having) |

Commits since you slept: `Board-day part 4` … `M4 stage A: LOOPBACK PASS`
… `DDR: characterised …`. `git log` shows them all.

## DDR — not resolved, and it matters (this is the architectural item)

With everything else correct, DDR **still does not retain data**: CPU
writes wedge the core, debugger writes bus-fault, reads return 0 — while
every controller-side status reports healthy (PLLs locked, DDRC in normal
mode with init done, DCI calibrated, PHY trained). That's the signature of
a PHY that cannot talk to the DRAM chips.

Evidence points at **rev-1.0 (2012 engineering-sample-era) XC7Z020
silicon**: DDRC register `0xF8006078` bus-faults on a plain read on fresh
silicon — it exists on rev 2.0/3.0 (whose init tables write it) and not
here — and MCTRL/IDCODE report rev 0. Rev-1.0 has known DDR limitations.
Consistent with a Rev-C ZedBoard from 2012–13.

**Consequence: the design lives in the 192 KB OCM until proven otherwise.**
This is a real architectural constraint, so stating it plainly:
- **Stage B is not blocked.** The C1 conv test needs ~4.6 KB/sample plus
  code — fits comfortably. FC traffic is smaller still.
- **M5/M7 sweeps** must stream samples one at a time from the host —
  which UART throughput forces anyway. No design change.
- **The 100,000-word buffer revert stays deferred**; `N_WORDS = 12288`
  and `loopback.c` says why. Revert instructions unchanged (D0015 note).
- If DDR is ever confirmed dead, the thesis methodology should say the
  board's DRAM was unavailable and all on-chip claims were, if anything,
  *stricter* than planned. Not a weakness — arguably cleaner.

**Two things only you can do to settle it (both in Vitis):**
1. **Build the FSBL** — `File > New Component > Application` → on
   `zed_platform` → template **Zynq FSBL** → Finish → Build (its own
   linker script already targets OCM; don't touch it). Copy
   `zynq_fsbl.elf` to `host/mac/build/fsbl.elf`. Then on the Mac:
   ```bash
   bash host/mac/run_fsbl.sh host/mac/build/fsbl.elf
   ```
   It skips our ps7_init (the FSBL runs its own C version, which carries
   silicon-rev workarounds the .tcl lacks), runs the FSBL, and prints its
   UART output. The FSBL says "DDR init …" and, if it fails, why. If it
   brings DDR up, the FSBL becomes our loader stage. ~10 minutes.
   *(Later finding, 03:30: the DDR PHY's DLLs are locked and trained —
   see decisions.md — so this test is genuinely the last discriminator.)*
2. If the FSBL fails too: DDR is hardware-dead on this board; we proceed
   on OCM with a clear conscience.

## Debugging rules that came out of tonight (in decisions.md)

1. Never trust CPU-side memory reads of a halted target that has run a
   program — its MMU is on. Read peripherals through the AHB-AP `mem_ap`.
2. When a program hangs on I/O, drive the peripheral by hand from the
   debugger first. If that works, the bug is in software addressing.
3. `devcfg.STATUS[PCFG_DONE]` and `MCTRL` read 0 over the debug port on
   this part regardless of truth; don't gate on them.
4. A wedged FTDI JTAG adapter (MPSSE assertion) recovers with a pyusb
   device reset — no replug needed.
5. Vitis 2024.1 BSP stdin/stdout live in the domain's `bsp.yaml`; the GUI
   is unreliable for it.

## What I did NOT do

- No Vivado or Vitis changes (couldn't, and wouldn't unasked).
- No push to GitHub — that's still yours.
- Did not start M6 step 1 or the Stage B C server: the DDR question
  determines buffer strategy for the C server, so it's better written
  after the FSBL check. Nothing about M6's design changed.

## Suggested first hour today

1. Read this. Skim decisions.md D0015 parts 4–5 if you want the register
   trail.
2. Vitis: build the FSBL, copy the `.elf`. I run it; we learn DDR's fate.
3. Then Stage B: swap the FIFO for the C1 engine in Vivado
   (`docs/m4_stage_b_vivado.md`), while I write the C server + Mac client
   sized for whichever memory we have.

Not a bad night: from "does any of this work" to a passing loopback with a
root cause, and a precise, testable question left over rather than a fog.
