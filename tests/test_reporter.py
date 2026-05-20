"""Tests for orchestrator.reporter."""
from pathlib import Path

from orchestrator.db import Database
from orchestrator.reporter import generate_task_report
from orchestrator.tasks import Task


def test_generate_task_report_writes_markdown(tmp_path, tmp_db_path):
    db = Database(tmp_db_path)
    db.init_schema()
    task = Task(id="F1", title="如何科学地提问", stage="F")
    db.append_event(type="task_started", task_id="F1")
    db.append_event(type="attempt_started", task_id="F1",
                    payload={"attempt_num": 1})
    db.append_event(type="attempt_passed", task_id="F1",
                    payload={"attempt_num": 1, "duration_sec": 120})
    db.append_event(type="codex_passed", task_id="F1",
                    payload={"summary": "Looks good."})
    db.append_event(type="task_done", task_id="F1",
                    payload={"commit": "abc1234"})

    report_path = generate_task_report(db, task, reports_dir=tmp_path)
    text = report_path.read_text()
    assert "F1" in text
    assert "如何科学地提问" in text
    assert "abc1234" in text
    assert "Looks good." in text
    assert "通过" in text


def test_generate_task_report_for_failed_task(tmp_path, tmp_db_path):
    db = Database(tmp_db_path)
    db.init_schema()
    task = Task(id="D1a", title="RV32I", stage="D")
    for i in range(3):
        db.append_event(type="attempt_started", task_id="D1a",
                        payload={"attempt_num": i+1})
        db.append_event(type="attempt_failed", task_id="D1a",
                        payload={"attempt_num": i+1,
                                 "fail_category": "exit_mismatch",
                                 "log_excerpt": f"error {i+1}"})
    db.append_event(type="task_failed", task_id="D1a")

    report_path = generate_task_report(db, task, reports_dir=tmp_path)
    text = report_path.read_text()
    assert "FAILED" in text or "失败" in text
    assert "error 3" in text
    assert "attempt_num" in text or "次尝试" in text
