from dataclasses import dataclass
from uuid import UUID

from src.types.footage_item import FootageItem
from src.types.motion_state import MotionState


@dataclass
class CaptureEvent:
    """
    Represents a capture event, which may consist of one or more captured photos or videos.

    Attributes:
        id: Unique identifier for the capture event.
        started_at: Timestamp when the capture event started.
        ended_at: Timestamp when the capture event ended.
        motion_state: Current motion detection state during the capture event.
        footage_items: List of FootageItem objects associated with this capture event.
    """
    id: UUID | None
    started_at: str
    ended_at: str
    motion_state: MotionState
    footage_items: list[FootageItem] | None


@dataclass
class CaptureEventInsert:
    ended_at: str | None
    motion_state: MotionState
