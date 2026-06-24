from __future__ import annotations

from datetime import datetime
from pathlib import Path
from time import sleep
from typing import Literal

from picamera2 import Picamera2
from picamera2.encoders import H264Encoder


def _timestamp_name() -> str:
    # Example: 2026-06-24_12-47-19_123456
    return datetime.now().strftime("%Y-%m-%d_%H-%M-%S_%f")


class CameraDriver:
    def __init__(self, footage_dir: str | Path = "footage") -> None:
        """
        Initialize the camera driver and create configurations for
        still image capture and video recording.
        Also sets up the output directory for saved media.

        Creates:
            self.picam2: Picamera2 camera instance.
            self.photo_config: Configuration used for still photos.
            self.video_config: Configuration used for video recording.
        """
        self.picam2: Picamera2 = Picamera2()
        self.photo_config: dict = self.picam2.create_still_configuration(
            main={"size": (1920, 1080)}
        )

        self.video_config: dict = self.picam2.create_video_configuration(
            main={"size": (1280, 720)}
        )

        self.footage_dir = Path(footage_dir)
        self.footage_dir.mkdir(parents=True, exist_ok=True)
        self.current_mode: Literal["photo", "video"] | None = None

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
        self.current_mode = "photo"
        sleep(1)

    def capture_jpeg(self) -> Path:
        """
        Capture a JPEG image, save it under footage/<timestamp>.jpeg,
        and return the saved file path.

        The camera switches to still mode, captures a JPEG image,
        temporarily stores it on disk, and then reads the file back
        into memory.

        Returns:
            Path: The path to the saved JPEG image.
        """
        out_path = self.footage_dir / f"{_timestamp_name()}.jpeg"

        self._switch_mode("photo")
        self.picam2.capture_file(
            str(out_path),
            format="jpeg",
        )
        return out_path

    def capture_video(self, seconds: int) -> Path:
        """
        Record a video clip, save it under footage/<timestamp>.h264,
        and return the saved file path.

        The camera switches to video mode, records for the specified
        duration, stores the recording in a temporary file, and then
        loads the file into memory.

        Args:
            seconds: Length of the recording in seconds.

        Returns:
            Path: The path to the saved video file.
        """
        out_path = self.footage_dir / f"{_timestamp_name()}.h264"

        encoder = H264Encoder()
        self._switch_mode("video")

        print("Recording video...")

        self.picam2.start_recording(encoder, str(out_path))
        sleep(seconds)
        self.picam2.stop_recording()

        print("Video recording complete")

        return out_path

    def stop_camera(self) -> None:
        """
        Stop the camera and release camera resources.
        """
        self.picam2.stop()

    def _switch_mode(self, mode: Literal["photo", "video"]) -> None:
        """
        Switch camera mode only if the requested mode is not active.
        """
        if self.current_mode == mode:
            return

        if mode == "photo":
            self.picam2.switch_mode(self.photo_config)
        else:
            self.picam2.switch_mode(self.video_config)

        self.current_mode = mode
