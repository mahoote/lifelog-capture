import threading
from signal import pause
from gpiozero import LED, Button
from util import blink_loop, shutdown_pi

LED_GPIO = 4
BUTTON_GPIO = 26

stop_event = threading.Event()

led = LED(LED_GPIO)
button = Button(BUTTON_GPIO, pull_up=True, bounce_time=0.05)

# start blinking in background
threading.Thread(
    target=blink_loop,
    args=(led, stop_event, 1.0),
    daemon=True
).start()

# bind button press to shutdown
button.when_pressed = lambda: shutdown_pi(stop_event)

pause()
