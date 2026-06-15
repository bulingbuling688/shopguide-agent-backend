from __future__ import annotations

import json
import sqlite3
import threading
from pathlib import Path
from typing import Any


class SQLiteConversationStore:
    def __init__(self, path: str = "shopguide.db"):
        self.path = path.replace("sqlite:///", "")
        self._locks: dict[str, threading.Lock] = {}
        self._global_lock = threading.Lock()
        self._init_db()

    def _init_db(self) -> None:
        Path(self.path).parent.mkdir(parents=True, exist_ok=True) if Path(self.path).parent != Path(".") else None
        with sqlite3.connect(self.path) as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS conversations (
                    session_id TEXT PRIMARY KEY,
                    version INTEGER NOT NULL,
                    messages TEXT NOT NULL
                )
                """
            )

    def lock_for(self, session_id: str) -> threading.Lock:
        with self._global_lock:
            if session_id not in self._locks:
                self._locks[session_id] = threading.Lock()
            return self._locks[session_id]

    def load(self, session_id: str) -> tuple[int, list[dict[str, Any]]]:
        with sqlite3.connect(self.path) as conn:
            row = conn.execute(
                "SELECT version, messages FROM conversations WHERE session_id = ?",
                (session_id,),
            ).fetchone()
        if not row:
            return 0, []
        return int(row[0]), json.loads(row[1])

    def append(self, session_id: str, role: str, content: str) -> tuple[int, list[dict[str, Any]]]:
        with self.lock_for(session_id):
            version, messages = self.load(session_id)
            messages.append({"role": role, "content": content})
            next_version = version + 1
            with sqlite3.connect(self.path) as conn:
                conn.execute(
                    """
                    INSERT INTO conversations(session_id, version, messages)
                    VALUES (?, ?, ?)
                    ON CONFLICT(session_id)
                    DO UPDATE SET version = excluded.version, messages = excluded.messages
                    """,
                    (session_id, next_version, json.dumps(messages, ensure_ascii=False)),
                )
            return next_version, messages
