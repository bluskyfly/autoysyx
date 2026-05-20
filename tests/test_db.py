"""Tests for orchestrator.db."""
import sqlite3
from pathlib import Path

from orchestrator.db import Database


def test_init_creates_required_tables(tmp_db_path: Path):
    db = Database(tmp_db_path)
    db.init_schema()

    conn = sqlite3.connect(str(tmp_db_path))
    tables = {row[0] for row in conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table'"
    )}
    conn.close()

    assert tables >= {"events", "attempts", "env_lock"}


def test_append_event_records_payload(tmp_db_path: Path):
    db = Database(tmp_db_path)
    db.init_schema()

    eid = db.append_event(
        type="task_started",
        task_id="D1a",
        payload={"reason": "deps met"},
    )
    assert eid > 0

    events = db.list_events(task_id="D1a")
    assert len(events) == 1
    assert events[0]["type"] == "task_started"
    assert events[0]["payload"] == {"reason": "deps met"}


def test_events_returned_in_chronological_order(tmp_db_path: Path):
    db = Database(tmp_db_path)
    db.init_schema()

    db.append_event(type="task_started", task_id="X")
    db.append_event(type="attempt_started", task_id="X")
    db.append_event(type="task_done", task_id="X")

    events = db.list_events(task_id="X")
    types = [e["type"] for e in events]
    assert types == ["task_started", "attempt_started", "task_done"]
