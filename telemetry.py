import json
import sqlite3
from pathlib import Path
from typing import Any, Dict

from security import sanitize_metadata


class TelemetryStore:
    def __init__(self, db_path: str = "council_memory.db"):
        self.db_path = db_path
        self._init_db()

    def _init_db(self):
        Path(self.db_path).touch(exist_ok=True)
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS telemetry_events (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    event_type TEXT NOT NULL,
                    metadata_json TEXT NOT NULL,
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
                )
                """
            )

    def log_event(self, event_type: str, metadata: Dict[str, Any]):
        sanitized = sanitize_metadata(metadata)
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                """
                INSERT INTO telemetry_events (event_type, metadata_json)
                VALUES (?, ?)
                """,
                (event_type, json.dumps(sanitized)),
            )
