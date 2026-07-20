from datetime import datetime
from pathlib import Path

import sqlite3

from src.types.footage_item import FootageItem, FootageState, FootageType
from src.utils.date_utils import parse_datetime


def row_to_footage_item(row: sqlite3.Row) -> FootageItem:
    """Convert a database row into the in-memory FootageItem model."""

    return FootageItem(
        id=row["id"],
        capture_event_id=row["capture_event_id"],
        sequence_index=row["sequence_index"],
        type=FootageType(row["type"]),
        role=row["role"],
        created_at=datetime.fromisoformat(row["created_at"]),
        file_path=Path(row["file_path"]),
        size_bytes=row["size_bytes"],
        state=FootageState(row["state"]),
        attempt=row["attempts"] if "attempts" in row.keys() else row["attempt"],
        last_attempt_at=parse_datetime(row["last_attempt_at"]),
        last_error=row["last_error"],
        duration_s=row["duration_s"],
        acked_at=parse_datetime(row["acked_at"]),
    )
