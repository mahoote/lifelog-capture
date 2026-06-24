import time
import subprocess
import threading
from gpiozero import LED
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


def blink_loop(led: LED, stop_event: threading.Event, period_s: float = 1.0):
    """
    Turn on and off the LED connected to GPIO pin 4.
    The LED will be turned on for 1 second and then turned off for 1 second.
    """
    while not stop_event.is_set():
        led.toggle()
        time.sleep(period_s)
    led.off()


def shutdown_pi(stop_event: threading.Event):
    """
    If the stop event is not set, set it and run the shutdown command.
    """
    if stop_event.is_set():
        return
    stop_event.set()
    subprocess.run(["sudo", "shutdown", "-h", "now"], check=False)
