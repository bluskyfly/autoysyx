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


def test_task_status_pending_when_no_events(tmp_db_path: Path):
    db = Database(tmp_db_path)
    db.init_schema()
    assert db.task_status("F1") == "pending"


def test_task_status_running_after_task_started(tmp_db_path: Path):
    db = Database(tmp_db_path)
    db.init_schema()
    db.append_event(type="task_started", task_id="F1")
    assert db.task_status("F1") == "running"


def test_task_status_completed_after_task_done(tmp_db_path: Path):
    db = Database(tmp_db_path)
    db.init_schema()
    db.append_event(type="task_started", task_id="F1")
    db.append_event(type="task_done", task_id="F1")
    assert db.task_status("F1") == "completed"


def test_task_status_failed_after_task_failed(tmp_db_path: Path):
    db = Database(tmp_db_path)
    db.init_schema()
    db.append_event(type="task_started", task_id="F1")
    db.append_event(type="task_failed", task_id="F1")
    assert db.task_status("F1") == "failed"


def test_task_status_skipped_after_skip_event(tmp_db_path: Path):
    db = Database(tmp_db_path)
    db.init_schema()
    db.append_event(type="task_skipped", task_id="F1")
    assert db.task_status("F1") == "skipped"


def test_task_status_reset_after_user_retry(tmp_db_path: Path):
    """User can reset a failed task back to pending via 'task_reset' event."""
    db = Database(tmp_db_path)
    db.init_schema()
    db.append_event(type="task_started", task_id="F1")
    db.append_event(type="task_failed", task_id="F1")
    db.append_event(type="task_reset", task_id="F1")
    assert db.task_status("F1") == "pending"
