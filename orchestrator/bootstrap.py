"""Phase-0 bootstrap: install tools + capture versions + lock."""
from __future__ import annotations

import shutil
import subprocess
from datetime import datetime, timezone
from pathlib import Path

import yaml

REQUIRED_TOOLS = [
    "gcc", "g++", "make", "cmake", "git", "python3",
    "verilator", "yosys",
    "riscv32-unknown-elf-gcc",
    "riscv64-linux-gnu-gcc",
    "qemu-system-riscv64",
    "mill",
    "java",
]


def _run_version(tool: str) -> tuple[int, str, str]:
    if shutil.which(tool) is None:
        return (127, "", f"{tool}: not in PATH")
    try:
        proc = subprocess.run(
            [tool, "--version"],
            capture_output=True,
            text=True,
            timeout=10,
            check=False,
        )
        return proc.returncode, proc.stdout, proc.stderr
    except subprocess.TimeoutExpired:
        return (124, "", f"{tool}: --version timed out")


def capture_tool_versions(tools: list[str] | None = None) -> dict[str, dict]:
    tools = tools or REQUIRED_TOOLS
    result: dict[str, dict] = {}
    for t in tools:
        rc, stdout, stderr = _run_version(t)
        path = shutil.which(t) or ""
        if rc == 0 and stdout.strip():
            ver_line = stdout.splitlines()[0].strip()
            result[t] = {"available": True, "version": ver_line, "path": path}
        else:
            result[t] = {"available": False, "version": "", "path": path}
    return result


def write_env_lock(lock_path: Path, versions: dict[str, dict]) -> None:
    payload = {
        "locked_at": datetime.now(timezone.utc).isoformat(),
        "tools": [
            {"name": name, **info}
            for name, info in sorted(versions.items())
        ],
    }
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    lock_path.write_text(yaml.safe_dump(payload, sort_keys=False), encoding="utf-8")


def run_bootstrap_sh(script_path: Path) -> int:
    """Invoke tools/bootstrap.sh, streaming output to terminal. Returns exit code."""
    proc = subprocess.run(
        ["bash", str(script_path)],
        cwd=str(script_path.parent.parent),
        check=False,
    )
    return proc.returncode


def check_env_drift(lock_path: Path) -> list[str]:
    """Return list of tool names whose current version diverged from lock."""
    if not lock_path.exists():
        return ["<no env-lock.yaml>"]
    parsed = yaml.safe_load(lock_path.read_text())
    drift: list[str] = []
    for entry in parsed.get("tools", []):
        if not entry.get("available"):
            continue
        name = entry["name"]
        locked = entry.get("version", "")
        rc, stdout, _ = _run_version(name)
        current = stdout.splitlines()[0].strip() if stdout else ""
        if rc != 0 or current != locked:
            drift.append(name)
    return drift
