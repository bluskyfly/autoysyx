"""Tests for orchestrator.tasks."""
from pathlib import Path

import pytest

from orchestrator.tasks import (
    Task,
    TasksFileError,
    detect_cycle,
    load_tasks,
    topological_order,
)


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


def test_load_tasks_null_tasks_key_raises(tmp_path: Path):
    """`tasks:` with no value should raise TasksFileError, not TypeError."""
    bad = tmp_path / "null.yaml"
    bad.write_text("tasks:\n")
    with pytest.raises(TasksFileError, match="tasks"):
        load_tasks(bad)


def test_load_tasks_scalar_tasks_key_raises(tmp_path: Path):
    """`tasks: "hello"` should raise TasksFileError clearly."""
    bad = tmp_path / "scalar.yaml"
    bad.write_text("tasks: hello\n")
    with pytest.raises(TasksFileError, match="tasks"):
        load_tasks(bad)


def test_load_tasks_non_mapping_entry_raises(tmp_path: Path):
    """List of non-dict entries should raise TasksFileError."""
    bad = tmp_path / "scalars.yaml"
    bad.write_text("tasks:\n  - 42\n  - hello\n")
    with pytest.raises(TasksFileError, match="mapping"):
        load_tasks(bad)


def test_load_tasks_string_deps_raises(tmp_path: Path):
    """`deps: PHASE0` (string instead of list) must NOT be split into chars."""
    bad = tmp_path / "bad_deps.yaml"
    bad.write_text(
        "tasks:\n"
        "  - id: F1\n"
        "    title: x\n"
        "    stage: F\n"
        "    deps: PHASE0\n"  # Forgot the brackets!
    )
    with pytest.raises(TasksFileError, match="deps"):
        load_tasks(bad)


def test_topological_order_respects_deps():
    tasks = load_tasks(FIXTURE_DIR / "minimal_tasks.yaml")
    order = topological_order(tasks)
    ids = [t.id for t in order]
    # PHASE0 must come before F1, F1 before F2
    assert ids.index("PHASE0") < ids.index("F1")
    assert ids.index("F1") < ids.index("F2")


def test_detect_cycle_returns_none_when_acyclic():
    tasks = load_tasks(FIXTURE_DIR / "minimal_tasks.yaml")
    assert detect_cycle(tasks) is None


def test_detect_cycle_finds_simple_cycle():
    a = Task(id="A", title="a", stage="X", deps=["B"])
    b = Task(id="B", title="b", stage="X", deps=["A"])
    cycle = detect_cycle([a, b])
    assert cycle is not None
    assert set(cycle) == {"A", "B"}


def test_detect_cycle_finds_self_loop():
    a = Task(id="A", title="a", stage="X", deps=["A"])
    cycle = detect_cycle([a])
    assert cycle == ["A"]


def test_topological_order_raises_on_unknown_dep():
    a = Task(id="A", title="a", stage="X", deps=["NOPE"])
    with pytest.raises(TasksFileError, match="unknown dep"):
        topological_order([a])
