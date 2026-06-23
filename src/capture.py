camera = None
motion = None
storage = None
clock = None

capture_interval = 0
video_duration = 0
quality = '720'
is_moving = False

def run_capture():
    """ Runs a loop to capture photos and videos.
    Will also detect motion and set the capture interval and mode based on it. """
    print('Running capture loop')

def capture_photo():
    """ Captures a photo and saves it to the storage."""
    pass

def capture_video():
    """ Captures a video and saves it to the storage."""
    pass

def on_motion_detected():
    """ Uses the gyroscope to determine the motion mode."""
    pass

def set_quality(quality):
    """ Sets the quality of the captured photos and videos."""
    pass