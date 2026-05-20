"""autoysyx CLI entry point."""
from __future__ import annotations

import sys
from pathlib import Path

import click

from .db import Database
from .tasks import load_tasks, pick_next_task


def _default_root() -> Path:
    return Path.cwd()


def _default_db_path(root: Path) -> Path:
    return root / "orchestrator" / "state.db"


def _default_tasks_path(root: Path) -> Path:
    return root / "tasks.yaml"


def _open_db(root: Path) -> Database:
    db_path = _default_db_path(root)
    db_path.parent.mkdir(parents=True, exist_ok=True)
    db = Database(db_path)
    db.init_schema()
    return db


@click.group()
@click.option("--root", type=click.Path(file_okay=False, path_type=Path),
              default=None, help="autoysyx project root (defaults to CWD)")
@click.pass_context
def cli(ctx: click.Context, root: Path | None) -> None:
    """autoysyx — autonomous YSYX completion orchestrator."""
    ctx.ensure_object(dict)
    ctx.obj["root"] = root or _default_root()


@cli.command()
@click.pass_context
def status(ctx: click.Context) -> None:
    """Print the status of every task."""
    root: Path = ctx.obj["root"]
    db = _open_db(root)
    tasks = load_tasks(_default_tasks_path(root))
    for t in tasks:
        s = db.task_status(t.id)
        click.echo(f"  {t.id:8s}  {s:10s}  {t.title}")


@cli.command()
@click.argument("task_id")
@click.pass_context
def skip(ctx: click.Context, task_id: str) -> None:
    """Mark a task as skipped (its dependents will run as if it succeeded)."""
    root: Path = ctx.obj["root"]
    db = _open_db(root)
    db.append_event(type="task_skipped", task_id=task_id,
                    payload={"reason": "user-requested skip"})
    click.echo(f"  skipped: {task_id}")


@cli.command()
@click.argument("task_id")
@click.pass_context
def retry(ctx: click.Context, task_id: str) -> None:
    """Reset a failed task back to pending so it will be picked up again."""
    root: Path = ctx.obj["root"]
    db = _open_db(root)
    db.append_event(type="task_reset", task_id=task_id,
                    payload={"reason": "user-requested retry"})
    click.echo(f"  reset to pending: {task_id}")


@cli.command("inject-hint")
@click.argument("task_id")
@click.argument("hint_file", type=click.Path(exists=True, dir_okay=False, path_type=Path))
@click.pass_context
def inject_hint(ctx: click.Context, task_id: str, hint_file: Path) -> None:
    """Drop a debug hint for TASK_ID and reset it for another attempt.

    The hint is copied to prompts/_hints/<task_id>.md; the next assemble_prompt
    call inlines it into the worker prompt. Use this after a task lands in the
    'needs_debug' state, once you've analyzed the escalation bundle with codex.
    """
    root: Path = ctx.obj["root"]
    db = _open_db(root)
    hints_dir = root / "prompts" / "_hints"
    hints_dir.mkdir(parents=True, exist_ok=True)
    target = hints_dir / f"{task_id}.md"
    target.write_text(hint_file.read_text(encoding="utf-8"), encoding="utf-8")
    db.append_event(type="task_reset", task_id=task_id,
                    payload={"reason": "hint injected", "hint_path": str(target)})
    click.echo(f"  hint copied to {target.relative_to(root)}; {task_id} reset to pending")


@cli.command()
@click.pass_context
def resume(ctx: click.Context) -> None:
    """Alias for `run` — picks up where the last session left off."""
    ctx.invoke(run)


@cli.command()
@click.option("--max-tasks", type=int, default=0,
              help="Limit to N tasks then stop (0 = unlimited).")
