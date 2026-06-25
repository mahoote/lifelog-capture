"""
Project configuration.

Edit these values to change the capture timing and camera resolutions.
Sizes are written as (width, height) in pixels.
"""

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
