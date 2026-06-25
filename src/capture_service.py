import threading

from src.drivers.camera_driver import CameraDriver
from src.led_utils import led_on, led_off, led_blink_loop, led_blink
from src.motion_detector import MotionDetector
from src.utils import wait_for_next_capture
from src.config import (DEFAULT_CAPTURE_INTERVAL_SECONDS,
                        IDLE_CAPTURE_INTERVAL_SECONDS,
                        VIDEO_CAPTURE_INTERVAL_SECONDS,
                        VIDEO_DURATION_SECONDS)


class CaptureService:
    def __init__(self, motion_detector: MotionDetector):
        self.motion_detector = motion_detector
        self._camera = CameraDriver()
        self._storage = None
        self._capture_interval = DEFAULT_CAPTURE_INTERVAL_SECONDS

    def run_capture(
            self,
            stop_event: threading.Event,
            capture_mode_event: threading.Event,
    ) -> None:
        """
        Runs a loop to capture photos and videos.
        Will also detect motion and set the capture interval and mode based on it.

        The thread remains alive until shutdown is requested.
        When transfer mode is active, capturing is paused.
        """
        print("Running capture loop")

        camera_started = False
        errored = False

        try:
            led_on()
            self._camera.start_camera()
            camera_started = True

            while not stop_event.is_set():
                if not capture_mode_event.is_set():
                    led_off()
                    stop_event.wait(timeout=0.25)
                    continue

                led_on()

                match self.motion_detector.state:
                    case "IDLE":
                        self._capture_interval = IDLE_CAPTURE_INTERVAL_SECONDS
                        self._capture_photo()
                    case "ACTIVE":
                        self._capture_interval = VIDEO_CAPTURE_INTERVAL_SECONDS
                        self._capture_video()
                    case _:
                        self._capture_interval = DEFAULT_CAPTURE_INTERVAL_SECONDS
                        self._capture_photo()

                should_continue = wait_for_next_capture(
                    stop_event=stop_event,
                    capture_mode_event=capture_mode_event,
                    interval_seconds=self._capture_interval,
                )

                if not should_continue:
                    continue

        except Exception as e:
            errored = True
            print(f"Error running capture logic: {e}")

        finally:
            print("Stopping capture loop")
            led_off()

            if camera_started:
                self._camera.stop_camera()

        if errored and not stop_event.is_set():
            led_blink_loop(
                stop_event=stop_event,
                on_period_s=0.5,
                off_period_s=0.5,
            )

    def _capture_photo(self) -> None:
        """
        Captures a photo and saves it to the storage.
        """
        footage_path = self._camera.capture_jpeg()
        print(f"Captured photo: {footage_path}")

        led_blink(0, 0.2)
        led_on()

        # TODO: save footage_path to storage

    def _capture_video(self) -> None:
        """
        Captures a video and saves it to the storage.
        """
        video_blink_stop_event = threading.Event()

        video_blink_thread = threading.Thread(
            target=led_blink_loop,
            kwargs={
                "stop_event": video_blink_stop_event,
                "on_period_s": 1,
                "off_period_s": 0.2,
            },
            daemon=True,
        )

        video_blink_thread.start()

        try:
            footage_path = self._camera.capture_video(VIDEO_DURATION_SECONDS)
            # TODO: save footage_path to storage

        finally:
            video_blink_stop_event.set()
            video_blink_thread.join(timeout=1)
            led_on()
