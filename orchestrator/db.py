"""SQLite event store for the orchestrator."""
import sqlite3
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
