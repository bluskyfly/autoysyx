"""SQLite event store for the orchestrator."""
import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS events (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    ts          TEXT NOT NULL,
    type        TEXT NOT NULL,
    task_id     TEXT,
    payload     TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_events_task ON events (task_id, ts);

CREATE TABLE IF NOT EXISTS attempts (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    task_id         TEXT NOT NULL,
    attempt_num     INTEGER NOT NULL,
    started_at      TEXT NOT NULL,
    ended_at        TEXT,
    worker_session  TEXT,
    contract_json   TEXT,
    verify_log_path TEXT,
    codex_log_path  TEXT,
    outcome         TEXT,
    fail_category   TEXT,
    cost_usd        REAL
);

CREATE TABLE IF NOT EXISTS env_lock (
    tool        TEXT PRIMARY KEY,
    version     TEXT NOT NULL,
    path        TEXT NOT NULL,
    sha256      TEXT,
    locked_at   TEXT NOT NULL
);
"""

# Terminal events take precedence over earlier ones — most recent wins.
_TERMINAL_EVENTS = {
    "task_done": "completed",
    "task_failed": "failed",
    "task_skipped": "skipped",
    "task_reset": "pending",
}


class Database:
    def __init__(self, path: Path) -> None:
        self.path = Path(path)

    def init_schema(self) -> None:
        conn = sqlite3.connect(str(self.path))
        try:
            conn.executescript(SCHEMA_SQL)
            conn.commit()
        finally:
            conn.close()

    def append_event(
        self,
        type: str,
        task_id: str | None = None,
        payload: dict | None = None,
        ts: str | None = None,
    ) -> int:
        ts = ts or datetime.now(timezone.utc).isoformat()
        payload_json = json.dumps(payload or {}, ensure_ascii=False)
        conn = sqlite3.connect(str(self.path))
        try:
            cur = conn.execute(
                "INSERT INTO events (ts, type, task_id, payload) VALUES (?, ?, ?, ?)",
                (ts, type, task_id, payload_json),
            )
            conn.commit()
            return cur.lastrowid
        finally:
            conn.close()

    def list_events(self, task_id: str | None = None) -> list[dict]:
        conn = sqlite3.connect(str(self.path))
        conn.row_factory = sqlite3.Row
        try:
            if task_id is not None:
                rows = conn.execute(
                    "SELECT * FROM events WHERE task_id = ? ORDER BY id",
                    (task_id,),
                ).fetchall()
            else:
                rows = conn.execute(
                    "SELECT * FROM events ORDER BY id"
                ).fetchall()
            return [
                {
                    "id": r["id"],
                    "ts": r["ts"],
                    "type": r["type"],
                    "task_id": r["task_id"],
                    "payload": json.loads(r["payload"]),
                }
                for r in rows
            ]
        finally:
            conn.close()

    def task_status(self, task_id: str) -> str:
        """Project current task status from its event stream.

        Status precedence: most recent terminal event wins; if only `task_started`
        seen, status is 'running'; if no events at all, status is 'pending'.
        """
        events = self.list_events(task_id=task_id)
        if not events:
            return "pending"
        # Walk newest-first to find first terminal event.
        for ev in reversed(events):
            if ev["type"] in _TERMINAL_EVENTS:
                return _TERMINAL_EVENTS[ev["type"]]
        # No terminal seen; if started, we're running.
        if any(e["type"] == "task_started" for e in events):
            return "running"
        return "pending"
