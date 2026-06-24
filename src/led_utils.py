from gpiozero import PWMLED
import time
import threading

LED_GPIO = 4
led = PWMLED(LED_GPIO)
LED_BRIGHTNESS = 0.5


def led_blink_loop(stop_event: threading.Event, period_s: float = 1.0):
    """
    While the stop event is not set, blink the LED.
    """
    while not stop_event.is_set():
        led_blink(period_s)
    led.off()


def led_blink(period_s: float = 1.0):
    """
    Turn on and off the LED connected to GPIO pin 4.
    The LED will be turned on for 1 second and then turned off for 1 second.
    """
    led.value = LED_BRIGHTNESS
    led.toggle()
    time.sleep(period_s)


def led_on():
    led.value = LED_BRIGHTNESS
    led.on()


def led_off():
    led.value = LED_BRIGHTNESS
    led.off()
