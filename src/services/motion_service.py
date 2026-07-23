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

import logging
from time import sleep, time
from typing import Callable

from src.drivers.bmi160_driver import BMI160Driver, ImuSample
from src.types.motion_state import MotionState

logger = logging.getLogger(__name__)


class MotionService:
    def __init__(
            self,
            imu: BMI160Driver,
            sample_rate_hz: float = 20.0,
            active_score: float = 0.45,
            idle_score: float = 0.10,
            active_hold_s: float = 0.6,
            idle_hold_s: float = 2.0,
            active_confirm_s: float = 1.5,
            default_confirm_s: float = 5.0,
            idle_confirm_s: float = 10.0,
    ):
        """
        Creates the motion classification logic.

        The thresholds are intentionally simple and easy to tune:
        - idle_score: below this for idle_hold_s means idle
        - active_score: above this for active_hold_s means active
        - between the two means default
        - active_confirm_s: how long active must stay requested before switching
        - default_confirm_s: how long default must stay requested before switching
        - idle_confirm_s: how long idle must stay requested before switching

        Walking should usually reach ACTIVE with the default active_score.
        If walking still stays as DEFAULT, reduce active_score further.
        """
        self.imu = imu
        self.sample_interval_s = 1.0 / sample_rate_hz
        self.active_score = active_score
        self.idle_score = idle_score
        self.active_hold_s = active_hold_s
        self.idle_hold_s = idle_hold_s
        self.state_confirm_s = {
            MotionState.ACTIVE: active_confirm_s,
            MotionState.DEFAULT: default_confirm_s,
            MotionState.IDLE: idle_confirm_s,
        }

        self.state = MotionState.DEFAULT
        self.score = 0.0

        self._baseline_accel_g = 1.0
        self._baseline_gyro_dps = 0.0
        self._idle_since: float | None = None
        self._active_since: float | None = None
        self._pending_state: MotionState | None = None
        self._pending_state_since: float | None = None
        self._state_change_listener: Callable[[MotionState], None] | None = None

    def set_state_change_listener(
            self,
            listener: Callable[[MotionState], None] | None,
    ) -> None:
        """
        Register a callback that is called every time the motion state changes.

        The LogService uses this to account for time in the previous state
        immediately when the state changes, without writing to disk each time.
        """
        self._state_change_listener = listener

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
        self._set_state(MotionState.IDLE, force=True)

    def update(self) -> MotionState:
        """
        Read one sample and return the current motion state.

        Returns:
            MotionState.IDLE, MotionState.DEFAULT, or MotionState.ACTIVE.
        """
        sample = self.imu.read_sample()
        score = self._motion_score(sample)

        # Smooth short spikes, but still react quickly enough for walking.
        alpha = 0.30
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
            self._set_state(MotionState.DEFAULT)

        if self._active_since is not None and now - self._active_since >= self.active_hold_s:
            self._set_state(MotionState.ACTIVE)
        elif self._idle_since is not None and now - self._idle_since >= self.idle_hold_s:
            self._set_state(MotionState.IDLE)

        return self.state

    def _set_state(self, new_state: MotionState, force: bool = False) -> None:
        """Update the motion state and log only when the mode changes."""
        if new_state == self.state:
            self._pending_state = None
            self._pending_state_since = None
            return

        now = time()

        if not force:
            if self._pending_state != new_state:
                self._pending_state = new_state
                self._pending_state_since = now
                return

            if self._pending_state_since is None:
                self._pending_state_since = now
                return

            required_confirm_s = self.state_confirm_s[new_state]
            if now - self._pending_state_since < required_confirm_s:
                return

        previous_state = self.state
        self.state = new_state
        self._pending_state = None
        self._pending_state_since = None

        logger.info(
            "Motion mode changed: %s -> %s, score=%.2f",
            previous_state.value,
            new_state.value,
            self.score,
        )

        if self._state_change_listener is not None:
            self._state_change_listener(new_state)

    def _motion_score(self, sample: ImuSample) -> float:
        """
        Convert accelerometer and gyroscope readings into one movement score.

        Acceleration uses the change away from the calibrated still magnitude.
        Gyroscope catches rotation, which helps detect head and body movement.
        """
        accel_delta_g = abs(sample.accel_magnitude_g - self._baseline_accel_g)
        gyro_delta_dps = max(0.0, sample.gyro_magnitude_dps - self._baseline_gyro_dps)

        # More sensitive than the first outdoor test version.
        # Walking should cross active_score through periodic acceleration and rotation.
        return (accel_delta_g * 5.0) + (gyro_delta_dps / 80.0)
