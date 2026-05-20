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


def test_review_diff_treats_diff_empty_complaint_as_skipped(tmp_path: Path):
    """Bug E fix: codex saying '必须修复: diff 为空, 无法 review' is INCONCLUSIVE.

    Worker-side tasks whose artifacts land under .gitignore'd ysyx-workbench/
    produce an empty staged diff. Codex receives that empty diff, says it can't
    form a judgment, and sometimes prefixes the answer with `必须修复:` —
    which the naive reject-pattern matcher (containing `必须修复`) flips to a
    rejection. That's wrong: codex didn't actually find a bug, it lacked input.

    These cases must be treated like a `skipped` review (not rejection), so the
    orchestrator doesn't kill an otherwise-passing task because of empty diffs.
    """
    inconclusive_msgs = [
        "必须修复: 当前 diff 为空，只有 `(no diff yet)`，无法对实际改动做有效 review。请提供实际 diff 后再审。",
        "必须修复: 这次 diff 不能证明 X 实现正确。当前 diff 为空。",
        "no diff yet, cannot review — please provide actual changes",
        "must fix: diff is empty, give me real changes first",
    ]
    for msg in inconclusive_msgs:
        with patch("orchestrator.reviewer._run_codex") as r:
            r.return_value = (0, msg, "")
            result = review_diff(diff_text="(no diff yet)", task_id="X",
                                 project_root=tmp_path)
        assert result.skipped, (
            f"inconclusive codex output must be skipped, not rejected. Got "
            f"approved={result.approved} skipped={result.skipped} for: {msg[:80]}"
        )
        assert not result.approved


def test_review_diff_still_rejects_real_codex_complaint(tmp_path: Path):
    """Bug E fix must not swallow real `必须修复` complaints about actual code.

    If codex says `必须修复: ALU.scala:42 carry-out logic wrong` (no mention
    of `diff 为空` / `no diff`), that IS a rejection.
    """
    real_complaints = [
        "必须修复: ALU.scala:42 的进位逻辑反了，应该是 b ^ cin 不是 b & cin",
        "FATAL: csr_mret 在 mstatus.MIE 还没恢复时就跳了",
        "must fix: the load instruction reads memory before resolving the address",
    ]
    for msg in real_complaints:
        with patch("orchestrator.reviewer._run_codex") as r:
            r.return_value = (0, msg, "")
            result = review_diff(diff_text="some real diff", task_id="X",
                                 project_root=tmp_path)
        assert not result.approved, f"real complaint must reject: {msg[:80]}"
        assert not result.skipped


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
