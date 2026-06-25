import threading
from collections.abc import Callable

from src.services.motion_service import MotionService
from src.utils import shutdown_pi


def toggle_motion_mode(motion_detector: MotionService) -> None:
    """Toggle between moving and stationary capture behavior."""
    motion_detector.is_moving = not motion_detector.is_moving

    if motion_detector.is_moving:
        print("Motion mode enabled, capturing video")
    else:
        print("Motion mode disabled, capturing photos")


def toggle_capture_mode(capture_mode_event: threading.Event) -> None:
    """Toggle between capture mode and transfer mode."""
    if capture_mode_event.is_set():
        print("Switching to transfer mode")
        capture_mode_event.clear()
    else:
        print("Switching to capture mode")
        capture_mode_event.set()


def create_button_handlers(
        stop_event: threading.Event,
        capture_mode_event: threading.Event,
        # motion: MotionDetector,
        capture_thread: threading.Thread,
) -> tuple[Callable[[], None], Callable[[], None]]:
    """
    Create button handlers for short and long button presses.

    Short press toggles capture mode.
    Long press initiates system shutdown.
    """
    button_state = {
        "long_press_handled": False,
    }

    def handle_long_press() -> None:
        """Handle a long button press."""
        print("Long press detected, shutting down")
        button_state["long_press_handled"] = True
        shutdown_pi(stop_event, capture_thread)

    def handle_button_release() -> None:
        """Handle a short button press."""
        if button_state["long_press_handled"]:
            button_state["long_press_handled"] = False
            return

        print("Short press detected")
        toggle_capture_mode(capture_mode_event)
        # toggle_motion_mode(motion)

    return handle_long_press, handle_button_release
