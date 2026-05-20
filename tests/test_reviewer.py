"""Tests for orchestrator.reviewer."""
from pathlib import Path
from unittest.mock import patch

from orchestrator.reviewer import ReviewResult, review_diff


def test_review_diff_passes_when_codex_approves(tmp_path: Path):
    with patch("orchestrator.reviewer._run_codex") as r:
        r.return_value = (0, "Looks good. No issues.", "")
        result = review_diff(diff_text="...", task_id="F1", project_root=tmp_path)
    assert result.approved
    assert result.summary == "Looks good. No issues."


def test_review_diff_rejects_when_codex_finds_issues(tmp_path: Path):
    with patch("orchestrator.reviewer._run_codex") as r:
        r.return_value = (0, "FATAL: this code is broken because X\n", "")
        result = review_diff(diff_text="...", task_id="F1", project_root=tmp_path)
    assert not result.approved
    assert "FATAL" in result.summary


def test_review_diff_treats_codex_failure_as_skipped(tmp_path: Path):
    """If codex CLI itself fails, treat as 'review skipped' not blocking."""
    with patch("orchestrator.reviewer._run_codex") as r:
        r.return_value = (1, "", "codex: command not found")
        result = review_diff(diff_text="...", task_id="F1", project_root=tmp_path)
    assert result.skipped
    assert "codex: command not found" in result.summary