@click.pass_context
def run(ctx: click.Context, max_tasks: int) -> None:
    """Run tasks one at a time until done, failed, or interrupted."""
    from .worker import run_worker, assemble_prompt
    from .verifier import verify_task, snapshot_immutable_files
    from .reviewer import review_diff
    from .reporter import generate_task_report
    import subprocess

    root: Path = ctx.obj["root"]
    db = _open_db(root)
    tasks = load_tasks(_default_tasks_path(root))
    template_path = root / "prompts" / "_template.md"
    reports_dir = root / "reports"

    done_count = 0
    while True:
        nxt = pick_next_task(db, tasks)
        if nxt is None:
            click.echo("  all done or blocked")
            return
        if max_tasks and done_count >= max_tasks:
            click.echo(f"  reached --max-tasks {max_tasks}")
            return

        click.echo(f"  ▶ {nxt.id} — {nxt.title}")
        db.append_event(type="task_started", task_id=nxt.id)
        attempt_num = 0
        prior_errors: list[str] = []

        while attempt_num < nxt.max_attempts:
            attempt_num += 1
            db.append_event(type="attempt_started", task_id=nxt.id,
                            payload={"attempt_num": attempt_num})

            prompt = assemble_prompt(template_path, nxt, root, prior_errors)
            immutable_base = snapshot_immutable_files(
                [root / f for f in nxt.immutable_files]
            )

            worker_res = run_worker(
                prompt=prompt,
                work_dir=root,
                add_dirs=[root / "docs-md", root / "ysyx-workbench"],
            )
            if worker_res.contract is None:
                prior_errors.append(
                    f"worker contract error: {worker_res.contract_error or worker_res.api_error}"
                )
                db.append_event(type="attempt_failed", task_id=nxt.id,
                                payload={"attempt_num": attempt_num,
                                         "fail_category": "contract_invalid",
                                         "log_excerpt": prior_errors[-1][:500]})
                continue

            verify_res = verify_task(nxt, cwd=root, immutable_baseline=immutable_base)
            if not verify_res.passed:
                excerpt = ""
                if verify_res.log_path:
                    excerpt = Path(verify_res.log_path).read_text()[-1000:]
                prior_errors.append(
                    f"verify failed ({verify_res.fail_category}):\n{excerpt}"
                )
                db.append_event(type="attempt_failed", task_id=nxt.id,
                                payload={"attempt_num": attempt_num,
                                         "fail_category": verify_res.fail_category,
                                         "log_excerpt": excerpt[:500]})
                continue

            # Stage all worker changes BEFORE asking codex, so codex sees the real diff.
            subprocess.run(["git", "add", "-A"], cwd=str(root), check=True)
            diff = subprocess.run(
                ["git", "diff", "--cached", "HEAD"],
                cwd=str(root), capture_output=True, text=True
            ).stdout or "(no diff yet)"
            review = review_diff(diff, nxt.id, project_root=root)
            if not review.approved and not review.skipped:
                prior_errors.append(f"codex rejected: {review.summary[:500]}")
                db.append_event(type="attempt_failed", task_id=nxt.id,
                                payload={"attempt_num": attempt_num,
                                         "fail_category": "codex_reject",
                                         "log_excerpt": review.summary[:500]})
                continue

            db.append_event(type="attempt_passed", task_id=nxt.id,
                            payload={"attempt_num": attempt_num,
                                     "duration_sec": verify_res.duration_sec})
            if not review.skipped:
                db.append_event(type="codex_passed", task_id=nxt.id,
                                payload={"summary": review.summary[:2000]})
            commit_msg = f"{nxt.id}: {nxt.title}"
            subprocess.run(
                ["git", "commit", "-m", commit_msg, "--allow-empty"],
                cwd=str(root), capture_output=True, text=True, check=True,
            )
            sha = subprocess.run(
                ["git", "rev-parse", "--short", "HEAD"],
                cwd=str(root), capture_output=True, text=True, check=True,
            ).stdout.strip()
            db.append_event(type="task_done", task_id=nxt.id,
                            payload={"commit": sha})
            generate_task_report(db, nxt, reports_dir)
            click.echo(f"  ✓ {nxt.id} done ({sha})")
            done_count += 1
            break
        else:
            # Exhausted attempts — instead of hard-failing, park in `needs_debug`
            # and write an escalation bundle so a human/AI collaborator can
            # diagnose and `inject-hint` to unblock. The task is NOT marked
            # `failed` here, so dependents stay blocked until a hint arrives.
            bundle_dir = _write_escalation_bundle(root, db, nxt, attempt_num, prior_errors)
            db.append_event(type="task_needs_debug", task_id=nxt.id,
                            payload={"attempts": attempt_num,
                                     "bundle_dir": str(bundle_dir.relative_to(root))})
            generate_task_report(db, nxt, reports_dir)
            click.echo(
                f"  ⏸ {nxt.id} NEEDS DEBUG after {attempt_num} attempts — "
                f"bundle: {bundle_dir.relative_to(root)}",
                err=True,
            )
            continue


def _write_escalation_bundle(
    root: Path,
    db,
    task,
    attempts: int,
    prior_errors: list[str],
) -> Path:
    """Dump the escalation context for `task` so a collaborator can debug.

    Captures everything a fresh reviewer needs without poking the live DB:
    the failed attempts' log excerpts, the worker's current staged diff,
    git status, and a meta.json with task config.
    """
    import json
    import subprocess
    from datetime import datetime, timezone

    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    bundle = root / "escalations" / f"{task.id}-{stamp}"
    bundle.mkdir(parents=True, exist_ok=True)

    (bundle / "attempts.log").write_text(
        "\n--- attempt boundary ---\n".join(prior_errors) or "(no prior errors recorded)",
        encoding="utf-8",
    )

    staged = subprocess.run(
        ["git", "diff", "--cached", "HEAD"],
        cwd=str(root), capture_output=True, text=True,
    ).stdout or "(no staged changes)"
    (bundle / "staged.patch").write_text(staged, encoding="utf-8")

    status = subprocess.run(
        ["git", "status", "--short"],
        cwd=str(root), capture_output=True, text=True,
    ).stdout
    (bundle / "git-status.txt").write_text(status, encoding="utf-8")

    meta = {
        "task_id": task.id,
        "title": task.title,
        "stage": task.stage,
        "deps": task.deps,
        "attempts_used": attempts,
        "max_attempts": task.max_attempts,
        "verification": task.verification,
        "doc_refs": task.doc_refs,
        "escalated_at": datetime.now(timezone.utc).isoformat(),
    }
    (bundle / "meta.json").write_text(
        json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8",
    )
    return bundle


@cli.command()
@click.pass_context
def bootstrap(ctx: click.Context) -> None:
    """Run tools/bootstrap.sh then capture env-lock.yaml."""
    from .bootstrap import (
        capture_tool_versions, run_bootstrap_sh, write_env_lock,
    )
    root: Path = ctx.obj["root"]
    script = root / "tools" / "bootstrap.sh"
    rc = run_bootstrap_sh(script)
    if rc != 0:
        click.echo(f"  bootstrap.sh exit {rc}, abort", err=True)
        sys.exit(rc)
    versions = capture_tool_versions()
    write_env_lock(root / "tools" / "env-lock.yaml", versions)
    click.echo("  bootstrap complete; env-lock.yaml written")


if __name__ == "__main__":
    cli()
