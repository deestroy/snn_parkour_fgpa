"""INA226 driver: the power meter for M5, over I2C.

The INA226 sits inline on the ZedBoard's 12 V input (docs/m5_power_meter_
shopping.md) and reports bus voltage, shunt voltage, current and power. This
driver configures it for our shunt and reads calibrated values.

Two implementations of the same interface:
  INA226      real chip via smbus2 (Raspberry Pi / any Linux I2C host, or the
              ZedBoard's own PS I2C if we go that way)
  MockINA226  synthetic supply for desk-testing the logger and protocol --
              a fixed idle floor plus a load that switches on when told,
              with realistic noise. Same methods, same units.

Units are SI throughout: volts, amps, watts, seconds. No milli- anywhere in
the API; formatting happens in report.py.
"""

import time
from typing import Optional

# INA226 register map (datasheet table 3)
REG_CONFIG = 0x00
REG_SHUNT_V = 0x01
REG_BUS_V = 0x02
REG_POWER = 0x03
REG_CURRENT = 0x04
REG_CALIB = 0x05
REG_MASK = 0x06
REG_MFR_ID = 0xFE      # reads 0x5449 ("TI")
REG_DIE_ID = 0xFF      # reads 0x2260

SHUNT_LSB_V = 2.5e-6   # fixed by the chip: 2.5 uV per shunt-register LSB
BUS_LSB_V = 1.25e-3    # fixed: 1.25 mV per bus-register LSB

# CONFIG bits: avg[11:9], bus conv time[8:6], shunt conv time[5:3], mode[2:0]
AVG = {1: 0, 4: 1, 16: 2, 64: 3, 128: 4, 256: 5, 512: 6, 1024: 7}
CT = {140e-6: 0, 204e-6: 1, 332e-6: 2, 588e-6: 3, 1.1e-3: 4,
      2.116e-3: 5, 4.156e-3: 6, 8.244e-3: 7}
MODE_CONT_SHUNT_BUS = 0b111


class INA226:
    """Real chip. shunt_ohms and max_amps set the calibration; the current
    LSB is max_amps / 2^15 so the full range fits the 16-bit register."""

    def __init__(self, bus: int = 1, addr: int = 0x40,
                 shunt_ohms: float = 0.02, max_amps: float = 1.5,
                 avg: int = 16, conv_time: float = 1.1e-3):
        import smbus2
        self.bus = smbus2.SMBus(bus)
        self.addr = addr
        self.shunt = shunt_ohms
        self.current_lsb = max_amps / 32768.0
        # datasheet eq. 1: CAL = 0.00512 / (current_lsb * R_shunt)
        cal = int(round(0.00512 / (self.current_lsb * shunt_ohms)))
        if not 0 < cal < 65536:
            raise ValueError("calibration out of range: %d" % cal)
        self._write(REG_CALIB, cal)
        cfg = (AVG[avg] << 9) | (CT[conv_time] << 6) | (CT[conv_time] << 3) | MODE_CONT_SHUNT_BUS
        self._write(REG_CONFIG, cfg)
        # one full conversion = avg * (bus_ct + shunt_ct); that's our max
        # meaningful sample rate
        self.conversion_s = avg * 2 * conv_time
        mfr, die = self._read(REG_MFR_ID), self._read(REG_DIE_ID)
        if mfr != 0x5449:
            raise IOError("not an INA226 at 0x%02x (mfr id 0x%04x)" % (addr, mfr))
        self.die_id = die

    def _write(self, reg: int, val: int) -> None:
        self.bus.write_i2c_block_data(self.addr, reg, [(val >> 8) & 0xFF, val & 0xFF])

    def _read(self, reg: int) -> int:
        b = self.bus.read_i2c_block_data(self.addr, reg, 2)
        return (b[0] << 8) | b[1]

    def _read_signed(self, reg: int) -> int:
        v = self._read(reg)
        return v - 65536 if v & 0x8000 else v

    def sample(self):
        """(t, bus_V, current_A, power_W). Current from the shunt register and
        our own LSB -- we do not trust the chip's power register, which uses a
        fixed 25x current-LSB scaling that is easy to get subtly wrong."""
        t = time.time()
        vbus = self._read(REG_BUS_V) * BUS_LSB_V
        vsh = self._read_signed(REG_SHUNT_V) * SHUNT_LSB_V
        i = vsh / self.shunt
        return t, vbus, i, vbus * i

    def close(self):
        self.bus.close()


class MockINA226:
    """Synthetic supply for desk-testing. Idle floor + switchable load, with
    Gaussian noise and slow drift, so protocol.py's statistics have something
    honest to chew on. Call set_load(watts) to 'start inference'."""

    def __init__(self, vbus: float = 12.0, idle_w: float = 3.2,
                 noise_w: float = 0.02, drift_w_per_s: float = 0.0,
                 conversion_s: float = 0.035, seed: int = 0):
        import random
        self.rng = random.Random(seed)
        self.vbus = vbus
        self.idle_w = idle_w
        self.noise_w = noise_w
        self.drift = drift_w_per_s
        self.conversion_s = conversion_s
        self.load_w = 0.0
        self.t0 = time.time()
        self.die_id = 0x2260

    def set_load(self, watts: float) -> None:
        self.load_w = watts

    def sample(self):
        t = time.time()
        p = self.idle_w + self.load_w + self.drift * (t - self.t0) \
            + self.rng.gauss(0, self.noise_w)
        i = p / self.vbus
        return t, self.vbus, i, p

    def close(self):
        pass
