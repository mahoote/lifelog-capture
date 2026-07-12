from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from time import sleep
from typing import Literal

from src.utils.date_utils import _timestamp_name

try:
    from libcamera import Transform
    from picamera2 import Picamera2
    from picamera2.encoders import H264Encoder
    from picamera2.outputs import FfmpegOutput
except Exception as exc:  # Allows parent code to inspect camera availability.
    Transform = None  # type: ignore[assignment]
    Picamera2 = None  # type: ignore[assignment]
    H264Encoder = None  # type: ignore[assignment]
    FfmpegOutput = None  # type: ignore[assignment]
    PICAMERA_IMPORT_ERROR = exc
else:
    PICAMERA_IMPORT_ERROR = None

from src.configs.config import PHOTO_SIZE, VIDEO_SIZE


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
        self.camera_available = False
        self.camera_error: str | None = None
        self.picam2: Picamera2 | None = None
        self.camera_transform = None
        self.photo_config: dict | None = None
        self.video_config: dict | None = None

        if PICAMERA_IMPORT_ERROR is not None:
            self.camera_error = str(PICAMERA_IMPORT_ERROR)
        else:
            try:
                self.picam2 = Picamera2()
                self.camera_transform = Transform(hflip=1, vflip=1)

                self.photo_config = self.picam2.create_still_configuration(
                    main={"size": PHOTO_SIZE},
                    transform=self.camera_transform,
                )

                self.video_config = self.picam2.create_video_configuration(
                    main={
                        "size": VIDEO_SIZE,
                        "format": "YUV420",
                    },
                    controls={
                        "FrameRate": 30,
                    },
                    transform=self.camera_transform,
                )
            except Exception as exc:
                self.camera_error = str(exc)
                self.picam2 = None

        self.footage_dir = Path(footage_dir)
        self.footage_dir.mkdir(parents=True, exist_ok=True)
        self.current_mode: Literal["photo", "video"] | None = None

    def start_camera(self) -> bool:
        """
        Configure and start the camera.

        The camera is initialized using the still-image configuration
        and becomes ready for capturing photos or recording videos.

        Returns:
            bool: True if the camera started, False otherwise.
        """
        if self.picam2 is None or self.photo_config is None:
            self.camera_available = False
            if self.camera_error is None:
                self.camera_error = "Camera is not initialized."
            return False

        try:
            self.picam2.configure(self.photo_config)
            self.picam2.start()
        except Exception as exc:
            self.camera_available = False
            self.camera_error = str(exc)
            self.current_mode = None
            return False

        self.camera_available = True
        self.camera_error = None
        self.current_mode = "photo"
        sleep(1)
        return True

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

        self._ensure_camera_available()
        self._switch_mode("photo")
        self.picam2.capture_file(
            str(out_path),
            format="jpeg",
        )
        return out_path

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

        out_path = self.footage_dir / f"{_timestamp_name()}.mp4"

        self._ensure_camera_available()

        self._switch_mode("video")

        # Let exposure, gain, and buffers settle after switching mode.
        sleep(2)

        encoder = H264Encoder(bitrate=8_000_000)
        output = FfmpegOutput(str(out_path))

        self.picam2.start_recording(encoder, output)
        sleep(seconds)
        self.picam2.stop_recording()

        capture_end_at = datetime.now(timezone.utc)

        return out_path, capture_end_at

    def stop_camera(self) -> None:
        """
        Stop the camera and release camera resources.
        """
        if self.picam2 is None or not self.camera_available:
            return

        self.picam2.stop()
        self.camera_available = False
        self.current_mode = None

    def _switch_mode(self, mode: Literal["photo", "video"]) -> None:
        """
        Switch camera mode only if the requested mode is not active.
        """
        self._ensure_camera_available()

        if self.current_mode == mode:
            return

        if mode == "photo":
            self.picam2.switch_mode(self.photo_config)
        else:
            self.picam2.switch_mode(self.video_config)

        self.current_mode = mode

    def _ensure_camera_available(self) -> None:
        """
        Raise a clear error if the camera is not available.
        """
        if self.picam2 is None or not self.camera_available:
            error = self.camera_error or "Camera is not available."
            raise RuntimeError(error)
