import logging
import threading

from src.drivers.camera_driver import CameraDriver
from src.services.storage_service import storage_write_item
from src.types.footage_item import FootageType
from src.utils.led_utils import led_on, led_off, led_blink_loop, led_blink
from src.services.log_service import LogService
from src.services.motion_service import MotionService
from src.types.motion_state import MotionState
from src.config import (DEFAULT_CAPTURE_INTERVAL_SECONDS,
                        IDLE_CAPTURE_INTERVAL_SECONDS,
                        VIDEO_CAPTURE_INTERVAL_SECONDS,
                        VIDEO_DURATION_SECONDS)
from src.utils.utils import wait_for_next_capture


class CaptureService:
    def __init__(self, motion_service: MotionService, log_service: LogService):
        self.motion_service = motion_service
        self.log_service = log_service
        self._camera = CameraDriver()
        self._capture_interval = DEFAULT_CAPTURE_INTERVAL_SECONDS
        self._capture_thread: threading.Thread | None = None
        self._stop_event = threading.Event()

    def start(self) -> None:
        if self._capture_thread is not None and self._capture_thread.is_alive():
            return

        self.log_service.resume_capture_mode()
        self._capture_thread = threading.Thread(
            target=self._run_capture,
            name="capture",
            daemon=True,
        )
        self._capture_thread.start()

    def stop(self, timeout_s: float = 3.0) -> None:
        self.log_service.pause_capture_mode()
        self._stop_event.set()
        led_off()

        if self._capture_thread is not None:
            self._capture_thread.join(timeout=timeout_s)
            self._capture_thread = None

    def _run_capture(self) -> None:
        """
        Run a capture loop until stop is requested.
        Will also detect motion and set the capture interval and mode based on it.
        """
        print("Running capture loop")

        camera_started = False
        errored = False

        try:
            led_on()
            self._camera.start_camera()
            camera_started = True

            led_on()

            match self.motion_service.state:
                case MotionState.IDLE:
                    self._capture_interval = IDLE_CAPTURE_INTERVAL_SECONDS
                    self._capture_photo()
                case MotionState.ACTIVE:
                    self._capture_interval = VIDEO_CAPTURE_INTERVAL_SECONDS
                    self._capture_video()
                case _:
                    self._capture_interval = DEFAULT_CAPTURE_INTERVAL_SECONDS
                    self._capture_photo()

            wait_for_next_capture(
                stop_event=self._stop_event,
                interval_seconds=self._capture_interval,
            )

        except Exception as e:
            errored = True
            print(f"Error running capture logic: {e}")

        finally:
            print("Stopping capture loop")
            led_off()

            if camera_started:
                self._camera.stop_camera()

        if errored and not self._stop_event.is_set():
            led_blink_loop(
                stop_event=self._stop_event,
                on_period_s=0.5,
                off_period_s=0.5,
            )

    def _capture_photo(self) -> None:
        """
        Captures a photo and saves it to the storage.
        """
        footage_path = self._camera.capture_jpeg()
        logging.info(f"Captured photo: {footage_path}")

        self.log_service.record_footage_taken()

        storage_write_item(
            file_path=footage_path,
            size_bytes=footage_path.stat().st_size,
            footage_type=FootageType.PHOTO,
            motion_state=self.motion_service.state,
            duration_s=None,
            capture_end_at=None
        )

        led_blink(0, 0.2)
        led_on()

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
            footage_path, capture_end_at = self._camera.capture_video(VIDEO_DURATION_SECONDS)
            logging.info(f"Captured video: {footage_path}")
            self.log_service.record_footage_taken()

            storage_write_item(
                file_path=footage_path,
                size_bytes=footage_path.stat().st_size,
                footage_type=FootageType.VIDEO,
                motion_state=self.motion_service.state,
                duration_s=VIDEO_DURATION_SECONDS,
                capture_end_at=capture_end_at
            )


        finally:
            video_blink_stop_event.set()
            video_blink_thread.join(timeout=1)
            led_on()
