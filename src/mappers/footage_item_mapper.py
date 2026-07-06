from datetime import datetime
from pathlib import Path

import sqlite3

from src.types.footage_item import FootageItem, FootageState, FootageType
from src.types.motion_state import MotionState


def row_to_footage_item(row: sqlite3.Row) -> FootageItem:
    """Convert a database row into the in-memory FootageItem model."""

    return FootageItem(
        id=row["id"],
        type=FootageType(row["type"]),
        created_at=datetime.fromisoformat(row["created_at"]),
        file_path=Path(row["file_path"]),
        size_bytes=row["size_bytes"],
        motion_state=MotionState(row["motion_state"]),
        state=FootageState(row["state"]),
        attempt=row["attempts"] if "attempts" in row.keys() else row["attempt"],
        sha256=row["sha256"],
        last_attempt_at=_parse_datetime(row["last_attempt_at"]),
        last_error=row["last_error"],
        duration_s=row["duration_s"],
        capture_end_at=_parse_datetime(row["capture_end_at"]),
        acked_at=_parse_datetime(row["acked_at"]),
    )


def _parse_datetime(value: str | None) -> datetime | None:
    if value is None:
        return None

    return datetime.fromisoformat(value)
