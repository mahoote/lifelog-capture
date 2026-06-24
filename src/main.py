import threading
from signal import pause

from gpiozero import Button

from src.button_utils import create_button_handlers
from src.capture import run_capture

BUTTON_GPIO = 26

stop_event = threading.Event()
capture_mode_event = threading.Event()

capture_mode_event.set()

button = Button(
    BUTTON_GPIO,
    pull_up=True,
    bounce_time=0.05,
    hold_time=3,
)

capture_thread = threading.Thread(
    target=run_capture,
    args=(stop_event, capture_mode_event),
    daemon=True,
)

handle_long_press, handle_button_release = create_button_handlers(
    stop_event,
    capture_mode_event,
    capture_thread,
)

capture_thread.start()

button.when_held = handle_long_press
button.when_released = handle_button_release

pause()
