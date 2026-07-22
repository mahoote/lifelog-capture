from __future__ import annotations

import logging
import subprocess
from pathlib import Path
from time import sleep, monotonic
from typing import Literal

from src.utils.date_utils import timestamp_name

try:
    from libcamera import Transform
    from picamera2 import Picamera2
    from picamera2.encoders import H264Encoder
    from picamera2.outputs import FileOutput
except Exception as exc:  # Allows parent code to inspect camera availability.
    Transform = None  # type: ignore[assignment]
    Picamera2 = None  # type: ignore[assignment]
    H264Encoder = None  # type: ignore[assignment]
    FileOutput = None  # type: ignore[assignment]
    PICAMERA_IMPORT_ERROR = exc
else:
    PICAMERA_IMPORT_ERROR = None

from src.configs.config import PHOTO_SIZE, VIDEO_SIZE

logger = logging.getLogger(__name__)


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
        self.videos_dir = self.footage_dir / "videos"

        self.footage_dir.mkdir(parents=True, exist_ok=True)
        self.videos_dir.mkdir(parents=True, exist_ok=True)
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

    def capture_jpg(self) -> Path:
        """
        Capture a JPG image, save it under footage/<timestamp>.jpg,
        and return the saved file path.

        The camera switches to still mode, captures a JPG image,
        temporarily stores it on disk, and then reads the file back
        into memory.

        Returns:
            Path: The path to the saved JPG image.
        """
        out_path = self.footage_dir / f"{timestamp_name()}.jpg"

        self._ensure_camera_available()
        self._switch_mode("photo")
        self.picam2.capture_file(
            str(out_path),
            format="jpg",
        )
        return out_path

    def capture_video(
            self,
            seconds: int,
    ) -> Path:
        """
        Record a video clip as raw H264, remux it to MP4 with a fixed framerate,
        and return the saved MP4 path.
        """
        video_path, _photo_paths = self.capture_video_with_extracted_photos(
            seconds=seconds,
            photo_count=0,
        )
        return video_path

    def capture_video_with_extracted_photos(
            self,
            seconds: int,
            photo_count: int = 3,
            photo_interval_s: float = 3.0,
    ) -> tuple[Path, list[Path]]:
        """
        Record a video and extract JPG snapshots from the final MP4.

        The camera only records video during the capture window. Photos are
        extracted afterwards with ffmpeg so the encoder is not interrupted while
        recording.
        """
        raw_path = self.videos_dir / f"{timestamp_name()}.h264"
        mp4_path = raw_path.with_suffix(".mp4")

        self._ensure_camera_available()
        self._switch_mode("video")

        # Give the camera pipeline time to settle after still -> video mode switch.
        sleep(3)

        encoder = H264Encoder(bitrate=8_000_000, repeat=True)
        output = FileOutput(str(raw_path))

        logger.info("Video recording started: %s", raw_path)

        recording_started = monotonic()
        self.picam2.start_recording(encoder, output)

        try:
            sleep(seconds)
        finally:
            self.picam2.stop_recording()

        recording_elapsed = monotonic() - recording_started

        logger.info(
            "Video recording stopped: path=%s requested=%ss elapsed=%.2fs size=%s",
            raw_path,
            seconds,
            recording_elapsed,
            raw_path.stat().st_size if raw_path.exists() else None,
        )

        subprocess.run(
            [
                "ffmpeg",
                "-y",
                "-framerate",
                "30",
                "-i",
                str(raw_path),
                "-c",
                "copy",
                str(mp4_path),
            ],
            check=True,
        )

        raw_path.unlink(missing_ok=True)

        logger.info("Converted video to MP4: %s", mp4_path)

        photo_paths = self._extract_video_photos(
            video_path=mp4_path,
            seconds=seconds,
            photo_count=photo_count,
            photo_interval_s=photo_interval_s,
        )

        return mp4_path, photo_paths

    def _extract_video_photos(
            self,
            video_path: Path,
            seconds: int,
            photo_count: int,
            photo_interval_s: float,
    ) -> list[Path]:
        """
        Extract JPG snapshots from a recorded MP4 using ffmpeg.
        """
        photo_paths: list[Path] = []

        for i in range(photo_count):
            timestamp_s = i * photo_interval_s
            if timestamp_s >= seconds:
                break

            photo_path = self.footage_dir / f"{timestamp_name()}_{i}.jpg"

            subprocess.run(
                [
                    "ffmpeg",
                    "-y",
                    "-ss",
                    str(timestamp_s),
                    "-i",
                    str(video_path),
                    "-frames:v",
                    "1",
                    "-q:v",
                    "2",
                    str(photo_path),
                ],
                check=True,
            )

            photo_paths.append(photo_path)
            logger.info(
                "Extracted video-frame photo: path=%s timestamp=%.2fs",
                photo_path,
                timestamp_s,
            )

        return photo_paths

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
