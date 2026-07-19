from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from pathlib import Path
from uuid import UUID

from src.types.motion_state import MotionState


class FootageType(StrEnum):
    """Supported types of captured footage."""

    PHOTO = "photo"
    VIDEO = "video"


class FootageState(StrEnum):
    """Current upload/synchronization state of a capture."""

    PENDING = "pending"
    UPLOADING = "uploading"
    ACKED = "acked"
    FAILED = "failed"


class FootageRole(StrEnum):
    """Role of the footage item in the capture event."""

    BURST = "burst"  # Used for photos
    SELECTED = "selected"  # Used for photos
    CONTEXT = "context"  # Used for video clips


@dataclass
class FootageItem:
    """
    Represents a single captured photo or video.

    Attributes:
        id: Unique identifier for the capture.
        capture_event_id: Identifier of the associated capture event.
        sequence_index: Order of the capture within the event.
        type: Whether the capture is a photo or video.
        role: Role of the capture in the event (e.g., burst, selected, context).
        created_at: Timestamp when the capture was created.
        file_path: Location of the file on disk.
        size_bytes: Size of the file in bytes.
        state: Current upload state.
        attempt: Number of upload attempts made.
        sha256: Optional SHA-256 checksum of the file.
        last_attempt_at: Timestamp of the most recent upload attempt.
        last_error: Description of the most recent upload failure.
        duration_s: Duration in seconds for videos.
        capture_end_at: Time when recording finished.
        acked_at: Time when the server acknowledged receipt.
    """

    id: UUID | None
    capture_event_id: UUID | None
    sequence_index: int
    type: FootageType
    role: FootageRole
    created_at: datetime
    file_path: Path
    size_bytes: int
    state: FootageState = FootageState.PENDING
    attempt: int = 0
    sha256: str | None = None
    last_attempt_at: datetime | None = None
    last_error: str | None = None
    duration_s: int | None = None
    capture_end_at: datetime | None = None
    acked_at: datetime | None = None


@dataclass
class FootageItemInsert:
    capture_event_id: UUID | None
    sequence_index: int
    type: FootageType
    role: FootageRole
    file_path: Path
    size_bytes: int
    sha256: str
    duration_s: int | None
    capture_end_at: datetime | None
