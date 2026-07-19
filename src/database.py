import sqlite3

from src.configs.config import DATA_DIR, DATABASE_PATH
from src.mappers.footage_item_mapper import row_to_footage_item
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
                capture_event_id, sequence_index, type, role, file_path,
                size_bytes, sha256, duration_s, capture_end_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
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

def select_pending_items() -> list[FootageItem]:
    """
    Retrieve all FootageItems in the upload queue that are in the 'pending' state.

    Returns:
        list[FootageItem]: A list of pending footage items.
    """
    with get_connection() as connection:
        cursor = connection.cursor()

        cursor.execute(
            """
            SELECT * FROM footage_item
            WHERE state = 'pending'
            ORDER BY created_at ASC
            """
        )

        rows = cursor.fetchall()
        return [row_to_footage_item(row) for row in rows]

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