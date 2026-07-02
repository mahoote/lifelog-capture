from __future__ import annotations

import threading

from src.services.capture_service import CaptureService


class ModeStateMachine:
    def __init__(
            self,
            capture_mode_event: threading.Event,
            capture_service: CaptureService,
    ):
        self._capture_service = capture_service
        self._capture_mode_event = capture_mode_event
        self._capture_mode_enabled = capture_mode_event.is_set()

    def run(self, stop_system_event: threading.Event) -> None:
        """
        Run the mode state machine until stop is requested.
        Sets the correct mode if the capture mode event is toggled.
        """
        self._set_mode()

        capture_mode_enabled = self._capture_mode_event.is_set()

        # Checking if the capture mode has toggled every cycle.
        while not stop_system_event.is_set():
            if capture_mode_enabled != self._capture_mode_enabled:
                self._set_mode()
                # Save the current state.
                capture_mode_enabled = self._capture_mode_enabled

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
        # TODO: Implement transfer mode stop logic
        self._capture_service.start()

    def _enter_transfer_mode(self) -> None:
        self._capture_service.stop()
        # TODO: Implement transfer mode start logic
