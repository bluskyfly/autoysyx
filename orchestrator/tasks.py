"""Task definitions loader and dependency graph utilities."""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml


class TasksFileError(Exception):
    """Raised when tasks.yaml is missing, malformed, or fails schema check."""


@dataclass
class Task:
    id: str
    title: str
    stage: str
    deps: list[str] = field(default_factory=list)
    estimated_minutes: int = 0
    doc_refs: list[str] = field(default_factory=list)
    immutable_files: list[str] = field(default_factory=list)
    verification: dict[str, Any] = field(default_factory=dict)
    max_attempts: int = 3


def load_tasks(path: Path) -> list[Task]:
    path = Path(path)
    if not path.exists():
        raise TasksFileError(f"tasks file not found: {path}")
    try:
        raw = yaml.safe_load(path.read_text(encoding="utf-8"))
    except yaml.YAMLError as e:
        raise TasksFileError(f"invalid YAML: {e}") from e

    if not isinstance(raw, dict) or "tasks" not in raw:
        raise TasksFileError("top-level 'tasks:' key required")

    raw_tasks = raw["tasks"]
    if not isinstance(raw_tasks, list):
        raise TasksFileError(
            f"'tasks:' must be a list, got {type(raw_tasks).__name__}"
        )

    tasks: list[Task] = []
    for entry in raw_tasks:
        if not isinstance(entry, dict):
            raise TasksFileError(
                f"task entry must be a mapping, got: {entry!r}"
            )
        if "id" not in entry or "title" not in entry:
            raise TasksFileError(f"task missing required id/title: {entry}")

        task_id = entry["id"]

        deps_raw = entry.get("deps", [])
        if not isinstance(deps_raw, list):
            raise TasksFileError(
                f"task {task_id}: 'deps' must be a list, "
                f"got {type(deps_raw).__name__}"
            )

        doc_refs_raw = entry.get("doc_refs", [])
        if not isinstance(doc_refs_raw, list):
            raise TasksFileError(
                f"task {task_id}: 'doc_refs' must be a list, "
                f"got {type(doc_refs_raw).__name__}"
            )

        immutable_files_raw = entry.get("immutable_files", [])
        if not isinstance(immutable_files_raw, list):
            raise TasksFileError(
                f"task {task_id}: 'immutable_files' must be a list, "
                f"got {type(immutable_files_raw).__name__}"
            )

        verification_raw = entry.get("verification", {})
        if not isinstance(verification_raw, dict):
            raise TasksFileError(
                f"task {task_id}: 'verification' must be a mapping, "
                f"got {type(verification_raw).__name__}"
            )

        tasks.append(
            Task(
                id=task_id,
                title=entry["title"],
                stage=entry.get("stage", ""),
                deps=list(deps_raw),
                estimated_minutes=int(entry.get("estimated_minutes", 0)),
                doc_refs=list(doc_refs_raw),
                immutable_files=list(immutable_files_raw),
                verification=dict(verification_raw),
                max_attempts=int(entry.get("max_attempts", 3)),
            )
        )
    return tasks
