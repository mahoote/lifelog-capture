from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from pathlib import Path
from uuid import UUID


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


@dataclass
class FootageItem:
    """
    Represents a single captured photo or video.

    Attributes:
        id: Unique identifier for the capture.
        type: Whether the capture is a photo or video.
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

    id: UUID
    type: FootageType
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
