"""Tests for orchestrator.reviewer."""
from pathlib import Path
from unittest.mock import patch

from orchestrator.reviewer import ReviewResult, review_diff, _DIFF_FILE_RELPATH


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


def test_review_diff_writes_large_diff_to_file_not_argv(tmp_path: Path):
    """Bug C fix: a 5 MB diff must not be embedded in the question argv.

    ask-codex.sh receives the question as a positional argument and joins it
    into a single string. Passing a large diff inline blows up execve() with
    `OSError: [Errno 7] Argument list too long`. The fix is to spill the diff
    to a file inside `project_root` and only pass a short question that points
    codex at that file.
    """
    huge_diff = "diff --git a/x b/x\n+" + ("A" * 5_000_000) + "\n"
    captured_questions: list[str] = []

    def capture(question: str, *_a, **_kw):
        captured_questions.append(question)
        return (0, "Looks good. No issues.", "")

    with patch("orchestrator.reviewer._run_codex", side_effect=capture):
        result = review_diff(
            diff_text=huge_diff, task_id="T", project_root=tmp_path
        )

    assert result.approved
    assert len(captured_questions) == 1
    q = captured_questions[0]
    assert len(q.encode()) < 8192, (
        f"question must stay small ({len(q.encode())} bytes) — large diff "
        "must be spilled to a file, not embedded inline"
    )
    diff_path = tmp_path / _DIFF_FILE_RELPATH.format(task_id="T")
    assert diff_path.exists()
    # The spilled patch is truncated (codex can't usefully read 5MB of HTML).
    spilled = diff_path.read_text()
    assert "diff truncated" in spilled
    # Both ends of the original diff should still be visible.
    assert spilled.startswith("[diff truncated")
    assert str(_DIFF_FILE_RELPATH.format(task_id="T")) in q


def test_review_diff_preserves_small_diff_verbatim(tmp_path: Path):
    """Diffs below the truncation threshold are written through unchanged."""
    small_diff = "diff --git a/x b/x\n+hello\n"
    with patch("orchestrator.reviewer._run_codex") as r:
        r.return_value = (0, "Looks good. No issues.", "")
        review_diff(diff_text=small_diff, task_id="S", project_root=tmp_path)
    spilled = (tmp_path / _DIFF_FILE_RELPATH.format(task_id="S")).read_text()
    assert spilled == small_diff
    assert "diff truncated" not in spilled
