from pathlib import Path
from dataclasses import dataclass

"""
Project configuration.

Edit these values to change the capture timing and camera resolutions.
Sizes are written as (width, height) in pixels.
"""

BASE_DIR = Path(__file__).resolve().parent.parent.parent
DATA_DIR = BASE_DIR / "data"
DATABASE_PATH = DATA_DIR / "lifelog.db"

HTTP_HOST = "0.0.0.0"
HTTP_PORT = 8000

# Time between captures when capture mode is active.
IDLE_CAPTURE_INTERVAL_SECONDS = 300  # User is not moving, so we can take photos less frequently.
DEFAULT_CAPTURE_INTERVAL_SECONDS = 60  # User is moving, so we can take photos more frequently.
VIDEO_CAPTURE_INTERVAL_SECONDS = 60  # User is moving a lot, so we can capture videos.

# Length of each video clip when motion is detected.
VIDEO_DURATION_SECONDS = 15

# Still photo resolution.
PHOTO_SIZE = (1920, 1080)

# Video recording resolution.
VIDEO_SIZE = (1280, 720)


@dataclass(frozen=True)
class PowerConfig:
    PGOOD_PIN: int = 22
    CHG_PIN: int = 27


@dataclass(frozen=True)
class AppConfig:
    BUTTON_PIN: int = 26
    BMI160_ADDRESS: int = 0x69
    BUTTON_BOUNCE_TIME_S: float = 0.05
    BUTTON_HOLD_TIME_S: float = 3.0
    LOGS_DIR: str = "logs"
