# M5 with a bench multimeter (before/instead of the INA226)

The professor's suggestion (2026-08-19): measure the board's input current
with a lab DMM rather than buying the INA226 breakout. This is the same
idle -> running -> idle delta protocol as `measure/protocol.py`, read by
eye and typed in. It produces energy per inference with an honest
uncertainty, and it tells you whether the DMM can resolve the delta at all
(if it cannot, that is the case for the INA226).

## What is being measured, and why the number is small

The whole board draws roughly 0.4-0.6 A at 12 V; almost all of it is the
ARM side, regulators and DDR. The FPGA engine's *dynamic* contribution --
the thing the thesis compares between dense and event-driven -- is likely
tens of milliwatts, i.e. **a few milliamps at 12 V**. So:

- the meter needs **>= 1 mA resolution on a ~1 A range; 0.1 mA is much
  better** (a 4 1/2-digit bench DMM; a 3 1/2-digit handheld will show the
  same reading idle and running);
- the run phase must be **BURST mode**, so the engine is busy ~100 % of the
  time (`python3 host/uart_client.py --burst-only --burst 12000` = ~18 s on
  the ED engine; scale N by the engine's latency to get 15-30 s);
- read idle **before and after**, and use several readings each, because
  the last digit will flicker.

## Wiring (you do this; power off first)

Series ammeter on the **12 V input**: barrel-jack breakout or a cut/spliced
adapter lead; the meter's A input in series with the +12 V conductor,
COM towards the board. Start on the meter's highest current range, confirm
~0.5 A, then move to the most sensitive range that still covers it. Never
switch ranges with the board powered if the meter breaks the circuit when
switching (most do) -- the board would brown out and reboot. Note the
meter's burden voltage: at 0.5 A on a 1 A range it can be 0.1-0.3 V; the
board's regulators do not care at 12 V input, but write it down.

Voltage: read the supply's 12 V once (or use the meter in V mode across the
barrel before wiring the ammeter). P = V x I.

## Procedure (one run = one engine bitstream)

1. Board booted from SD, `uart_client.py` PING ok, engine idle. Wait 60 s
   for thermal settling.
2. **Idle before**: 5 readings, ~5 s apart. Type them in.
3. **Burst**: start `python3 host/uart_client.py --burst-only --burst N`
   (N sized for 15-30 s). Take 5 readings while it runs, spread over the
   window. Note the client's reported elapsed seconds and N.
4. **Idle after**: 5 readings.
5. `python3 measure/manual_meter.py` prompts for all of the above and
   writes `measure/runs/<timestamp>_<label>.json` plus the number:

       energy per inference = (V x (I_run - I_idle)) x elapsed / N

   with the uncertainty from the spread of the readings (SEM), and a flag
   if idle drifted between before and after by more than the delta itself.
6. Repeat 3 times per engine. Repeat for the other engine's bitstream.

## What to report (project brief: never mean power alone)

- energy per inference, measured (uJ), +/- SEM, and Vivado's estimate
  beside it (1.73 W total on-chip for the ED build; the fabric-only estimate
  from the power report is the fairer comparator -- record both);
- latency per inference (from BURST, already measured: ED K=4 1.51 ms;
  dense predicted 4.4 ms);
- resources (LUT/FF/BRAM/DSP), firing rate, accuracy -- from decisions.md.

If `I_run - I_idle` is within the reading noise, say so: "the DMM cannot
resolve the engine's power at 12 V" is a legitimate, useful sentence, and
it is the justification for the INA226 (0.02 ohm shunt, 2.5 uV LSB) or for
measuring a lower-current rail.


---

# Protocol upgrades from the 2026-08-20 methodology review

## The three energy quantities (C0038) — never let them merge

1. **System energy per inference** — board-level (12 V input), dominated by
   the ARM/PS (~96 % of dynamic). The deployment number.
2. **Delta-E between the two engines** — the fabric-attributable
   difference between builds measured in the same session. THE
   architecture result. All dense-vs-ED claims cite this.
3. **Engine energy** — (2) plus the static attribution from idle
   measurements, method stated.
Every table labels which quantity each number is. The ES-Parkour audit
uses (2) or (3), never (1).

## Measurement boundary (C0004) — the sentence every table caption cites

"Measured at the 12 V board input: the boundary encloses the whole
ZedBoard — FPGA (PS+PL), DDR3, clocks, PHYs, OLED, LEDs and all regulator
losses. Published accelerator figures are almost always die-only tool
estimates; the two are not directly comparable and are never mixed in one
column." Open question to settle from the Rev C.1 schematic before the
first session: whether VCCINT (PL core) is a separately shuntable net —
if yes, a load-side measurement isolates the fabric and supersedes the
barrel-jack numbers for quantity (2). Regulator non-linearity (C0026):
if staying at the barrel jack, characterise input-vs-load with a known
variable load, or bound and declare it.

## Idle power is a first-class measurement (C0001)

Report P_idle(design) AND delta-P(design) per bitstream. Idle state,
defined once: PL configured and clocked, DMA idle, CPU in the
conv_server receive loop, no BURST. Static power is half the thesis
argument; the delta alone subtracts it away.

## Noise floor first (C0002) — at the start of EVERY session

Same bitstream: twice cold (power-cycle between), twice warm (10 min
apart). The spread is the session's noise floor; no delta smaller than it
may be reported. If the floor exceeds the dense-vs-ED delta, engine
replication (N_ENGINES, C0003) becomes mandatory.

## Thermal discipline (C0009/C0020)

Warm up with continuous BURST until XADC die temperature is stable
(tolerance stated, e.g. +/-1 degC over 2 min) BEFORE the measurement
window; log die temperature at every idle and burst reading. Idle-vs-
burst temperature difference bounds the leakage term inside delta-P.

## Statistics (C0013/C0019)

Per condition: >= 5 repeats, report mean +/- 95 % CI, never single
values. Between-repeats: re-arm BURST fresh (new sample order where
C0018's sweep mode applies). Implementation-seed variance: each design
built 3-5 times with different placer seeds (all WNS >= 0), P_idle and
delta-P per build; the seed spread is quoted next to every design-level
delta, and if it rivals the delta, the comparison says so.

## Sample distribution (C0018)

Never a single sample: BURST's sweep mode cycles the loaded sample set;
energy is reported as mean +/- spread over samples. State-reset behaviour
between iterations is documented in host/protocol.md and identical for
both engines.
