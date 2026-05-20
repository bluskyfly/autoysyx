"""Tests for orchestrator.bootstrap."""
from pathlib import Path
from unittest.mock import patch

from orchestrator.bootstrap import capture_tool_versions, write_env_lock


def test_capture_tool_versions_returns_known_tools():
    """Should call --version on each tool and capture the leading line."""
    fake = {
        "gcc": (0, "gcc (Ubuntu 13.3.0) 13.3.0\n", ""),
        "missing-tool": (127, "", "command not found"),
    }
    with patch("orchestrator.bootstrap._run_version") as r:
        r.side_effect = lambda t: fake[t]
        result = capture_tool_versions(["gcc", "missing-tool"])
    assert result["gcc"]["available"] is True
    assert "13.3.0" in result["gcc"]["version"]
    assert result["missing-tool"]["available"] is False


def test_write_env_lock_creates_valid_yaml(tmp_path: Path):
    versions = {
        "verilator": {"available": True, "version": "5.042", "path": "/usr/bin/verilator"},
        "yosys": {"available": True, "version": "0.60+39", "path": "/usr/local/bin/yosys"},
    }
    lock_path = tmp_path / "env-lock.yaml"
    write_env_lock(lock_path, versions)
    assert lock_path.exists()

    import yaml
    parsed = yaml.safe_load(lock_path.read_text())
    assert parsed["tools"][0]["name"] in {"verilator", "yosys"}
    assert "locked_at" in parsed
