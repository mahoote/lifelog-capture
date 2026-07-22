"""
Background worker for motion detection.

This keeps the threading loop out of main.py and away from the pure
MotionDetector logic.
"""

from __future__ import annotations

import logging
import threading
from time import sleep

from src.drivers.bmi160_driver import BMI160Driver
from src.services.motion_service import MotionService

logger = logging.getLogger(__name__)


class MotionWorker:
    def __init__(
            self,
            imu: BMI160Driver,
            detector: MotionService,
    ):
        self.imu = imu
        self.detector = detector

    def run(self, stop_capture_event: threading.Event, stop_motion_event: threading.Event) -> None:
        """
        Start the IMU, calibrate, then update motion state until stopped.

        Other parts of the app can read detector.state. They should not call
        detector.update() themselves, because this worker owns the update loop.
        """
        logger.info("Starting motion service")

        self.imu.start()
        try:
            self.detector.calibrate_idle()

            while not stop_capture_event.is_set() or not stop_motion_event.is_set():
                self.detector.update()
                sleep(self.detector.sample_interval_s)
        finally:
            logger.info("Stopping motion service")
            self.imu.close()
