import sqlite3

from src.config import DATA_DIR, DATABASE_PATH
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
            CREATE TABLE IF NOT EXISTS footage_item (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                type TEXT NOT NULL,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                file_path TEXT NOT NULL,
                size_bytes INTEGER NOT NULL,
                motion_state TEXT NOT NULL,
                state TEXT NOT NULL DEFAULT 'pending',
                attempts INTEGER NOT NULL DEFAULT 0,
                sha256 TEXT,
                last_attempt_at TEXT,
                last_error TEXT,
                duration_s INTEGER,
                capture_end_at TEXT,
                acked_at TEXT
            )
            """
        )

        connection.commit()

def add_item(item: FootageItemInsert) -> None:
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
                type, file_path, size_bytes, sha256, duration_s, capture_end_at, motion_state
            ) VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                item.type,
                str(item.file_path),
                item.size_bytes,
                item.sha256,
                item.duration_s,
                item.capture_end_at,
                item.motion_state
            )
        )

        connection.commit()

def set_state(item_id: int, new_state: FootageState) -> None:
    """
    Update the state of a FootageItem in the upload queue.

    Args:
        item_id (int): The ID of the footage item to update.
        new_state (FootageState): The new state to set.
    """
    with get_connection() as connection:
        cursor = connection.cursor()

        cursor.execute(
            """
            UPDATE footage_item
            SET state = ?
            WHERE id = ?
            """,
            (new_state, item_id)
        )

        connection.commit()

def get_pending_items() -> list[FootageItem]:
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
        return [FootageItem(**row) for row in rows]