"""
Background worker for motion detection.

This keeps the threading loop out of main.py and away from the pure
MotionDetector logic.
"""

from __future__ import annotations

import threading
from time import sleep

from src.drivers.bmi160_driver import BMI160Driver
from src.services.motion_service import MotionService


class MotionWorker:
    def __init__(
            self,
            imu: BMI160Driver,
            detector: MotionService,
            stop_system_event: threading.Event,
    ):
        self.imu = imu
        self.detector = detector
        self.stop_system_event = stop_system_event

    def run(self) -> None:
        """
        Start the IMU, calibrate, then update motion state until stopped.

        Other parts of the app can read detector.state. They should not call
        detector.update() themselves, because this worker owns the update loop.
        """
        self.imu.start()
        self.detector.calibrate_idle()

        while not self.stop_system_event.is_set():
            self.detector.update()
            sleep(self.detector.sample_interval_s)
