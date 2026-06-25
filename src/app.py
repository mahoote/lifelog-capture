"""
Application wiring for the smart glasses runtime.

main.py should stay small. This file owns the setup order:
- shared events
- hardware objects
- background threads
- button callbacks
- shutdown cleanup
"""

from __future__ import annotations

import threading
from dataclasses import dataclass
from signal import pause
from gpiozero import Button

from src.button_utils import create_button_handlers
from src.capture import run_capture
from src.drivers.bmi160_driver import BMI160Driver
from src.motion_detector import MotionDetector
from src.workers.motion_worker import MotionWorker


@dataclass(frozen=True)
class AppConfig:
    button_gpio: int = 26
    bmi160_address: int = 0x69
    button_bounce_time_s: float = 0.05
    button_hold_time_s: float = 3.0


class LifelogApp:
    def __init__(self, config: AppConfig):
        self.config = config

        self.stop_event = threading.Event()
        self.capture_mode_event = threading.Event()
        self.capture_mode_event.set()

        self.imu = BMI160Driver(address=config.bmi160_address)
        self.motion_detector = MotionDetector(self.imu)
        self.motion_worker = MotionWorker(
            imu=self.imu,
            detector=self.motion_detector,
            stop_event=self.stop_event,
        )

        self.button = self._create_button()
        self.motion_thread = self._create_motion_thread()
        self.capture_thread = self._create_capture_thread()

    def start(self) -> None:
        """Start workers and attach button callbacks."""
        self.motion_thread.start()
        self.capture_thread.start()
        self._bind_button_handlers()

    def wait(self) -> None:
        """Block the main thread while gpiozero handles button callbacks."""
        pause()

    def stop(self) -> None:
        """Ask threads to stop and clean up hardware resources."""
        self.stop_event.set()
        self.motion_thread.join(timeout=2)
        self.capture_thread.join(timeout=2)
        self.imu.close()

    def _create_button(self) -> Button:
        return Button(
            self.config.button_gpio,
            pull_up=True,
            bounce_time=self.config.button_bounce_time_s,
            hold_time=self.config.button_hold_time_s,
        )

    def _create_motion_thread(self) -> threading.Thread:
        return threading.Thread(
            target=self.motion_worker.run,
            name="motion-detector",
            daemon=True,
        )

    def _create_capture_thread(self) -> threading.Thread:
        return threading.Thread(
            target=run_capture,
            args=(self.stop_event, self.capture_mode_event),
            name="capture",
            daemon=True,
        )

    def _bind_button_handlers(self) -> None:
        handle_long_press, handle_button_release = create_button_handlers(
            self.stop_event,
            self.motion_detector,
            self.capture_thread,
        )

        self.button.when_held = handle_long_press
        self.button.when_released = handle_button_release
