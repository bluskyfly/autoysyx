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

    tasks: list[Task] = []
    for entry in raw["tasks"]:
        if "id" not in entry or "title" not in entry:
            raise TasksFileError(f"task missing required id/title: {entry}")
        tasks.append(
            Task(
                id=entry["id"],
                title=entry["title"],
                stage=entry.get("stage", ""),
                deps=list(entry.get("deps", [])),
                estimated_minutes=int(entry.get("estimated_minutes", 0)),
                doc_refs=list(entry.get("doc_refs", [])),
                immutable_files=list(entry.get("immutable_files", [])),
                verification=dict(entry.get("verification", {})),
                max_attempts=int(entry.get("max_attempts", 3)),
            )
        )
    return tasks
