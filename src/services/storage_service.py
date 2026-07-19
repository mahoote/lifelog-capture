import logging
from datetime import datetime
from pathlib import Path

from src.database import insert_footage_item, select_pending_items, update_item_state, delete_item_by_id, \
    select_item_by_id
from src.types.footage_item import FootageType, FootageItemInsert, FootageItem, FootageState, FootageRole
from src.types.motion_state import MotionState
from src.utils.math_utils import calculate_sha256

logger = logging.getLogger(__name__)


def create_capture_event(motion_state: MotionState) -> None:
    """
    Creates a new capture event in the database.
    """
    pass


def save_footage_item(file_path: Path, size_bytes: int, footage_type: FootageType, motion_state: MotionState,
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
        capture_event_id=None,  # TODO: Dynamic
        sequence_index=0,  # TODO: Dynamic
        type=footage_type,
        role=FootageRole.SELECTED,  # TODO: Dynamic
        file_path=file_path,
        size_bytes=size_bytes,
        sha256=sha256,
        duration_s=duration_s,
        capture_end_at=capture_end_at
    )

    insert_footage_item(new_footage_item)


def update_footage_state(item_id: str, new_state: FootageState) -> bool:
    """
    Updates the state of a footage item in the database.
    """
    if not isinstance(new_state, FootageState):
        logger.error(f"Invalid state '{new_state}' provided for item {item_id}.")
        return False

    return update_item_state(item_id, new_state)


def list_pending_footage() -> list[FootageItem]:
    """
    Returns a list of all pending footage items in the database.
    """
    return select_pending_items()


def get_footage_item(item_id: str) -> FootageItem | None:
    """
    Returns one footage item by ID.
    """
    return select_item_by_id(item_id)


def delete_footage_item(item_id: str) -> None:
    """
    Deletes a footage item from the database.
    """
    success = delete_item_by_id(item_id)

    if not success:
        logger.error(f"Failed to delete item with ID {item_id}.")
