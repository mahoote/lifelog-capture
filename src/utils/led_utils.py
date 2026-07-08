from gpiozero import PWMLED
import time
import threading

LED_GPIO = 4
led = PWMLED(LED_GPIO)
LED_BRIGHTNESS = 0.3


def led_blink_amount(amount: int, on_period_s: float = 0.1, off_period_s: float = 0.1):
    """
    Blink the LED x number of times.
    """
    for _ in range(amount):
        led_blink(on_period_s, off_period_s)


def led_blink_loop(stop_event: threading.Event, on_period_s: float = 1.0, off_period_s: float = 1.0):
    """
    While the stop event is not set, blink the LED.
    """
    while not stop_event.is_set():
        led_blink(on_period_s, off_period_s)
    led.off()


def led_blink(on_period_s: float = 1.0, off_period_s: float = 1.0):
    """
    Turn on and off the LED connected to GPIO pin 4.
    The LED will be turned on for 1 second and then turned off for 1 second.
    """
    led.value = LED_BRIGHTNESS
    time.sleep(on_period_s)
    led.off()
    time.sleep(off_period_s)


def led_on():
    led.value = LED_BRIGHTNESS


def led_off():
    led.off()
