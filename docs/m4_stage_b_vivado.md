# M4 Stage B — swap the FIFO for the real engine

Do this only after Stage A's `LOOPBACK PASS`. It edits the working loopback
project, so every unfamiliar piece (toolchain, board, DMA) is already proven;
anything that breaks from here is the engine integration, which narrows
debugging enormously.

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

## 4. Bitstream and files

Generate Bitstream (same as Stage A; this one takes a little longer).
Collect and rename **`conv.bit`** + **`conv.hwh`**:

| What | Where |
|---|---|
| `design_1_wrapper.bit` | `<project>.runs/impl_1/` |
| `design_1.hwh` | `<project>.gen/sources_1/bd/design_1/hw_handoff/` |

## 5. On the board

Upload to Jupyter: `conv.bit`, `conv.hwh`, `host/conv_test.py`,
`host/conv_test_data.npz` (generate the npz on the Mac with
`python3 host/make_conv_test_data.py` if it isn't in the repo copy).

```python
%run conv_test.py
```

**M4's done-when:** `HARDWARE PASS ... bit-identical to the golden model on
real silicon.` — the same 9,280-word comparison the simulation testbench
makes, now against the physical chip.

## If it fails where simulation passed

The vectors are identical to the passing sim run, so the differences are
environmental. In rough order of likelihood:

1. **Weight hex missed synthesis** — output is consistent junk. Re-check
   step 2.3; look for `$readmemh` warnings in the synthesis log.
2. **recvchannel.wait() hangs** — engine never finished. Check the reset
   polarity wiring (aresetn, not a raw reset net) and that connection
   automation actually connected `aclk`.
3. **Sporadic wrong words** — would suggest a timing failure; check
   Vivado's timing summary says all constraints met (at 100 MHz this design
   should meet timing trivially; if FCLK0 got set higher, drop it to 100).
