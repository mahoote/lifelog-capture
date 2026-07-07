import threading
from gpiozero import Button


class PowerService:
    def __init__(self,
                 pgood: Button,
                 chg: Button,
                 capture_mode_event: threading.Event):
        self.pgood = pgood
        self.chg = chg
        self.capture_mode_event = capture_mode_event
        self._power_thread: threading.Thread | None = None

    def run_power_monitor(self):
        """
        Runs the power monitor in a separate thread. If the thread is already running, it does nothing.
        """
        if self._power_thread is not None and self._power_thread.is_alive():
            return

        self._power_thread = threading.Thread(
            target=self._run_power_monitor,
            name="power-monitor",
            daemon=True,
        )

    def _run_power_monitor(self):
        """
        Monitor the battery charging state and print messages when it changes.
        """
        previous_charging = False

        while True:
            if self._is_battery_charging() and not previous_charging:
                print("Battery is charging")
                self.capture_mode_event.clear()
                previous_charging = True
            elif not self._is_battery_charging() and previous_charging:
                print("Battery is not charging")
                self.capture_mode_event.set()
                previous_charging = False

    def _is_battery_charging(self) -> bool:
        return self.chg.is_pressed and self.pgood.is_pressed
