from datetime import datetime
from pathlib import Path

from src.database import add_item
from src.types.footage_item import FootageType, FootageItemInsert
from src.types.motion_state import MotionState
from src.utils.math_utils import calculate_sha256


def storage_write_item(file_path: Path, size_bytes: int, footage_type: FootageType, motion_state: MotionState,
                       duration_s: int | None,
                       capture_end_at: datetime | None) -> None:
    """
    Writes a new footage item to the database.
    Only includes the minimum required fields.
    """
    sha256 = calculate_sha256(file_path)

    new_footage_item = FootageItemInsert(
        type=footage_type,
        file_path=file_path,
        size_bytes=size_bytes,
        sha256=sha256,
        duration_s=duration_s,
        capture_end_at=capture_end_at,
        motion_state=motion_state
    )

    add_item(new_footage_item)
