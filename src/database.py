import sqlite3
import json
from uuid import uuid4

from src.configs.config import DATA_DIR, DATABASE_PATH
from src.mappers.footage_item_mapper import row_to_footage_item
from src.types.capture_event import CaptureEvent
from src.types.footage_item import FootageItem, FootageState, FootageItemInsert


def get_connection() -> sqlite3.Connection:
    """
    Create and return a connection to the SQLite database.

    The data directory is created automatically if it does not exist.
    Rows are returned as sqlite3.Row objects, allowing column access
    by name.

    Returns:
        sqlite3.Connection: Configured SQLite connection.
    """
    DATA_DIR.mkdir(parents=True, exist_ok=True)

    connection = sqlite3.connect(DATABASE_PATH)
    connection.execute("PRAGMA foreign_keys = ON")
    connection.row_factory = sqlite3.Row

    return connection


def init_database() -> None:
    """
    Create all required database tables if they do not already exist.
    """
    with get_connection() as connection:
        cursor = connection.cursor()

        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS capture_event (
                id TEXT PRIMARY KEY,
                started_at TEXT NOT NULL,
                ended_at TEXT NOT NULL,
                motion_state TEXT NOT NULL
            )
            """
        )

        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS footage_item (
                id TEXT PRIMARY KEY,
                capture_event_id TEXT NOT NULL,
                sequence_index INTEGER NOT NULL,
                type TEXT NOT NULL,
                role TEXT NOT NULL,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                file_path TEXT NOT NULL,
                size_bytes INTEGER NOT NULL,
                state TEXT NOT NULL DEFAULT 'pending',
                attempts INTEGER NOT NULL DEFAULT 0,
                sha256 TEXT,
                last_attempt_at TEXT,
                last_error TEXT,
                duration_s INTEGER,
                capture_end_at TEXT,
                acked_at TEXT,

                FOREIGN KEY (capture_event_id)
                    REFERENCES capture_event (id)
                    ON DELETE CASCADE
            )
            """
        )

        connection.commit()

def insert_capture_event(started_at: str, ended_at: str, motion_state: str) -> None:
    """
    Add a new CaptureEvent to the database.

    Args:
        started_at (str): Timestamp when the capture event started.
        ended_at (str): Timestamp when the capture event ended.
        motion_state (str): Motion detection state during the capture event.
    """
    with get_connection() as connection:
        cursor = connection.cursor()

        cursor.execute(
            """
            INSERT INTO capture_event (id, started_at, ended_at, motion_state)
            VALUES (?, ?, ?, ?)
            """,
            (str(uuid4()), started_at, ended_at, motion_state)
        )

        connection.commit()

def update_capture_event(id: str, ended_at: str) -> bool:
    """
    Update an existing CaptureEvent in the database.

    Args:
        id (str): The ID of the capture event to update.
        ended_at (str): New timestamp when the capture event ended.

    Returns:
        bool: if the update was successful, False otherwise.
    """
    with get_connection() as connection:
        cursor = connection.cursor()

        cursor.execute(
            """
            UPDATE capture_event
            SET ended_at = ?
            WHERE id = ?
            """,
            (ended_at, id)
        )

        connection.commit()
        return cursor.rowcount > 0

def insert_footage_item(item: FootageItemInsert) -> None:
    """
    Add a new FootageItem to the upload queue.

    Args:
        item (FootageItemInsert): The footage item to add.
    """
    with get_connection() as connection:
        cursor = connection.cursor()

        cursor.execute(
            """
            INSERT INTO footage_item (
                id, capture_event_id, sequence_index, type, role, file_path,
                size_bytes, sha256, duration_s, capture_end_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                str(uuid4()),
                item.capture_event_id,
                item.sequence_index,
                item.type,
                item.role,
                str(item.file_path),
                item.size_bytes,
                item.sha256,
                item.duration_s,
                item.capture_end_at
            )
        )

        connection.commit()

def update_item_state(id: str, new_state: FootageState) -> bool:
    """
    Update the state of a FootageItem in the upload queue.

    Args:
        id (str): The ID of the footage item to update.
        new_state (FootageState): The new state to set.

    Returns:
        bool: True if the update was successful, False otherwise.
    """
    with get_connection() as connection:
        cursor = connection.cursor()

        cursor.execute(
            """
            UPDATE footage_item
            SET state = ?
            WHERE id = ?
            """,
            (new_state, id)
        )

        connection.commit()
        return cursor.rowcount > 0

def select_pending_capture_events() -> list[CaptureEvent]:
    """
    Retrieve capture events that have at least one pending footage item.
    Each capture event includes its pending footage items.
    """
    with get_connection() as connection:
        cursor = connection.cursor()

        cursor.execute(
            """
            SELECT
                capture_event.id,
                capture_event.started_at,
                capture_event.ended_at,
                capture_event.motion_state,
                json_group_array(
                    json_object(
                        'id', footage_item.id,
                        'capture_event_id', footage_item.capture_event_id,
                        'sequence_index', footage_item.sequence_index,
                        'type', footage_item.type,
                        'role', footage_item.role,
                        'created_at', footage_item.created_at,
                        'file_path', footage_item.file_path,
                        'size_bytes', footage_item.size_bytes,
                        'state', footage_item.state,
                        'attempts', footage_item.attempts,
                        'sha256', footage_item.sha256,
                        'last_attempt_at', footage_item.last_attempt_at,
                        'last_error', footage_item.last_error,
                        'duration_s', footage_item.duration_s,
                        'capture_end_at', footage_item.capture_end_at,
                        'acked_at', footage_item.acked_at
                    )
                ) AS footage_items
            FROM capture_event
            INNER JOIN footage_item
                ON footage_item.capture_event_id = capture_event.id
            WHERE footage_item.state = 'pending'
            GROUP BY
                capture_event.id,
                capture_event.started_at,
                capture_event.ended_at,
                capture_event.motion_state
            ORDER BY capture_event.started_at ASC
            """
        )

        rows = cursor.fetchall()

    return [
        CaptureEvent(
            id=row["id"],
            started_at=row["started_at"],
            ended_at=row["ended_at"],
            motion_state=row["motion_state"],
            footage_items=json.loads(row["footage_items"])
        )
        for row in rows
    ]

def select_item_by_id(id: str) -> FootageItem | None:
    """
    Retrieve one FootageItem by ID.
    """
    with get_connection() as connection:
        cursor = connection.cursor()

        cursor.execute(
            """
            SELECT * FROM footage_item
            WHERE id = ?
            """,
            (id,)
        )

        row = cursor.fetchone()

        if row is None:
            return None

        return row_to_footage_item(row)

def delete_item_by_id(id: str) -> bool:
    """
    Delete a FootageItem from the upload queue.

    Args:
        id (str): The ID of the footage item to delete.

    Returns:
        bool: True if the delete was successful, False otherwise.
    """
    with get_connection() as connection:
        cursor = connection.cursor()

        cursor.execute(
            """
            DELETE FROM footage_item
            WHERE id = ?
            """,
            (id,)
        )

        connection.commit()
        return cursor.rowcount > 0