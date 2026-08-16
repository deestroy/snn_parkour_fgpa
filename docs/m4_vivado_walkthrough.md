# M4 Stage A — first overlay, step by step (Windows VM + PYNQ-Z2)

Goal of this stage: build a **loopback** overlay — Python sends a buffer to
the fabric over DMA, a FIFO hands it straight back, Python checks it returned
intact. **No custom RTL is involved.** This proves the toolchain, the board,
the SD image, the network and the DMA machinery, so that when our real engine
goes in (Stage B) any new failure belongs to the engine, not the plumbing.

You drive the Vivado GUI; this document is the map. Where a click matters, it
is spelled out. Each numbered section ends with a **Checkpoint** — do not move
on until it holds. Jargon is defined at first use.

---

## 0. What you need before starting

- [ ] Windows VM with Vivado installed. Check the version: open Vivado, then
      `Help > About`. Anything 2020.2 or newer is fine for this flow.
      (Zynq-7020 is covered by the free licence tier — no licence action
      needed. If Vivado ever asks about licences for this chip, something
      else is wrong.)
- [ ] PYNQ-Z2 board, microSD card (8 GB or more), micro-USB cable.
- [ ] Ethernet cable from the board to your router (easiest), or directly to
      a computer (workable, needs a static-IP step noted in §6).
- [ ] A way to move files between this repo and the VM (shared folder, git,
      or even a USB stick). And from your Mac/VM to the board — that happens
      through the browser, no tools needed.

---

## 1. One-time: PYNQ-Z2 board definition into Vivado

Vivado doesn't know this board out of the box. A "board file" teaches it the
part number, pin names and the processing-system preset.

1. Download the PYNQ-Z2 board file zip from the TUL website
   (search "PYNQ-Z2 board file" — the file is `pynq-z2.zip`, a few KB).
2. Unzip. You get a folder `pynq-z2` containing `board.xml`.
3. Copy that folder into Vivado's board directory. Depending on version it is
   one of:
   - `C:\Xilinx\Vivado\<version>\data\boards\board_files\`
   - `C:\Xilinx\Vivado\<version>\data\xhub\boards\XilinxBoardStore\boards\Xilinx\`
   If `board_files` exists under `data\boards\`, use that one.
4. Restart Vivado.

**Checkpoint:** `File > Project > New`, click through to the "Default Part"
page, select the **Boards** tab, search "pynq". `PYNQ-Z2` appears.

*(If the board file refuses to appear: fall back to the Parts tab and pick
`xc7z020clg400-1`. Everything below still works — the board file is a
convenience, not a requirement, because the SD image configures the chip's
DDR at boot regardless.)*

---

## 2. Create the project

1. `File > Project > New` → name `m4_loopback`, location anywhere in the VM,
   **RTL Project**, "Do not specify sources at this time".
2. Part/board page: select the PYNQ-Z2 board (or the part, per §1 fallback).
3. Finish.

**Checkpoint:** empty project open, part shown bottom-right is
`xc7z020clg400-1`.

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
| `design_1_wrapper.bit` | `m4_loopback.runs/impl_1/` |
| `design_1.hwh` | `m4_loopback.gen/sources_1/bd/design_1/hw_handoff/` |

Copy both out and **rename to the same basename**: `loopback.bit` and
`loopback.hwh`. PYNQ finds the .hwh by the .bit's name — a mismatched name is
the single most common first-overlay failure.

**Checkpoint:** two files, same basename, different extensions.

---

## 5. One-time: flash the SD card

1. On any machine: download the **PYNQ-Z2 v3.0.1 image** from pynq.io
   (Boards → PYNQ-Z2). ~2 GB zip.
2. Flash the unzipped `.img` to the microSD with **Balena Etcher** (or
   Rufus). This erases the card.
3. Board switches (silkscreen labels on the board):
   - Boot jumper (near SD slot) → **SD**
   - Power jumper → **USB** (powering from the micro-USB cable is fine here)
4. Insert SD, connect Ethernet, connect micro-USB to any powered USB port,
   flip the power switch.

**Checkpoint:** the red PWR LED comes on immediately; within ~60 s the
**green DONE LED** lights and two blue LEDs flash — that is PYNQ saying the
boot completed.

---

## 6. Reach Jupyter

- Router case: browse to `http://pynq:9090` (or find the board's IP in your
  router's device list and use `http://<ip>:9090`).
- Direct-cable case: set your computer's Ethernet adapter to static IP
  `192.168.2.1`, netmask `255.255.255.0`; the board is at `192.168.2.99`;
  browse to `http://192.168.2.99:9090`.
- Password: `xilinx`.

**Checkpoint:** Jupyter file listing in the browser.

---

## 7. Run the loopback test

1. In Jupyter, upload `loopback.bit`, `loopback.hwh`, and
   `host/loopback_test.py` from this repo (Upload button, top right).
2. New notebook → single cell:

   ```python
   %run loopback_test.py
   ```

**Checkpoint — and Stage A's done-when:** it prints `LOOPBACK PASS` with a
throughput number. That line means: bitstream built in the VM, loaded from
Jupyter, and 100k words made the round trip CPU → DDR → DMA → fabric → DMA →
DDR → CPU intact.

---

## 8. When something goes wrong (the four classic failures)

| Symptom | Likely cause | Fix |
|---|---|---|
| `Overlay` load complains about .hwh | basename mismatch | §4 rename step |
| Notebook hangs at `sendchannel.wait()` | DMA can't reach DDR | §3 step 5 (HP0) skipped, or connection automation not re-run |
| Hangs at `recvchannel.wait()` | stream never terminated | FIFO not in the path / TLAST not passed — check §3 step 6 wiring direction |
| Board boots but no Jupyter | network, not board | §6 other case; try `ping pynq` / router list; give it a full 2 min |

If a failure isn't in this table: photograph the block design + the error and
bring it back to me; that context is usually enough to pinpoint it.

---

## What happens in Stage B (next, after PASS)

The FIFO comes out; an AXI-Stream wrapper around our verified C1 engine goes
in. That wrapper and its simulation testbench are my job and land in the repo
before you open Vivado again — the Vivado steps will be a shorter repeat of
§3–§4 with one extra "Add Sources" step for our Verilog files.
