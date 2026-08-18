# M4 Stage A — first overlay, step by step (Windows VM + ZedBoard, bare metal)

> **Board note (D0014/D0015):** written for the PYNQ-Z2, revised for the
> ZedBoard that actually arrived. Same Zynq-7020 chip. Because no PYNQ image
> exists for the ZedBoard, the board runs a **bare-metal C program built in
> Vitis** instead of Linux + Jupyter (D0015). §1–§4 (Vivado) are unchanged
> from the PYNQ plan; §5 onward is the Vitis flow.

Goal of this stage: build a **loopback** design — a C program on the ARM
sends a buffer to the fabric over DMA, a FIFO hands it straight back, the
program checks it returned intact and reports over the USB serial port. **No custom RTL is involved.** This proves the toolchain, the board,
the SD image, the network and the DMA machinery, so that when our real engine
goes in (Stage B) any new failure belongs to the engine, not the plumbing.

You drive the Vivado GUI; this document is the map. Where a click matters, it
is spelled out. Each numbered section ends with a **Checkpoint** — do not move
on until it holds. Jargon is defined at first use.

---

## 0. What you need before starting

- [ ] Windows VM with **Vivado 2024.1 and Vitis 2024.1** (both confirmed
      installed). Zynq-7020 is covered by the free licence tier.
- [ ] ZedBoard, microSD card (8 GB or more), micro-USB cable (for the UART
      port, optional but useful), and — **[ZedBoard]** — the **12 V barrel
      power supply**. The ZedBoard cannot run from USB power. No brick, no
      board day.
- [ ] **Two micro-USB cables** to the machine running Vitis: one to the
      **PROG** port (J17, USB-JTAG — programs the FPGA and loads the C
      program) and one to the **UART** port (J14 — the serial console the
      program prints to). No Ethernet, no SD card, no network setup.
- [ ] If Vitis runs in the VM, the VM must be able to see those USB devices
      (VirtualBox/VMware: USB passthrough — attach "Digilent" or "FTDI"
      devices to the VM once they enumerate).
- [ ] A way to move files between this repo and the VM (shared folder, git,
      or a USB stick).

---

## 1. Board definition **[ZedBoard]** — nothing to install

The ZedBoard's board file ships inside Vivado. Skip the download-and-copy
dance entirely.

