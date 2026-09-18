# Fresh Vivado project for the conv engine (written 2026-09-18)

Why: the m4_conv project accumulated stale copies of the HDL in
m4_loopback/, a duplicate-module warning, three open implemented designs
and two synthesis modes. A clean project referencing the git clone in
place removes the per-file copy step that nearly shipped a bitstream
without the C0044 fix.

Every setting below is transcribed from the .hwh of the dense P=4 x8
bitstream validated on silicon 2026-09-17 (archive/dense_p4_x8_20260917_2312),
not from memory. The build script's Mac-side check then diffs the new
project's .hwh against that one, so any missed setting shows up before
the card.

Names the build script relies on: project `m4_conv2` at
`C:/Users/dhritiaravind/m4_conv2/m4_conv2.xpr`, block design `design_1`,
wrapper `design_1_wrapper`, RTL block instance `axis_conv_top_0`, DMA
instance `axi_dma_0`. Keep them.

## 1. Project

File > Project > New. Name `m4_conv2`, location `C:/Users/dhritiaravind`,
RTL Project, "Do not specify sources at this time". Default Part page:
**Boards** tab, search "zed", pick **ZedBoard Zynq Evaluation and
Development Kit**. Finish.

Checkpoint: part bottom-right reads xc7z020clg484-1.

## 2. Sources — the ten files, referenced in place

Add Sources > Add or create design sources > Add Files. Select exactly
these ten (the dependency closure of axis_conv_top, i.e. the list the
Mac's lint ladder checks) under `C:\Users\dhritiaravind\snn_parkour_fpga\hdl\`:

    common\lif_update.v
    dense\axis_conv_top.v
    dense\axis_conv.v
    dense\conv_layer_p.v
    dense\conv_layer_p_c1.v
    dense\conv_layer_p_g1.v        (DVS-Gesture table, DATASET=1; C0012)
    eventdriven\ed_conv_layer.v
    eventdriven\ed_scatter.v
    eventdriven\ed_scatter_c1.v
    eventdriven\ed_scatter_g1.v    (DVS-Gesture table, DATASET=1; C0012)

**Untick "Copy sources into project"** (this is the whole point: a
`git pull` in the clone then updates the project). Finish. No .hex file:
weights are baked into the *_c1.v files (BAKED_WEIGHTS=1).

Checkpoint: Sources shows axis_conv_top at the top with the others
nested under it; no missing-module message; Ctrl+F `(C0044)` in
ed_conv_layer.v finds one hit at line 210.

## 3. Block design

IP INTEGRATOR > Create Block Design, name `design_1`. Add (the + button):
ZYNQ7 Processing System, AXI Direct Memory Access. Then right-click the
canvas > **Add Module...** > `axis_conv_top` (the RTL-module flow; its
port names make Vivado infer the two AXI-Stream interfaces, clock and
reset). The instance is named `axis_conv_top_0` automatically.

Run Block Automation (green banner), defaults, OK.

### 3a. ZYNQ7 PS — double-click it and set, in this order

1. **Presets > ZedBoard > Apply Configuration.** Then verify
   DDR Configuration > Memory Part = **MT41J128M16 HA-15E**.
   (Applying the preset resets the settings below, so do it first.)
2. Peripheral I/O Pins: **UART 1** ticked on **MIO 48..49**; UART 0
   unticked. **SD 0** ticked (SD boot needs it; the preset normally
   sets it — verify).
3. PS-PL Configuration > HP Slave AXI Interface: **S AXI HP0** ticked,
   data width **64**. General > M AXI GP0 stays ticked.
4. Clock Configuration > PL Fabric Clocks: **FCLK_CLK0 enabled, 100 MHz**
   (the cycle model and every latency number are at 100 MHz).
   APU 666.666667 MHz is the preset's value; leave it.
OK.

### 3b. AXI DMA — double-click it

- **Enable Scatter Gather Engine: unticked**
- Width of buffer length register: **26**
- Address width: 32
- Enable read channel (MM2S): ticked, data width 32, burst size 16,
  DRE unticked
- Enable write channel (S2MM): ticked, data width 32, burst size 16,
  DRE unticked
- Micro DMA unticked
OK.

### 3c. Wiring

- `axi_dma_0 : M_AXIS_MM2S`  ->  `axis_conv_top_0 : s_axis`
- `axis_conv_top_0 : m_axis` ->  `axi_dma_0 : S_AXIS_S2MM`

Run Connection Automation, tick All Automation, OK; run it again if the
banner reappears. It adds the AXI interconnects and the reset block and
wires aclk / aresetn to FCLK_CLK0 and the reset block's peripheral_aresetn.
If the RTL block's aclk or aresetn is left unconnected, wire them by
hand to the same nets the DMA uses.

### 3d. Address Editor tab

Three assignments must exist: axi_dma_0 S_AXI_LITE (register space, via
GP0), and both `axi_dma_0/Data_MM2S` and `axi_dma_0/Data_S2MM` mapped to
`processing_system7_0/S_AXI_HP0/HP0_DDR_LOWOCM` (the DDR). If any is
missing: Address Editor > Assign All. (The script re-checks this and
assigns if needed, but look once.)

Validate (F6). Checkpoint: no errors.

### 3e. Rule for a project that references the clone in place

After ANY `git pull` that touches hdl/, before building: open the block
design, right-click `axis_conv_top_0` > **Refresh Module Reference**,
save. The block keeps a snapshot of the module's ports and parameters;
a parameter added in the file (DATASET, 2026-09-18) is invisible to the
block until refreshed, and the script's read-back stops on it
("parameter DATASET reads back , wanted 0"). New files in the closure
(check_all.sh's lint line lists it) must be added to the project too.

## 4. Wrapper

Sources > right-click design_1 > Create HDL Wrapper > Let Vivado manage.
Checkpoint: design_1_wrapper is the top (bold) in Sources.

## 5. First build — through the script

In the Tcl console (the script now defaults to this project):

    set ENGINE 1; set ED_K 4; set DENSE_P 4; source C:/Users/dhritiaravind/snn_parkour_fpga/host/vivado/build_engine.tcl

That is the ED K=4 N=1 configuration — the silicon operating point and
the only N=1 build that still predates C0044, so it is the one worth
re-making first. The script sets the RTL block's parameters, switches
the block design to global synthesis, checks the address map, builds,
gates on WNS/WHS, exports the .xsa, runs bootgen with the FSBL and
build-4 conv_server.elf (sizes checked), and copies the delivery into
the Mac's host/mac/build/<tag>/. Nothing in Vitis is needed: the PS
configuration is identical, so the existing platform's FSBL is correct
(if you ever rebuild the platform, the FSBL size check will tell you to
update FSBL_SIZE in the script).

Mac side, before the card: the usual .hwh checks plus a full diff of the
PS and DMA parameters against the archived validated .hwh.

## Expected from the ED K=4 rebuild

Same per-sample latencies as experiments/board_ed_k4_20260905.md
(mean 688.5 us) and 16/16 — the C0044 fix is invisible on N-MNIST by
construction. Resources near the 2026-09-05 numbers, LUTs not strictly
comparable (global vs hierarchical synthesis).
