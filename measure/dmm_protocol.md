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
