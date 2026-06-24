import threading
from signal import pause
from gpiozero import Button

from src.capture import run_capture
from src.utils import shutdown_pi

BUTTON_GPIO = 26

stop_event = threading.Event()
capture_mode_event = threading.Event()

capture_mode_event.set()

button = Button(BUTTON_GPIO, pull_up=True, bounce_time=0.05)

capture_thread = threading.Thread(
    target=run_capture,
    args=(stop_event, capture_mode_event),
    daemon=True
)
capture_thread.start()

# bind button press to shutdown
button.when_pressed = lambda: shutdown_pi(stop_event, capture_thread)

pause()
