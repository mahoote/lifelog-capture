import logging
from datetime import datetime
from pathlib import Path

from src.database import add_item, get_pending_items, set_item_state, delete_item_by_id
from src.types.footage_item import FootageType, FootageItemInsert, FootageItem, FootageState
from src.types.motion_state import MotionState
from src.utils.math_utils import calculate_sha256


logger = logging.getLogger(__name__)


def write_item(file_path: Path, size_bytes: int, footage_type: FootageType, motion_state: MotionState,
               duration_s: int | None,
               capture_end_at: datetime | None) -> None:
    """
    Writes a new footage item to the database.
    Only includes the minimum required fields.
    """
    sha256 = calculate_sha256(file_path)

    if not sha256:
        logger.error(f"Failed to calculate SHA256 for file {file_path}.")

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


def update_state(item_id: str, new_state: FootageState) -> bool:
    """
    Updates the state of a footage item in the database.
    """
    if not isinstance(new_state, FootageState):
        logger.error(f"Invalid state '{new_state}' provided for item {item_id}.")
        return False

    return set_item_state(item_id, new_state)


def list_pending() -> list[FootageItem]:
    """
    Returns a list of all pending footage items in the database.
    """
    return get_pending_items()


def delete_item(item_id: str) -> None:
    """
    Deletes a footage item from the database.
    """
    success = delete_item_by_id(item_id)

    if not success:
        logger.error(f"Failed to delete item with ID {item_id}.")
