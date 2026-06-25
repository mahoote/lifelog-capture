"""
Three-state motion detection logic for BMI160 IMU samples.

This file does not talk directly to I2C registers. That belongs in
bmi160_driver.py.

States:
    idle     User is basically still, for example standing or sitting.
    default  Some movement, but not sustained high movement.
    active   Lots of movement, for example walking outside or cleaning.
"""

from __future__ import annotations

from enum import Enum
from time import sleep, time

from src.drivers.bmi160_driver import BMI160Driver, ImuSample


class MotionState(str, Enum):
    IDLE = "idle"
    DEFAULT = "default"
    ACTIVE = "active"


class MotionDetector:
    def __init__(
            self,
            imu: BMI160Driver,
            sample_rate_hz: float = 20.0,
            active_score: float = 1.20,
            idle_score: float = 0.12,
            active_hold_s: float = 0.8,
            idle_hold_s: float = 2.0,
    ):
        """
        Creates the motion classification logic.

        The thresholds are intentionally simple and easy to tune:
        - idle_score: below this for idle_hold_s means idle
        - active_score: above this for active_hold_s means active
        - between the two means default
        """
        self.imu = imu
        self.sample_interval_s = 1.0 / sample_rate_hz
        self.active_score = active_score
        self.idle_score = idle_score
        self.active_hold_s = active_hold_s
        self.idle_hold_s = idle_hold_s

        self.state = MotionState.DEFAULT
        self.score = 0.0

        self._baseline_accel_g = 1.0
        self._baseline_gyro_dps = 0.0
        self._idle_since: float | None = None
        self._active_since: float | None = None

    def calibrate_idle(self, samples: int = 80) -> None:
        """
        Calibrate while the sensor is still.

        Call this when the device is placed in its normal orientation and is not
        being moved. It makes idle detection less sensitive to mounting angle
        and sensor offset.
        """
        accel_total = 0.0
        gyro_total = 0.0

        for _ in range(samples):
            sample = self.imu.read_sample()
            accel_total += sample.accel_magnitude_g
            gyro_total += sample.gyro_magnitude_dps
            sleep(self.sample_interval_s)

        self._baseline_accel_g = accel_total / samples
        self._baseline_gyro_dps = gyro_total / samples
        self.score = 0.0
        self._idle_since = None
        self._active_since = None
        self.state = MotionState.IDLE

    def update(self) -> MotionState:
        """
        Read one sample and return the current motion state.

        Returns:
            MotionState.IDLE, MotionState.DEFAULT, or MotionState.ACTIVE.
        """
        sample = self.imu.read_sample()
        score = self.motion_score(sample)

        # Smooth short spikes, but still react quickly enough for walking.
        alpha = 0.25
        self.score = (alpha * score) + ((1.0 - alpha) * self.score)

        now = time()

        if self.score >= self.active_score:
            if self._active_since is None:
                self._active_since = now
            self._idle_since = None
        elif self.score <= self.idle_score:
            if self._idle_since is None:
                self._idle_since = now
            self._active_since = None
        else:
            self._idle_since = None
            self._active_since = None
            self.state = MotionState.DEFAULT
            print("Motion State: DEFAULT")

        if self._active_since is not None and now - self._active_since >= self.active_hold_s:
            self.state = MotionState.ACTIVE
            print("Motion State: ACTIVE")
        elif self._idle_since is not None and now - self._idle_since >= self.idle_hold_s:
            self.state = MotionState.IDLE
            print("Motion State: IDLE")

        return self.state

    def motion_score(self, sample: ImuSample) -> float:
        """
        Convert accelerometer and gyroscope readings into one movement score.

        Acceleration uses the change away from the calibrated still magnitude.
        Gyroscope catches rotation, which helps detect head and body movement.
        """
        accel_delta_g = abs(sample.accel_magnitude_g - self._baseline_accel_g)
        gyro_delta_dps = max(0.0, sample.gyro_magnitude_dps - self._baseline_gyro_dps)

        # Weighting chosen so ordinary small shifts land in default, while
        # walking or cleaning tends to cross active.
        return (accel_delta_g * 3.0) + (gyro_delta_dps / 120.0)
