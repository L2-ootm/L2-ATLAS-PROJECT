"""TEST-04 command-line cross-surface conformance contract."""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[3]
RUNNER = REPO_ROOT / "scripts" / "conformance" / "run_cross_surface.py"


def test_cross_surface_runner_proves_every_reference_mission() -> None:
    result = subprocess.run(
        [sys.executable, str(RUNNER), "--all", "--assert-clean-gateway"],
        cwd=REPO_ROOT,
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0, result.stderr or result.stdout
    assert "plain_completion: PASS" in result.stdout
    assert "reconnect_resume: PASS" in result.stdout
    assert "gateway: clean" in result.stdout
