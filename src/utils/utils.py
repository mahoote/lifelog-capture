import subprocess
import threading
from time import monotonic


def wait_for_next_capture(
        stop_event: threading.Event,
        interval_seconds: float,
        last_capture_at: float,
        check_every: float = 0.25,
) -> bool:
    """
    Wait briefly before checking whether the next capture should happen.

    Returns:
        True if elapsed time has reached the current interval.
        False if shutdown was requested or the interval has not elapsed yet.
    """
    if stop_event.is_set():
        return False

    if monotonic() - last_capture_at >= interval_seconds:
        return True

    stop_event.wait(timeout=check_every)
    return False


def shutdown_pi(stop_system_event: threading.Event, managed_thread: threading.Thread | None = None):
    """
    Set stop_system_event, wait briefly for services to stop, then shut down the Pi.
    """
    if stop_system_event.is_set():
        return

    stop_system_event.set()

    if managed_thread is not None:
        managed_thread.join(timeout=5)

    subprocess.run(["sudo", "shutdown", "-h", "now"], check=False)
