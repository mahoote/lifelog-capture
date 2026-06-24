import subprocess
import threading
from time import monotonic


def wait_for_next_capture(
        stop_event: threading.Event,
        capture_mode_event: threading.Event,
        interval_seconds: float,
        check_every: float = 0.25,
) -> bool:
    """
    Wait until the next capture should happen.

    Returns:
        True if the full interval completed and capture mode is still active.
        False if shutdown was requested or capture mode was disabled.
    """
    deadline = monotonic() + interval_seconds

    while not stop_event.is_set() and capture_mode_event.is_set():
        remaining = deadline - monotonic()

        if remaining <= 0:
            return True

        stop_event.wait(timeout=min(check_every, remaining))

    return False


def shutdown_pi(stop_event: threading.Event, capture_thread: threading.Thread | None = None):
    """
    Set stop_event, wait briefly for services to stop, then shut down the Pi.
    """
    if stop_event.is_set():
        return

    stop_event.set()

    if capture_thread is not None:
        capture_thread.join(timeout=5)

    subprocess.run(["sudo", "shutdown", "-h", "now"], check=False)
