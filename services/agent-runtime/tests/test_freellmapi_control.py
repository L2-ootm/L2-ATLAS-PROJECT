"""Tests for freellmapi_control — the external-sidecar process primitive.

Only the deterministic pieces (no real node process is started, no network).
"""
from __future__ import annotations

import pathlib

from typer.testing import CliRunner

from atlas_runtime import freellmapi_control as fc
from atlas_runtime.cli.main import app

runner = CliRunner()


def _offline(monkeypatch) -> None:
    monkeypatch.setattr(fc, "health_ok", lambda timeout=1.0: False)


def test_status_shape(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(fc, "STATE_FILE", tmp_path / "freellmapi.json")
    _offline(monkeypatch)
    st = fc.status()
    assert set(st) == {"running", "base_url", "dir", "installed", "remediation"}
    assert st["running"] is False
    assert st["base_url"].startswith("http")


def test_start_without_checkout_gives_remediation(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(fc, "STATE_FILE", tmp_path / "freellmapi.json")
    monkeypatch.setattr(fc, "resolve_dir", lambda: None)
    _offline(monkeypatch)
    ok, msg = fc.start()
    assert ok is False
    assert "ATLAS_FREELLMAPI_DIR" in msg
    assert "git clone" in msg


def test_start_without_build_gives_remediation(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(fc, "STATE_FILE", tmp_path / "freellmapi.json")
    monkeypatch.setattr(fc, "resolve_dir", lambda: tmp_path)
    _offline(monkeypatch)
    ok, msg = fc.start()
    assert ok is False
    assert "npm run build" in msg


def test_env_dir_wins(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("ATLAS_FREELLMAPI_DIR", str(tmp_path))
    assert fc.resolve_dir() == pathlib.Path(tmp_path)


def test_env_dir_missing_yields_none(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("ATLAS_FREELLMAPI_DIR", str(tmp_path / "nope"))
    assert fc.resolve_dir() is None


def test_stop_without_pid_fails_cleanly(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(fc, "STATE_FILE", tmp_path / "freellmapi.json")
    ok, msg = fc.stop()
    assert ok is False
    assert "no pid" in msg


def test_cli_status_json(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(fc, "STATE_FILE", tmp_path / "freellmapi.json")
    _offline(monkeypatch)
    result = runner.invoke(app, ["freellmapi", "status", "--json"])
    assert result.exit_code == 0
    assert '"running": false' in result.output


def test_cli_start_not_installed_exits_nonzero(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(fc, "STATE_FILE", tmp_path / "freellmapi.json")
    monkeypatch.setattr(fc, "resolve_dir", lambda: None)
    _offline(monkeypatch)
    result = runner.invoke(app, ["freellmapi", "start"])
    assert result.exit_code == 1
    assert "ATLAS_FREELLMAPI_DIR" in result.output
