camera = None
motion = None
storage = None
clock = None

capture_interval = 0
video_duration = 0
photo_quality = 95
is_moving = False


def run_capture():
    """
    Runs a loop to capture photos and videos.
    Will also detect motion and set the capture interval and mode based on it.
    """
    print('Running capture loop')


def _capture_photo():
    """
    Captures a photo and saves it to the storage.
    """
    pass


def _capture_video():
    """
    Captures a video and saves it to the storage.
    """
    pass


def _on_motion_detected():
    """
    Uses the gyroscope to determine the motion mode.
    """
    pass


def _set_quality(quality):
    """
    Sets the quality of the captured photos and videos.
    """
    pass
