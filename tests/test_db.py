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
