from __future__ import annotations

from datetime import datetime


def timestamp_name() -> str:
    # Example: 2026-06-24_12-47-19_123456
    return datetime.now().strftime("%Y-%m-%d_%H-%M-%S_%f")


def timestamp_utc() -> str:
    return datetime.now().isoformat()


def parse_datetime(value: str | None) -> datetime | None:
    if value is None:
        return None

    return datetime.fromisoformat(value)
