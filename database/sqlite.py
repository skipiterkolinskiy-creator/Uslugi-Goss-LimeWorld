import sqlite3

from config import settings


async def init_database() -> None:
    settings.database_path.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(settings.database_path) as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS license_tests (
                user_id INTEGER NOT NULL,
                license_code TEXT NOT NULL,
                current_index INTEGER NOT NULL,
                score INTEGER NOT NULL,
                used_questions TEXT NOT NULL,
                answered_callbacks TEXT NOT NULL DEFAULT '',
                PRIMARY KEY (user_id, license_code)
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS pending_requests (
                request_id INTEGER PRIMARY KEY AUTOINCREMENT,
                request_type TEXT NOT NULL,
                user_id INTEGER NOT NULL,
                payload_json TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'pending',
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            )
            """
        )
        conn.commit()
