import time
import subprocess
import threading
from gpiozero import LED


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
    # idempotent
    if stop_event.is_set():
        return
    stop_event.set()
    subprocess.run(["sudo", "shutdown", "-h", "now"], check=False)
