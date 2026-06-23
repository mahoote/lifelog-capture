from pathlib import Path
from tempfile import NamedTemporaryFile
from time import sleep

from picamera2 import Picamera2
from picamera2.encoders import H264Encoder


class CameraDriver:
    def __init__(self) -> None:
        """
        Initialize the camera driver and create configurations for
        still image capture and video recording.

        Creates:
            self.picam2: Picamera2 camera instance.
            self.photo_config: Configuration used for still photos.
            self.video_config: Configuration used for video recording.
        """
        self.picam2: Picamera2 = Picamera2()
        self.photo_config: dict = self.picam2.create_still_configuration()
        self.video_config: dict = self.picam2.create_video_configuration()

    def start_camera(self) -> None:
        """
        Configure and start the camera.

        The camera is initialized using the still-image configuration
        and becomes ready for capturing photos or recording videos.

        Returns:
            None
        """
        self.picam2.configure(self.photo_config)
        self.picam2.start()

    def capture_jpeg(self, quality: int) -> bytes:
        """
        Capture a JPEG image and return it as raw bytes.

        The camera switches to still mode, captures a JPEG image,
        temporarily stores it on disk, and then reads the file back
        into memory.

        Args:
            quality: JPEG compression quality from 1 to 100.
                     Higher values give better image quality but
                     produce larger files. Default is 85.

        Returns:
            bytes: The complete JPEG image as a bytes object.
        """
        temp_path = Path("/tmp/camera_capture.jpg")

        self.picam2.switch_mode(self.photo_config)
        self.picam2.capture_file(
            str(temp_path),
            format="jpeg",
            quality=quality,
        )

        return temp_path.read_bytes()

    def record_clip(self, seconds: int) -> bytes:
        """
        Record a video clip and return it as raw H.264 bytes.

        The camera switches to video mode, records for the specified
        duration, stores the recording in a temporary file, and then
        loads the file into memory.

        Args:
            seconds: Length of the recording in seconds.

        Returns:
            bytes: The recorded video encoded in H.264 format.
        """
        with NamedTemporaryFile(suffix=".h264", delete=True) as temp_file:
            encoder = H264Encoder()

            self.picam2.switch_mode(self.video_config)
            self.picam2.start_recording(encoder, temp_file.name)

            sleep(seconds)

            self.picam2.stop_recording()

            return Path(temp_file.name).read_bytes()

    def stop_camera(self) -> None:
        """
        Stop the camera and release camera resources.

        Returns:
            None
        """
        self.picam2.stop()
