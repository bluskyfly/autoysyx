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


def test_review_diff_inlines_small_diff_into_question(tmp_path: Path):
    """A small diff goes verbatim into the codex question (stdin), not a file.

    Bug D fix: codex runs under a bwrap sandbox that can refuse disk reads.
    The reviewer must hand codex everything it needs in the prompt itself.
    """
    small_diff = "diff --git a/x b/x\n+SENTINEL_INLINE_VALUE\n"
    captured: list[str] = []

    def capture(question: str, *_a, **_kw):
        captured.append(question)
        return (0, "Looks good. No issues.", "")

    with patch("orchestrator.reviewer._run_codex", side_effect=capture):
        review_diff(diff_text=small_diff, task_id="S", project_root=tmp_path)

    assert len(captured) == 1
    q = captured[0]
    assert "SENTINEL_INLINE_VALUE" in q
    assert "diff truncated" not in q


def test_review_diff_truncates_huge_diff_but_still_inlines(tmp_path: Path):
    """A 5 MB diff must be truncated AND inlined (not spilled to a file).

    Truncating keeps us well under ARG_MAX / the codex context window. Inlining
    keeps us independent of codex sandbox file-read permission.
    """
    huge_diff = (
        "diff --git a/head b/head\n+HEAD_SENTINEL\n"
        + ("A" * 5_000_000)
        + "\n+TAIL_SENTINEL\ndiff end\n"
    )
    captured: list[str] = []

    def capture(question: str, *_a, **_kw):
        captured.append(question)
        return (0, "Looks good. No issues.", "")

    with patch("orchestrator.reviewer._run_codex", side_effect=capture):
        result = review_diff(diff_text=huge_diff, task_id="T", project_root=tmp_path)

    assert result.approved
    assert len(captured) == 1
    q = captured[0]
    # Must stay safely under ARG_MAX (~3.2 MB) and codex context budget.
    assert len(q.encode()) < 400_000, f"question too large: {len(q.encode())} bytes"
    assert "diff truncated" in q
    # Both ends of the original diff still visible in the truncated payload.
    assert "HEAD_SENTINEL" in q
    assert "TAIL_SENTINEL" in q
    # No reliance on a spilled patch file.
    assert not (tmp_path / ".autoysyx").exists()
