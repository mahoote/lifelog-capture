from pathlib import Path

"""
Project configuration.

Edit these values to change the capture timing and camera resolutions.
Sizes are written as (width, height) in pixels.
"""

BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data"
DATABASE_PATH = DATA_DIR / "lifelog.db"

BLE_DEVICE_NAME = "Lifelog Glasses"

BLE_SERVICE_UUID = "8f18b6c0-6d9f-4f3c-9fd5-111111111111"
BLE_WIFI_SCAN_UUID = "8f18b6c0-6d9f-4f3c-9fd5-222222222222"
BLE_WIFI_CREDENTIALS_UUID = "8f18b6c0-6d9f-4f3c-9fd5-333333333333"
BLE_WIFI_STATUS_UUID = "8f18b6c0-6d9f-4f3c-9fd5-444444444444"
BLE_TRANSFER_STATUS_UUID = "8f18b6c0-6d9f-4f3c-9fd5-555555555555"
BLE_TRANSFER_COMMAND_UUID = "8f18b6c0-6d9f-4f3c-9fd5-666666666666"

# Time between captures when capture mode is active.
IDLE_CAPTURE_INTERVAL_SECONDS = 300  # User is not moving, so we can take photos less frequently.
DEFAULT_CAPTURE_INTERVAL_SECONDS = 120  # User is moving, so we can take photos more frequently.
VIDEO_CAPTURE_INTERVAL_SECONDS = 180  # User is moving a lot, so we can capture videos.

# Length of each video clip when motion is detected.
VIDEO_DURATION_SECONDS = 10

# Still photo resolution.
PHOTO_SIZE = (1920, 1080)

# Video recording resolution.
VIDEO_SIZE = (1280, 720)
