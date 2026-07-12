from __future__ import annotations

from datetime import datetime


def _timestamp_name() -> str:
    # Example: 2026-06-24_12-47-19_123456
    return datetime.now().strftime("%Y-%m-%d_%H-%M-%S_%f")
