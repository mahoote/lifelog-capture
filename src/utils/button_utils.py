import threading
from collections.abc import Callable

from src.utils.utils import shutdown_pi


def toggle_capture_mode(capture_mode_event: threading.Event) -> None:
    """Toggle between capture mode and transfer mode."""
    if capture_mode_event.is_set():
        print("Switching to transfer mode")
        capture_mode_event.clear()
    else:
        print("Switching to capture mode")
        capture_mode_event.set()


def create_button_handlers(
        stop_system_event: threading.Event,
        capture_mode_event: threading.Event,
        managed_thread: threading.Thread | None = None,
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
        shutdown_pi(stop_system_event, managed_thread)

    def handle_button_release() -> None:
        """Handle a short button press."""
        if button_state["long_press_handled"]:
            button_state["long_press_handled"] = False
            return

        print("Short press detected")
        toggle_capture_mode(capture_mode_event)

    return handle_long_press, handle_button_release
