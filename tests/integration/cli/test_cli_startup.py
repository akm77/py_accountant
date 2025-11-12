from __future__ import annotations

import subprocess
import sys
from pathlib import Path

PACKAGE_ROOT = Path(__file__).resolve().parents[3]


def run_cli(args: list[str]) -> subprocess.CompletedProcess[str]:
    cmd = [sys.executable, "-m", "presentation.cli.main"] + args
    return subprocess.run(cmd, capture_output=True, text=True, cwd=str(PACKAGE_ROOT))


def test_cli_starts_help():
    proc = run_cli(["--help"])
    assert proc.returncode == 0, proc.stderr
    assert "Async CLI foundation" in proc.stdout
    assert "version" in proc.stdout
    assert "diagnostics" in proc.stdout


def test_cli_version_outputs_version():
    proc = run_cli(["version"])
    assert proc.returncode == 0, proc.stderr
    assert proc.stdout.strip(), "Version output should not be empty"


def test_cli_ping():
    proc = run_cli(["diagnostics", "ping"])
    assert proc.returncode == 0, proc.stderr
    assert proc.stdout.strip() == "pong"
