from datetime import datetime
from pathlib import Path

import sqlite3
from uuid import UUID

from src.types.footage_item import FootageItem, FootageRole, FootageState, FootageType
from src.utils.date_utils import parse_datetime


def row_to_footage_item(row: sqlite3.Row) -> FootageItem:
    """Convert a database row into the in-memory FootageItem model."""

    return FootageItem(
        id=UUID(row["id"]),
        capture_event_id=UUID(row["capture_event_id"]) if row["capture_event_id"] else None,
        sequence_index=row["sequence_index"],
        type=FootageType(row["type"]),
        role=FootageRole(row["role"]),
        created_at=datetime.fromisoformat(row["created_at"]),
        file_path=Path(row["file_path"]),
        size_bytes=row["size_bytes"],
        state=FootageState(row["state"]),
        attempt=row["attempt"],
        last_attempt_at=parse_datetime(row["last_attempt_at"]),
        last_error=row["last_error"],
        duration_s=row["duration_s"],
        acked_at=parse_datetime(row["acked_at"]),
    )
