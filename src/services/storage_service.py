import logging
from pathlib import Path

from src.database import insert_footage_item, update_item_state, delete_item_by_id, \
    select_item_by_id, select_pending_capture_events, insert_capture_event
from src.types.capture_event import CaptureEvent, CaptureEventInsert
from src.types.footage_item import FootageType, FootageItemInsert, FootageItem, FootageState, FootageRole
from src.types.motion_state import MotionState

logger = logging.getLogger(__name__)


def create_capture_event(ended_at: str | None, motion_state: MotionState) -> None:
    """
    Creates a new capture event in the database.
    """
    new_capture_event = CaptureEventInsert(
        ended_at=ended_at,
        motion_state=motion_state
    )

    insert_capture_event(new_capture_event)


def save_footage_item(file_path: Path,
                      size_bytes: int,
                      footage_type: FootageType,
                      duration_s: int | None) -> None:
    """
    Writes a new footage item to the database.
    Only includes the minimum required fields.
    """
    new_footage_item = FootageItemInsert(
        capture_event_id=None,  # TODO: Dynamic
        sequence_index=0,  # TODO: Dynamic
        type=footage_type,
        role=FootageRole.SELECTED,  # TODO: Dynamic
        file_path=file_path,
        size_bytes=size_bytes,
        duration_s=duration_s,
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


def list_pending_capture_events() -> list[CaptureEvent]:
    """
    Returns a list of all pending capture events in the database.
    """
    return select_pending_capture_events()


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
