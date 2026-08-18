# M4 Stage B — swap the FIFO for the real engine (bare metal, ZedBoard)

> Revised 2026-08-18 for the bare-metal/JTAG flow that passed Stage A. The
> Vivado part is unchanged; the software part is `conv_server.c` on the
> board and `uart_client.py` on the Mac instead of PYNQ.

Stage A passed (`LOOPBACK PASS`, 2026-08-18). This edits the working
loopback project, so every unfamiliar piece (toolchain, board, DMA, JTAG
loader, UART) is already proven; anything that breaks from here is the
engine integration, which narrows debugging enormously.

## 1. Files into the VM

From this repo, copy these five files somewhere the VM can see:

```
hdl/common/lif_update.v
hdl/dense/conv_layer.v
hdl/dense/axis_conv.v
hdl/dense/axis_conv_top.v
sim/vectors/conv_c1_w.hex     (generate first if missing:
                               python3 sim/export_conv_vectors.py --layer c1)
```

## 2. Add them to the project

1. Open the `m4_loopback` project (or File > Project > Save As to keep the
   loopback intact — recommended, name it `m4_conv`).
2. `Add Sources > Add or create design sources` → add the four `.v` files.
3. `Add Sources` again → **Add or create design sources** → add
   `conv_c1_w.hex` too (yes, as a design source — this is what lets
   `$readmemh("conv_c1_w.hex", ...)` find it during synthesis).

**Checkpoint:** the Sources panel shows `axis_conv_top` with the other
modules nested under it, no missing-module warnings.

## 3. Edit the block design

1. Open `design_1`. Right-click the `axis_data_fifo_0` block → Delete.
2. Right-click empty canvas → **Add Module...** → pick `axis_conv_top`.
   (This is the RTL-module flow — our port names and attributes make Vivado
   infer the two stream interfaces, the clock and the reset.)
3. Wire it where the FIFO was:
   - `axi_dma_0 : M_AXIS_MM2S` → `axis_conv_top_0 : s_axis`
   - `axis_conv_top_0 : m_axis` → `axi_dma_0 : S_AXIS_S2MM`
4. **Run Connection Automation** (twice if the banner reappears) — it wires
   `aclk` and `aresetn`. If no banner: connect `aclk` to the same clock pin
   the DMA uses (`s_axi_lite_aclk`'s net) and `aresetn` to the
   `peripheral_aresetn` of the reset block already on the canvas.
5. Validate (F6).

**Checkpoint:** validation clean. The design is DMA → our engine → DMA.

## 4. Bitstream and hardware export

Generate Bitstream (same as Stage A). Then `File > Export > Export Hardware`
with **Include bitstream** → a new `design_1_wrapper.xsa`. Collect for the
Mac (`host/mac/build/`, via Google Drive as before):

| file | where |
|---|---|
| `design_1_wrapper.bit` | `<project>.runs/impl_1/` |
| `design_1_wrapper.xsa` | wherever Export Hardware wrote it |

## 5. Vitis: the conv server

**Prerequisite (2026-08-18):** the block design must carry the **ZedBoard
preset** AND still have **S AXI HP0 enabled with the DMA masters mapped to
DDR in the Address Editor** — applying the preset silently clears HP0, and
the symptom is MM2S DMADecErr on the first transfer (seen 2026-08-18) (ZYNQ7 PS → Presets → ZedBoard; DDR part MT41J128M16). Without it
DDR silently loses data — that was two days of the log. Since the platform
was recreated from that corrected .xsa, DDR works and apps use the
**default** linker script (DDR at 0x100000). No OCM edit.

1. New application `conv_server` on `zed_platform` (empty app, as before).
2. Add `host/board/conv_server.c` under its `src/`.
3. Leave `lscript.ld` as generated (DDR). Buffers are 2 x 256 KB.
4. Build. Copy `conv_server.elf` to `host/mac/build/`.
5. **Preferred run mode — boot from SD, no debugger:** `conv_server` →
   **Create Boot Image** (FSBL from the recreated platform, the new
   `.bit`, `conv_server.elf`) → `BOOT.BIN` → copy over; the Mac writes the
   card. Jumpers 00110, power on, and the board comes up serving. The
   FSBL's debug output on the console confirms each stage.

## 6. On the Mac

If booted from SD (preferred): nothing to program — just run the client
once the board is up (it PINGs first, then streams 16 golden samples and
compares every returned word):
```bash
python3 host/uart_client.py
```
If instead loading over JTAG: `bash host/mac/stage_b.sh` (extracts
ps7_init from the .xsa, programs bitstream + ELF, runs the client). Note
the JTAG path's ps7_init.tcl must come from the CORRECTED .xsa or DDR
will not work.

**M4's done-when:** `BOARD PASS: 16 samples, 9280 words, bit-identical to
the golden model` — the same 9,280-word comparison the simulation testbench
makes and the mock server passes, now against the physical chip.

## If it fails where simulation and the mock passed

The vectors and the client are identical to the passing mock run
(`python3 host/mock_server.py --selftest`), so the differences are the
engine on silicon and the C server. In rough order of likelihood:

1. **`board error: DMA timeout`** — engine never produced 580 words. The
   AXIS wrapper's tlast/handshake on real hardware, or the DMA S2MM length.
   Check the block design wiring direction (§3) and that connection
   automation connected `aclk`/`aresetn` to the engine.
2. **Words WRONG, consistently** — weight hex didn't make it into synthesis
   (`$readmemh` warning in the Vivado log; step 2.3), or the engine's
   parameters in `axis_conv_top.v` don't match C1.
3. **No PING reply at all** — server not running: check `program.sh`
   output ended in "running", and that the ELF was linked to OCM (entry
   0x00000000; `python3 -c` check in `program.sh` prints it).
4. **`link: crc mismatch` from the client** — UART byte loss. Should not
   happen at 115200 with the paced writer; if it does, the client's
   `drain()` + retry is the workaround and the cause is worth a look.
