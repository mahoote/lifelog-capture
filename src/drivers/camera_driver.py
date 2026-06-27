from __future__ import annotations

from libcamera import Transform
from picamera2 import Picamera2
from picamera2.encoders import H264Encoder
from datetime import datetime, timezone
from pathlib import Path
from time import sleep
from typing import Literal

from src.config import PHOTO_SIZE, VIDEO_SIZE
from src.types.motion_state import MotionState


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
        self.camera_transform = Transform(hflip=1, vflip=1)

        self.photo_config: dict = self.picam2.create_still_configuration(
            main={"size": PHOTO_SIZE},
            transform=self.camera_transform,
        )

        self.video_config: dict = self.picam2.create_video_configuration(
            main={"size": VIDEO_SIZE},
            transform=self.camera_transform,
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

    from datetime import datetime, timezone
    from pathlib import Path

    def capture_video(
            self,
            seconds: int,
    ) -> tuple[Path, datetime]:
        """
        Record a video clip, save it under footage/<timestamp>.h264,
        and return the saved file path along with the time recording ended.

        The camera switches to video mode, records for the specified
        duration, and stores the recording on disk.

        Args:
            seconds: Length of the recording in seconds.

        Returns:
            tuple[Path, datetime]:
                - Path to the saved video file.
                - UTC timestamp when recording finished.
        """
        out_path = self.footage_dir / f"{_timestamp_name()}.h264"

        encoder = H264Encoder()
        self._switch_mode("video")

        self.picam2.start_recording(encoder, str(out_path))
        sleep(seconds)
        self.picam2.stop_recording()

        capture_end_at = datetime.now(timezone.utc)

        return out_path, capture_end_at

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
