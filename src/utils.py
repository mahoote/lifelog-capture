from gpiozero import LED
from time import sleep

led = LED(4)  # BCM GPIO 4


def led_loop():
    """
    Loop to turn on and off the LED connected to GPIO pin 4.
    The LED will be turned on for 1 second and then turned off for 1 second.
    """
    while True:
        led.on()
        sleep(1)
        led.off()
        sleep(1)
