import sqlite3
from uuid import UUID

from src.types.capture_event import CaptureEvent
from src.types.motion_state import MotionState


def row_to_capture_event(row: sqlite3.Row) -> CaptureEvent:
    return CaptureEvent(
        id=UUID(row["id"]),
        started_at=row["started_at"],
        ended_at=row["ended_at"],
        motion_state=MotionState(row["motion_state"]),
        footage_items=None,
    )
