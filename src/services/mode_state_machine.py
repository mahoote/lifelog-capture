from __future__ import annotations

import threading

from src.services.capture_service import CaptureService
from src.services.transfer_service import TransferService


class ModeStateMachine:
    def __init__(
            self,
            capture_mode_event: threading.Event,
            capture_service: CaptureService,
            transfer_service: TransferService,
            poll_interval_seconds: float = 0.25,
    ):
        self._capture_service = capture_service
        self._transfer_service = transfer_service
        self._capture_mode_event = capture_mode_event
        self._capture_mode_enabled = capture_mode_event.is_set()
        self._poll_interval_seconds = poll_interval_seconds

    def run(self, stop_system_event: threading.Event) -> None:
        """
        Run the mode state machine until stop is requested.
        Sets the correct mode if the capture mode event is toggled.
        """
        self._set_mode()

        # Checking if the capture mode has toggled every cycle.
        while not stop_system_event.is_set():
            capture_mode_enabled = self._capture_mode_event.is_set()

            if capture_mode_enabled != self._capture_mode_enabled:
                self._capture_mode_enabled = capture_mode_enabled
                self._set_mode()
            stop_system_event.wait(timeout=self._poll_interval_seconds)

        self._capture_service.stop()

    def _set_mode(self):
        """
        Sets the correct mode based on the capture mode event.
        """
        if self._capture_mode_enabled:
            self._enter_capture_mode()
        else:
            self._enter_transfer_mode()

    def _enter_capture_mode(self) -> None:
        self._transfer_service.stop()
        self._capture_service.start()

    def _enter_transfer_mode(self) -> None:
        self._capture_service.stop()
        self._transfer_service.start()
