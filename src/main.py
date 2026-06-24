import threading
from signal import pause
from gpiozero import LED, Button

from src.capture import run_capture
from utils import blink_loop, shutdown_pi

LED_GPIO = 4
BUTTON_GPIO = 26

stop_event = threading.Event()
capture_mode_event = threading.Event()

capture_mode_event.set()

led = LED(LED_GPIO)
button = Button(BUTTON_GPIO, pull_up=True, bounce_time=0.05)

# start blinking in background
threading.Thread(
    target=blink_loop,
    args=(led, stop_event, 1.0),
    daemon=True
).start()

threading.Thread(
    target=run_capture,
    args=(stop_event, capture_mode_event),
    daemon=True
).start()

# bind button press to shutdown
button.when_pressed = lambda: shutdown_pi(stop_event)

pause()