**Checkpoint:** `File > Project > New`, click through to the "Default Part"
page, select the **Boards** tab, search "zed". `ZedBoard Zynq Evaluation and
Development Kit` appears. (Fallback if it somehow doesn't: Parts tab,
`xc7z020clg484-1` — note **clg484**, the ZedBoard's package, not the
PYNQ-Z2's clg400.)

---

## 2. Create the project

1. `File > Project > New` → name `m4_loopback_zed`, location anywhere in the
   VM, **RTL Project**, "Do not specify sources at this time".
   **[ZedBoard]** Make a NEW project rather than reusing the PYNQ-Z2 one:
   the processing-system preset (DDR timing, clocks, peripherals) is
   board-specific and baked in when block automation runs.
2. Part/board page: **Boards** tab → **ZedBoard**.
3. Finish.

**Checkpoint:** empty project open, part shown bottom-right is
`xc7z020clg484-1`.

---

## 3. The block design (all clicking, no code)

A "block design" is Vivado's graphical canvas for wiring pre-made IP blocks
("IP" = intellectual property block = someone else's finished module).

1. Flow Navigator (left) → `IP INTEGRATOR > Create Block Design`. Accept the
   default name `design_1`.
2. Press the **+** button (or Ctrl+I) and add, one at a time:
   - **ZYNQ7 Processing System** — the ARM cores ("PS"). Everything else on
     the chip is the fabric ("PL").
   - **AXI Direct Memory Access** — the DMA engine.
   - **AXIS Data FIFO** — our stand-in accelerator: a first-in-first-out
     queue that returns whatever it is fed.
3. A green banner appears: **Run Block Automation**. Click it, accept
   defaults, OK. (This applies the board preset to the PS — clocks, DDR.)
   **[ZedBoard]** This step is exactly why a fresh project was needed: the
   preset it applies is the ZedBoard's.
4. Configure the DMA: double-click `axi_dma_0`:
   - **Untick "Enable Scatter Gather Engine"** (we use simple mode).
   - Width of buffer length register: set to **26**.
   - Leave both channels (read = memory→stream, write = stream→memory) on.
   - OK.
5. Configure the PS for DMA traffic: double-click the ZYNQ block →
   `PS-PL Configuration > HP Slave AXI Interface` → tick **S AXI HP0
   interface**. OK. (HP = high performance port — how the DMA reaches DDR.)
6. Wire the streams (drag from pin to pin):
   - `axi_dma_0 : M_AXIS_MM2S`  →  `axis_data_fifo_0 : S_AXIS`
   - `axis_data_fifo_0 : M_AXIS` →  `axi_dma_0 : S_AXIS_S2MM`
   (MM2S = "memory-mapped to stream" = the send direction; S2MM = receive.)
7. Green banner again: **Run Connection Automation** → tick "All Automation"
   → OK. Run it twice if the banner reappears — it wires up AXI
   interconnects, clocks and resets.
8. `Tools > Validate Design` (F6).

**Checkpoint:** validation reports no errors (warnings about unused DMA
status streams are fine).

---

## 4. Bitstream

1. Sources panel → right-click `design_1` → **Create HDL Wrapper** → "Let
   Vivado manage". (The wrapper is a one-file Verilog shell around the block
   design — the actual top level.)
2. Flow Navigator → **Generate Bitstream**. Accept "launch synthesis and
   implementation first". This is the long step: 10–25 minutes in a VM.
3. When it finishes, dismiss the "open implemented design" dialog.

Collect exactly two files (paths relative to the project folder):

| What | Where |
|---|---|
| `design_1_wrapper.bit` | `m4_loopback_zed.runs/impl_1/` |
| `design_1.hwh` | `m4_loopback_zed.gen/sources_1/bd/design_1/hw_handoff/` |

(Those two files were what PYNQ wanted. **On the bare-metal path they are
not needed** — keep them for reference only.) What Vitis wants instead:

4. `File > Export > Export Hardware...` → **Include bitstream** → Next →
   note the output path → Finish. This writes `design_1_wrapper.xsa`: the
   whole hardware description plus the bitstream, in one file.

**Checkpoint:** `design_1_wrapper.xsa` exists (a few MB).

---

## 5. Board setup **[ZedBoard, bare metal]**

1. Boot-mode jumpers **JP7–JP11 = 0 0 0 0 0** — all toward GND. That is
   **JTAG boot**: the board waits for Vitis to load it over USB. (This is
   different from the SD-boot setting a PYNQ board would use.)
2. Plug the **12 V brick** into the barrel jack. Connect **both** micro-USB
   cables (PROG J17 and UART J14) to the Vitis machine. Power switch SW8 on.

**Checkpoint:** green power LED (LD13) on. The blue DONE LED (LD12) stays
OFF — correct: nothing is programmed yet. In Windows Device Manager two
new serial/USB devices appear (a "Digilent USB Device" and a COM port).

---

## 6. Vitis: platform + application

Vitis is the software side of the Xilinx suite: it takes the .xsa, builds
the drivers for exactly the hardware in it (the "platform"), and compiles C
against them.

1. Launch **Vitis 2024.1** (Vitis Unified IDE). Choose a workspace folder
   (any empty folder).
2. `File > New Component > Platform` → name `zed_platform` → **Hardware
   Design: browse to `design_1_wrapper.xsa`** → OS **standalone**, processor
   **ps7_cortexa9_0** → Finish. Then **Build** the platform (hammer icon;
   ~1–2 min). Standalone = bare metal = no OS.
3. `File > New Component > Application` → name `loopback` → select the
   platform you just built → template **Hello World** → Finish.
4. In the Explorer, open `loopback/src/helloworld.c`. **Delete its
   contents and paste in `host/board/loopback.c` from this repo** (or drop
   the file in and delete helloworld.c). Build the application.

**Checkpoint:** application builds with 0 errors. If it complains about
`XPAR_AXIDMA_0_DEVICE_ID`, the DMA isn't in the .xsa — re-export from
Vivado after a fresh Generate Bitstream. Anything else, paste the error to
me: this file was written without a compiler and the first build is its
test.

---

## 7. Run it

1. Open a serial terminal on the UART COM port at **115200 baud, 8N1**
   (Vitis has one built in: the *Serial Monitor* / *Vitis Serial Terminal*
   view — pick the COM port that appeared in §5, set 115200. PuTTY or Tera
   Term work equally well.)
2. Right-click the `loopback` application → **Run As > Launch Hardware**.
   Vitis programs the FPGA with the bitstream (blue DONE LED lights),
   initialises the ARM, downloads the ELF, and starts it.
3. Watch the serial terminal.

**Checkpoint — and Stage A's done-when:** the terminal prints
`LOOPBACK PASS: 100000 words round-tripped bit-identical`. That line means:
bitstream built in Vivado, platform and app built in Vitis, board
programmed over JTAG, and 400 KB made the round trip CPU → DDR → DMA →
fabric → DMA → DDR → CPU intact, with the cache handling right.

---

## 8. When something goes wrong (the classic failures, bare-metal edition)

| Symptom | Likely cause | Fix |
|---|---|---|
| Nothing on the serial terminal at all | wrong COM port or baud, or terminal opened after the program already printed | 115200; pick the other COM port; re-Run |
| `TIMEOUT waiting for send (MM2S)` | DMA can't reach DDR | §3 step 5 (HP0) skipped, or connection automation not re-run — fix in Vivado, re-export .xsa, rebuild platform |
| `TIMEOUT waiting for receive (S2MM)` | stream never came back | FIFO wiring direction (§3 step 6), TLAST |
| `LOOPBACK FAIL: N words differ`, N small and scattered | cache | the two `Xil_DCache*` calls are present? buffers 64-byte aligned? |
| `LOOPBACK FAIL`, most words differ | data width mismatch | FIFO TDATA width vs DMA (32-bit) — §3 |
| Vitis can't find the board | USB passthrough | attach the Digilent JTAG device to the VM; check Device Manager |
| DONE LED never lights on Run | jumpers | JP7–JP11 must be all 0 (JTAG boot) |

If a failure isn't in this table: paste the terminal output and the Vitis
error, plus a screenshot of the block design, and we'll pinpoint it.

---

## What happens in Stage B (next, after PASS)

The FIFO comes out; the verified AXI-Stream wrapper around our C1 engine
goes in (already in the repo: `hdl/dense/axis_conv_top.v` and friends). The
Vivado steps are a short repeat of §3–§4 with one "Add Sources" step; then a
new C program (`host/board/conv_server.c`) streams golden samples through the
engine and a Python client on the Mac (`host/uart_client.py`) feeds it and
compares against the golden model over the serial port. See
`docs/m4_stage_b_vivado.md`.
