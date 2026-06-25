"""
Low-level BMI160 driver for the DFRobot Gravity BMI160 6-axis IMU.

This file only handles sensor communication:
- opening I2C
- configuring the BMI160
- reading raw accelerometer and gyroscope registers
- converting raw values into useful units

DFRobot address note:
- Default I2C address is 0x69
- If SDO is connected to GND, use 0x68
"""

from __future__ import annotations

from dataclasses import dataclass
from math import sqrt
from time import sleep

try:
    from smbus2 import SMBus
except ImportError:  # Raspberry Pi OS often has this package instead
    from smbus import SMBus  # type: ignore


@dataclass
class ImuSample:
    ax_g: float
    ay_g: float
    az_g: float
    gx_dps: float
    gy_dps: float
    gz_dps: float

    @property
    def accel_magnitude_g(self) -> float:
        return sqrt(self.ax_g**2 + self.ay_g**2 + self.az_g**2)

    @property
    def gyro_magnitude_dps(self) -> float:
        return sqrt(self.gx_dps**2 + self.gy_dps**2 + self.gz_dps**2)


class BMI160Driver:
    # BMI160 registers
    CHIP_ID_REG = 0x00
    DATA_START_REG = 0x0C
    CMD_REG = 0x7E
    ACC_CONF_REG = 0x40
    ACC_RANGE_REG = 0x41
    GYR_CONF_REG = 0x42
    GYR_RANGE_REG = 0x43

    EXPECTED_CHIP_ID = 0xD1

    # Register values
    CMD_ACC_NORMAL = 0x11
    CMD_GYR_NORMAL = 0x15
    ACC_CONF_100HZ = 0x28
    GYR_CONF_100HZ = 0x28
    ACC_RANGE_2G = 0x03
    GYR_RANGE_2000DPS = 0x00

    ACCEL_LSB_PER_G = 16384.0
    GYRO_LSB_PER_DPS = 16.4

    def __init__(self, bus_number: int = 1, address: int = 0x69):
        self.bus_number = bus_number
        self.address = address
        self.bus: SMBus | None = None

    def start(self) -> None:
        """Open I2C, verify the chip, and configure the BMI160."""
        self.bus = SMBus(self.bus_number)

        chip_id = self._read_u8(self.CHIP_ID_REG)
        if chip_id != self.EXPECTED_CHIP_ID:
            raise RuntimeError(
                f"BMI160 not found at 0x{self.address:02X}. "
                f"Expected chip id 0x{self.EXPECTED_CHIP_ID:02X}, got 0x{chip_id:02X}."
            )

        self._write_u8(self.CMD_REG, self.CMD_ACC_NORMAL)
        sleep(0.05)
        self._write_u8(self.CMD_REG, self.CMD_GYR_NORMAL)
        sleep(0.2)

        self._write_u8(self.ACC_RANGE_REG, self.ACC_RANGE_2G)
        self._write_u8(self.GYR_RANGE_REG, self.GYR_RANGE_2000DPS)
        self._write_u8(self.ACC_CONF_REG, self.ACC_CONF_100HZ)
        self._write_u8(self.GYR_CONF_REG, self.GYR_CONF_100HZ)
        sleep(0.05)

    def close(self) -> None:
        if self.bus is not None:
            self.bus.close()
            self.bus = None

    def read_sample(self) -> ImuSample:
        """Read one accelerometer and gyroscope sample from the BMI160."""
        if self.bus is None:
            raise RuntimeError("Call start() before reading the BMI160.")

        data = self.bus.read_i2c_block_data(self.address, self.DATA_START_REG, 12)

        gx = self._to_int16(data[1], data[0]) / self.GYRO_LSB_PER_DPS
        gy = self._to_int16(data[3], data[2]) / self.GYRO_LSB_PER_DPS
        gz = self._to_int16(data[5], data[4]) / self.GYRO_LSB_PER_DPS
        ax = self._to_int16(data[7], data[6]) / self.ACCEL_LSB_PER_G
        ay = self._to_int16(data[9], data[8]) / self.ACCEL_LSB_PER_G
        az = self._to_int16(data[11], data[10]) / self.ACCEL_LSB_PER_G

        return ImuSample(ax_g=ax, ay_g=ay, az_g=az, gx_dps=gx, gy_dps=gy, gz_dps=gz)

    def _read_u8(self, register: int) -> int:
        if self.bus is None:
            raise RuntimeError("I2C bus is not open.")
        return self.bus.read_byte_data(self.address, register)

    def _write_u8(self, register: int, value: int) -> None:
        if self.bus is None:
            raise RuntimeError("I2C bus is not open.")
        self.bus.write_byte_data(self.address, register, value)

    @staticmethod
    def _to_int16(msb: int, lsb: int) -> int:
        value = (msb << 8) | lsb
        if value & 0x8000:
            value -= 0x10000
        return value
