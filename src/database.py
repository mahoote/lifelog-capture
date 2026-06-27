import sqlite3

from src.config import DATA_DIR, DATABASE_PATH


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
            CREATE TABLE IF NOT EXISTS upload_queue (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                type TEXT NOT NULL,
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
                acked_at TEXT
            )
            """
        )

        connection.commit()