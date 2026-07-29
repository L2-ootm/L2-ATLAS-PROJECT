"""Behavior tests for scripts/fresh_install_smoke.py (Phase 10.0.2 Plan 04).

Test 1: the full step sequence (db init --demo -> atlas up -> atlas doctor ->
mock-mode mission run) succeeds end-to-end against a throwaway ATLAS_HOME with
no provider credentials, and exits 0.

Test 2: a simulated `atlas up` failure (gateway/cockpit health check forced
false) causes the smoke to exit non-zero and report which step failed.
"""
from __future__ import annotations

import pathlib
import subprocess
import sys

REPO_ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "scripts"))

import fresh_install_smoke  # noqa: E402


def test_fresh_install_smoke_passes_end_to_end(capsys):
    exit_code = fresh_install_smoke.main(
        gateway_health_ok=lambda: True,
        cockpit_health_ok=lambda: True,
    )
    out = capsys.readouterr().out
    assert exit_code == 0
    assert "SMOKE PASSED" in out
    assert "[1]" in out
    assert "[2]" in out
    assert "[3]" in out
    assert "[4]" in out
    assert "mock-mode mission run: status=succeeded" in out


def test_fresh_install_smoke_fails_when_atlas_up_fails(capsys):
    exit_code = fresh_install_smoke.main(
        gateway_health_ok=lambda: False,
        cockpit_health_ok=lambda: True,
    )
    captured = capsys.readouterr()
    assert exit_code == 1
    assert "FAIL: step 2 (atlas up)" in captured.err
    assert "SMOKE PASSED" not in captured.out


def test_installed_verifier_fails_closed_without_local_index(tmp_path):
    missing = tmp_path / "missing-release-index.json"
    result = subprocess.run(
        [
            "node",
            str(REPO_ROOT / "scripts" / "ci" / "verify-clean-install.js"),
            "--local-index",
            str(missing),
            "--home",
            str(tmp_path / "install"),
            "--version",
            "0.1.5",
            "--probe-version",
            "--probe-freellmapi-redaction",
        ],
        cwd=tmp_path,
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode != 0
    assert "local release index does not exist" in (result.stdout + result.stderr)
