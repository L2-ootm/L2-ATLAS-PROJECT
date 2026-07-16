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
    assert set(st) == {"running", "base_url", "dir", "installed", "api_key", "remediation"}
    assert st["running"] is False
    assert st["base_url"].startswith("http")


def test_get_api_key_absent_checkout(monkeypatch) -> None:
    monkeypatch.setattr(fc, "resolve_dir", lambda: None)
    assert fc.get_api_key() is None


def test_get_api_key_reads_sidecar_db(tmp_path, monkeypatch) -> None:
    import sqlite3

    db_dir = tmp_path / "server" / "data"
    db_dir.mkdir(parents=True)
    with sqlite3.connect(db_dir / "freeapi.db") as conn:
        conn.execute("CREATE TABLE settings (key TEXT PRIMARY KEY, value TEXT)")
        conn.execute("INSERT INTO settings VALUES ('unified_api_key', 'fk-local-123')")
    monkeypatch.setattr(fc, "resolve_dir", lambda: tmp_path)
    assert fc.get_api_key() == "fk-local-123"


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


def test_sidecar_home_follows_atlas_home_env(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("ATLAS_HOME", str(tmp_path))
    monkeypatch.delenv("ATLAS_DB", raising=False)
    assert fc.sidecar_home() == tmp_path / "sidecars" / "freellmapi"


def test_resolve_dir_falls_back_to_sidecar_home(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(fc, "STATE_FILE", tmp_path / "state" / "freellmapi.json")
    home = tmp_path / "home"
    home.mkdir()
    monkeypatch.setattr(fc, "sidecar_home", lambda: home)
    assert fc.resolve_dir() == home


def test_install_requires_git(monkeypatch) -> None:
    monkeypatch.setattr(fc.shutil, "which", lambda name: None)
    ok, msg = fc.install(pathlib.Path("/tmp/wherever"))
    assert ok is False
    assert "git" in msg


def test_install_requires_npm(monkeypatch) -> None:
    monkeypatch.setattr(fc.shutil, "which", lambda name: "git" if "git" in name else None)
    ok, msg = fc.install(pathlib.Path("/tmp/wherever"))
    assert ok is False
    assert "npm" in msg


def test_install_rejects_existing_non_checkout_without_force(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(fc.shutil, "which", lambda name: name)
    dest = tmp_path / "existing"
    dest.mkdir()
    (dest / "some_file.txt").write_text("not a checkout", encoding="utf-8")
    ok, msg = fc.install(dest)
    assert ok is False
    assert "force=True" in msg


def test_install_clones_and_builds(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(fc, "STATE_FILE", tmp_path / "state" / "freellmapi.json")
    monkeypatch.setattr(fc.shutil, "which", lambda name: name)

    calls = []

    class _FakeResult:
        returncode = 0
        stderr = ""

    def _fake_run(*args, **kwargs):
        calls.append((args, kwargs))
        # Simulate `git clone` creating the destination checkout.
        if args and args[0] and args[0][0] == "git":
            dest = pathlib.Path(args[0][-1])
            (dest / ".git").mkdir(parents=True, exist_ok=True)
        return _FakeResult()

    monkeypatch.setattr(fc.subprocess, "run", _fake_run)
    dest = tmp_path / "install-target"
    ok, msg = fc.install(dest)
    assert ok is True
    assert str(dest) in msg
    assert fc._read_state()["dir"] == str(dest)
    assert len(calls) == 3  # clone, npm install, npm run build


def test_cli_freellmapi_install(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(fc, "install", lambda target=None, force=False: (True, "freellmapi installed"))
    result = runner.invoke(app, ["freellmapi", "install", "--json"])
    assert result.exit_code == 0
    assert '"ok": true' in result.output
