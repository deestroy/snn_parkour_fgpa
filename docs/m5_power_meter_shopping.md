# M5 power meter — what to order (decide today, parts have lead time)

The measurement: current and voltage on the ZedBoard's **input supply**,
sampled continuously while the board sits idle vs. runs inference. Energy per
inference = (mean running power − mean idle power) × time, averaged over
thousands of back-to-back inferences. The ZedBoard draws roughly 3–6 W at 12 V,
so we are metering **0–0.5 A on a 12 V rail** (a lower current, so a 0.05 Ω shunt also works and gives finer resolution) and looking for deltas of tens to
hundreds of mW.

## Option A (recommended): INA226 breakout + replacement shunt

- **INA226 breakout board** — the generic "CJMCU-226" module, a few dollars
  from the usual suspects. Buy **two** (spare).
- **Caveat that matters:** these modules ship with a 0.1 Ω shunt (marked
  R100). At 2 A that drops 200 mV — beyond the INA226's ±81.92 mV sense
  range, so it would clip. Order a **0.02 Ω, 1%, ≥2 W shunt resistor**
  (0.01 Ω also fine) and we swap it: one desolder, one solder. With 0.02 Ω:
  2 A → 40 mV, well in range, ~1.5 mA resolution, 80 mW dissipated worst
  case.
- 16-bit readings, I²C interface, averaging built into the chip. This is the
  part named in the project brief and what the published-work comparison
  expects.

## Option B (no soldering): Adafruit INA260

- Integrated 2 mΩ shunt, handles 15 A, plain I²C, ~$10. Resolution 1.25 mA /
  1.25 mW — coarser per sample than a well-shunted INA226, but averaging over
  seconds of steady-state inference makes that irrelevant for the idle-vs-
  running delta. Choose this if the shunt swap in Option A sounds unappealing.

Skip the Joulescope for now: ~$1000 and weeks of lead time buys bandwidth we
don't need for steady-state deltas. Revisit only if M7 needs per-inference
transient resolution.

## Also in the cart (either option)

- A **2.1 mm barrel-jack extension or pigtail pair** (male + female,
  centre-positive) — the shunt goes inline in its 12 V wire, so the board's
  own brick and jack stay unmodified. On the ZedBoard the sense point is the
  12 V input, not a USB line.
- Dupont jumper wires female-female, if none around the lab.

## How it gets read (no extra hardware)

The ZedBoard reads its own meter: the INA226's I²C pins go to the board's
JA1 PMOD connector (3.3 V logic on both sides, direct wiring), and the logging
script runs on the board's ARM alongside the inference driver. Self-metering
adds a small constant load — irrelevant for delta measurements, and the
methodology chapter will say so explicitly. (Alternative if you prefer
isolation: any Raspberry Pi or Arduino can host the I²C instead; the logging
code will speak plain smbus either way.)

## Wiring sketch (for when it arrives — do not wire anything yet)

```
 12V brick ---+12V--[ shunt 0.02R ]---+12V---> ZedBoard barrel jack (D0014)
             |                    |
           VIN+                VIN- (INA226 senses across the shunt)
 GND --------+--------------------+--------> common ground
 INA226 SDA/SCL/3V3/GND ------------------> JA1 PMOD pins (mapping comes with
                                             the logging code)
```
