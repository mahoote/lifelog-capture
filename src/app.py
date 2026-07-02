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

from src.utils.button_utils import create_button_handlers
from src.services.capture_service import CaptureService
from src.drivers.bmi160_driver import BMI160Driver
from src.services.log_service import LogService
from src.services.mode_state_machine import ModeStateMachine
from src.services.motion_service import MotionService
from src.workers.motion_worker import MotionWorker


@dataclass(frozen=True)
class AppConfig:
    button_gpio: int = 26
    bmi160_address: int = 0x69
    button_bounce_time_s: float = 0.05
    button_hold_time_s: float = 3.0
    logs_dir: str = "logs"


class LifelogApp:
    def __init__(self, config: AppConfig):
        self.config = config

        ## Create events
        self.stop_system_event = threading.Event()
        self.capture_mode_event = threading.Event()

        ## Set events
        self.capture_mode_event.set()

        ## Instantiate services and drivers
        self.imu = BMI160Driver(address=config.bmi160_address)
        self.motion_service = MotionService(self.imu)
        self.motion_worker = MotionWorker(
            imu=self.imu,
            detector=self.motion_service,
            stop_system_event=self.stop_system_event,
        )

        self.log_service = LogService(
            motion_service=self.motion_service,
            logs_dir=config.logs_dir,
        )

        # Set the motion service listener
        self.motion_service.set_state_change_listener(
            self.log_service.record_motion_state_change
        )

        self.capture_service = CaptureService(
            motion_service=self.motion_service,
            log_service=self.log_service,
        )
        self.mode_state_machine = ModeStateMachine(
            capture_mode_event=self.capture_mode_event,
            capture_service=self.capture_service,
        )

        self.button = self._create_button()

        ## Create threads
        self.motion_thread = self._create_motion_thread()
        self.mode_state_machine_thread = self._create_mode_state_machine_thread()

    def start(self) -> None:
        """Start workers and attach button callbacks."""
        self.motion_thread.start()
        self.mode_state_machine_thread.start()
        self._bind_button_handlers()

    def wait(self) -> None:
        """Block the main thread while gpiozero handles button callbacks."""
        pause()

    def stop(self) -> None:
        """Ask threads to stop and clean up hardware resources."""
        self.stop_system_event.set()
        self.motion_thread.join(timeout=2)
        self.mode_state_machine_thread.join(timeout=2)
        self.capture_service.stop()
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

    def _create_mode_state_machine_thread(self) -> threading.Thread:
        return threading.Thread(
            target=self.mode_state_machine.run,
            args=(self.stop_system_event,),
            name="mode-state-machine",
            daemon=True,
        )

    def _bind_button_handlers(self) -> None:
        handle_long_press, handle_button_release = create_button_handlers(
            self.stop_system_event,
            self.capture_mode_event,
            self.mode_state_machine_thread,
        )

        self.button.when_held = handle_long_press
        self.button.when_released = handle_button_release
