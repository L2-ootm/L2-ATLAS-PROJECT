"""Tests for the Discord sidecar lifecycle primitive (discord_control).

No real process is spawned and no HTTP is made: subprocess.Popen, the platform
kill path, and the /health probe are monkeypatched, and the state file is
redirected to tmp. Mirrors test_messaging_gateway_control.py.
"""
from __future__ import annotations

import pytest

from atlas_runtime import discord_control as dc


@pytest.fixture(autouse=True)
def _tmp_state(tmp_path, monkeypatch):
    monkeypatch.setattr(dc, "STATE_FILE", tmp_path / "discord-bot.json")


class _FakeProc:
    def __init__(self, pid: int = 5151) -> None:
        self.pid = pid


def test_status_stopped_when_unreachable(monkeypatch) -> None:
    monkeypatch.setattr(dc, "_health_payload", lambda timeout=1.0: None)
    assert dc.status() == {"running": False, "pid": None, "ready": False, "guild_count": 0}


def test_coexistence_warning_on_shared_token(monkeypatch) -> None:
    monkeypatch.setattr(dc, "_bot_token", lambda: "same-token")
    monkeypatch.setattr(dc, "_foundation_discord_token", lambda: "same-token")
    warning = dc.coexistence_warning()
    assert warning is not None and "share a bot token" in warning


def test_coexistence_silent_on_distinct_or_missing(monkeypatch) -> None:
    monkeypatch.setattr(dc, "_bot_token", lambda: "bot-token")
    monkeypatch.setattr(dc, "_foundation_discord_token", lambda: "other-token")
    assert dc.coexistence_warning() is None
    # Missing foundation token -> no warning (can't tell).
    monkeypatch.setattr(dc, "_foundation_discord_token", lambda: None)
    assert dc.coexistence_warning() is None


def test_token_fingerprint_never_returns_raw_token() -> None:
    fp = dc._token_fingerprint("super-secret-token")
    assert fp is not None and "secret" not in fp and len(fp) == 12
    assert dc._token_fingerprint(None) is None


def test_status_running_from_health(monkeypatch) -> None:
    dc._write_state({"pid": 4242})
    monkeypatch.setattr(dc, "_health_payload", lambda timeout=1.0: {"ready": True, "guild_count": 3})
    assert dc.status() == {"running": True, "pid": 4242, "ready": True, "guild_count": 3}


def test_start_spawns_detached_and_records_pid(monkeypatch, tmp_path) -> None:
    bot_dir = tmp_path / "discord-bot"
    (bot_dir / "bot").mkdir(parents=True)
    (bot_dir / "bot" / "main.py").write_text("", encoding="utf-8")
    monkeypatch.setattr(dc, "DISCORD_DIR", bot_dir)
    monkeypatch.setattr(dc, "bot_python", lambda: "python")
    monkeypatch.setattr(dc, "health_ok", lambda timeout=1.0: False)
    captured: dict = {}

    def _fake_popen(args, **kwargs):
        captured["args"] = args
        return _FakeProc(pid=9300)

    monkeypatch.setattr(dc.subprocess, "Popen", _fake_popen)

    ok, msg = dc.start()
    assert ok is True
    assert "9300" in msg
    assert captured["args"][1:] == ["-m", "bot.main"]
    assert dc._read_state()["pid"] == 9300


def test_start_is_idempotent_when_running(monkeypatch) -> None:
    monkeypatch.setattr(dc, "health_ok", lambda timeout=1.0: True)

    def _boom(*_a, **_k):
        raise AssertionError("Popen must not run when already healthy")

    monkeypatch.setattr(dc.subprocess, "Popen", _boom)
    ok, msg = dc.start()
    assert ok is True
    assert "already running" in msg


def test_start_fails_when_dir_missing(monkeypatch, tmp_path) -> None:
    monkeypatch.setattr(dc, "DISCORD_DIR", tmp_path / "nope")
    monkeypatch.setattr(dc, "health_ok", lambda timeout=1.0: False)
    ok, msg = dc.start()
    assert ok is False
    assert "not found" in msg


def test_stop_kills_recorded_pid_and_clears_state(monkeypatch) -> None:
    dc._write_state({"pid": 7777})
    killed: dict = {}
    if dc.os.name == "nt":
        monkeypatch.setattr(dc.subprocess, "run", lambda cmd, **k: killed.update(cmd=cmd))
    else:
        monkeypatch.setattr(dc.os, "kill", lambda pid, sig: killed.update(pid=pid))
    ok, msg = dc.stop()
    assert ok is True
    assert "7777" in msg
    assert killed
    assert dc._read_state().get("pid") is None


def test_stop_without_pid_is_idempotent_success() -> None:
    ok, msg = dc.stop()
    assert ok is True
    assert "not running" in msg
