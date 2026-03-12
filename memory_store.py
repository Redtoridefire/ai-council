import json
import sqlite3
from pathlib import Path
from typing import List


class CouncilMemory:
    def __init__(self, db_path: str = "council_memory.db"):
        self.db_path = db_path
        self._init_db()

    def _init_db(self):
        Path(self.db_path).touch(exist_ok=True)
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS decisions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    question TEXT NOT NULL,
                    final_decision TEXT NOT NULL,
                    aggregate_json TEXT NOT NULL,
                    responses_json TEXT NOT NULL,
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
                )
                """
            )

    def save_decision(self, question: str, final_decision: str, aggregate: dict, responses: dict):
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                """
                INSERT INTO decisions (question, final_decision, aggregate_json, responses_json)
                VALUES (?, ?, ?, ?)
                """,
                (question, final_decision, json.dumps(aggregate), json.dumps(responses)),
            )

    def get_recent(self, limit: int = 3) -> List[dict]:
        with sqlite3.connect(self.db_path) as conn:
            rows = conn.execute(
                """
                SELECT question, final_decision, aggregate_json, created_at
                FROM decisions
                ORDER BY created_at DESC
                LIMIT ?
                """,
                (limit,),
            ).fetchall()

        return [
            {
                "question": row[0],
                "final_decision": row[1],
                "aggregate": json.loads(row[2]),
                "created_at": row[3],
            }
            for row in rows
        ]

    def get_recent_for_role(self, role: str, limit: int = 2) -> List[dict]:
        """Return the most recent decisions including that role's specific response."""
        with sqlite3.connect(self.db_path) as conn:
            rows = conn.execute(
                """
                SELECT question, responses_json, aggregate_json, created_at
                FROM decisions
                ORDER BY created_at DESC
                LIMIT ?
                """,
                (limit,),
            ).fetchall()

        result = []
        for row in rows:
            responses = json.loads(row[1])
            result.append(
                {
                    "question": row[0],
                    "role_response": responses.get(role, ""),
                    "aggregate": json.loads(row[2]),
                    "created_at": row[3],
                }
            )
        return result
