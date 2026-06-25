class MotionDetector:
    def __init__(self):
        """
        Initializes the motion detector.
        """
        self.is_moving = False

    def on_motion_detected(self) -> None:
        """
        Uses the gyroscope to determine the motion mode.
        """
        self.is_moving = True
