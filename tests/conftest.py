"""Shared pytest fixtures for orchestrator tests."""
from pathlib import Path
import pytest


@pytest.fixture
def tmp_db_path(tmp_path: Path) -> Path:
    """Temporary SQLite DB path for isolated tests."""
    return tmp_path / "state.db"
