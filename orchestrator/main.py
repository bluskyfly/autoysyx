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


@cli.command()
@click.pass_context
def resume(ctx: click.Context) -> None:
    """Alias for `run` — picks up where the last session left off."""
    ctx.invoke(run)


@cli.command()
@click.pass_context
def run(ctx: click.Context) -> None:
    """Run tasks one at a time until done, failed, or interrupted."""
    root: Path = ctx.obj["root"]
    db = _open_db(root)
    tasks = load_tasks(_default_tasks_path(root))
    nxt = pick_next_task(db, tasks)
    if nxt is None:
        click.echo("  nothing to do — all tasks done or blocked")
        return
    click.echo(f"  next task: {nxt.id} — {nxt.title}")
    # Real run loop wired in Task 11.2.


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
