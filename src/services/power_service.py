import logging
import threading
from gpiozero import Button

from src.app import AppConfig

logger = logging.getLogger(__name__)


class PowerService:
    def __init__(self,
                 config: AppConfig,
                 capture_mode_event: threading.Event,
                 stop_system_event: threading.Event):
        self.capture_mode_event = capture_mode_event
        self.stop_system_event = stop_system_event
        self._power_thread: threading.Thread | None = None
        self._pgood = Button(config.PGOOD_PIN, pull_up=True)
        self._chg = Button(config.CHG_PIN, pull_up=True)

    def run_power_monitor(self):
        """
        Runs the power monitor in a separate thread. If the thread is already running, it does nothing.
        """
        logger.debug("Starting power monitor")

        if self._power_thread is not None and self._power_thread.is_alive():
            return

        self._power_thread = threading.Thread(
            target=self._run_power_monitor,
            name="power-monitor",
            daemon=True,
        )

    def _stop_power_monitor(self):
        """
        Stops the power monitor thread.
        """
        if self._power_thread is not None and self._power_thread.is_alive():
            self._power_thread.join()
            self._power_thread = None

    def _run_power_monitor(self):
        """
        Monitor the battery charging state and log messages when it changes.
        """
        logger.info("Inside power monitor thread")
        logger.debug("Initial battery charging status: %s", self._is_battery_charging())
        previous_charging = False

        while not self.stop_system_event.is_set():
            logger.debug("Checking battery charging status %s", self._is_battery_charging())

            if self._is_battery_charging() and not previous_charging:
                logger.info("Battery is charging")
                self.capture_mode_event.clear()
                previous_charging = True
            elif not self._is_battery_charging() and previous_charging:
                logger.info("Battery is not charging")
                self.capture_mode_event.set()
                previous_charging = False

        self._stop_power_monitor()

    def _is_battery_charging(self) -> bool:
        """
        Both the CHG and PGOOD pins must be high for the battery to be considered charging.
        """
        return self._chg.is_pressed and self._pgood.is_pressed
