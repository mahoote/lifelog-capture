import threading
from src.camera_driver import CameraDriver
from src.led_utils import led_on, led_off, led_blink_loop, led_blink
from src.motion_detector import MotionDetector
from src.utils import wait_for_next_capture

motion = MotionDetector()
_camera = CameraDriver()
_storage = None
_clock = None

_capture_interval = 10  # TODO: make this configurable
_video_duration = 10


def run_capture(
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
        _camera.start_camera()
        camera_started = True

        while not stop_event.is_set():
            # TODO: Use when transfer mode is implemented
            # if not capture_mode_event.is_set():
            #     led_off()
            #     stop_event.wait(timeout=0.25)
            #     continue

            led_on()

            if _motion.is_moving:
                _capture_video()
            else:
                _capture_photo()

            should_continue = wait_for_next_capture(
                stop_event=stop_event,
                capture_mode_event=capture_mode_event,
                interval_seconds=_capture_interval,
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
            _camera.stop_camera()

    if errored and not stop_event.is_set():
        led_blink_loop(
            stop_event=stop_event,
            on_period_s=0.5,
            off_period_s=0.5,
        )


def _capture_photo() -> None:
    """
    Captures a photo and saves it to the storage.
    """
    footage_path = _camera.capture_jpeg()
    print(f"Captured photo: {footage_path}")

    led_blink(0, 0.2)
    led_on()

    # TODO: save footage_path to storage


def _capture_video() -> None:
    """
    Captures a video and saves it to the storage.
    """
    video_blink_stop_event = threading.Event()

    video_blink_thread = threading.Thread(
        target=led_blink_loop,
        kwargs={
            "stop_event": video_blink_stop_event,
            "on_period_s": 0.25,
            "off_period_s": 0.75,
        },
        daemon=True,
    )

    video_blink_thread.start()

    try:
        footage_path = _camera.capture_video(_video_duration)
        # TODO: save footage_path to storage

    finally:
        video_blink_stop_event.set()
        video_blink_thread.join(timeout=1)
        led_on()
