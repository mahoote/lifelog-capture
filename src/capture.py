from src.camera_driver import CameraDriver

_camera = CameraDriver()
_motion = None
_storage = None
_clock = None

_capture_interval = 60
_video_duration = 10
_photo_quality = 95
_is_moving = False


def run_capture() -> None:
    """
    Runs a loop to capture photos and videos.
    Will also detect motion and set the capture interval and mode based on it.
    """
    print('Running capture loop')
    try:
        _camera.start_camera()

        if _is_moving:
            _capture_video()
        else:
            _capture_photo()

    except Exception as e:
        print(f"Error running capture logic: {e}")
    finally:
        _camera.stop_camera()


def _capture_photo() -> None:
    """
    Captures a photo and saves it to the storage.
    """
    jpeg_bytes = _camera.capture_jpeg(_photo_quality)
    # TODO: save jpeg_bytes to storage


def _capture_video() -> None:
    """
    Captures a video and saves it to the storage.
    """
    video_bytes = _camera.capture_video(_video_duration)
    # TODO: save video_bytes to storage


def _on_motion_detected() -> None:
    """
    Uses the gyroscope to determine the motion mode.
    """
    pass
