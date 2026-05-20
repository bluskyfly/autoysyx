"""Tests for orchestrator.tasks."""
from pathlib import Path

import pytest

from orchestrator.tasks import Task, load_tasks, TasksFileError


FIXTURE_DIR = Path(__file__).parent / "fixtures"


def test_load_tasks_returns_task_objects():
    tasks = load_tasks(FIXTURE_DIR / "minimal_tasks.yaml")
    ids = [t.id for t in tasks]
    assert ids == ["PHASE0", "F1", "F2"]


def test_task_fields_populated():
    tasks = load_tasks(FIXTURE_DIR / "minimal_tasks.yaml")
    f1 = next(t for t in tasks if t.id == "F1")
    assert f1.title == "如何科学地提问"
    assert f1.stage == "F"
    assert f1.deps == ["PHASE0"]
    assert f1.estimated_minutes == 20
    assert f1.doc_refs == ["docs-md/2407/f/1.md"]
    assert f1.verification["type"] == "doc_artifact"


def test_load_tasks_missing_file_raises(tmp_path: Path):
    with pytest.raises(TasksFileError):
        load_tasks(tmp_path / "nope.yaml")


def test_load_tasks_invalid_yaml_raises(tmp_path: Path):
    bad = tmp_path / "bad.yaml"
    bad.write_text("tasks: [{id: X")  # malformed
    with pytest.raises(TasksFileError):
        load_tasks(bad)
