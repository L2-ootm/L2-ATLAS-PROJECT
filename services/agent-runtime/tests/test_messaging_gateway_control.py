"""Tests for the messaging-gateway lifecycle primitive.

No real process is ever spawned: ``subprocess.Popen`` and the platform kill path
are monkeypatched, and the state file is redirected to a tmp path. Covers the
four real outcomes the cockpit relies on: stopped status, idempotent start,
start without a foundation CLI, and stop clearing the recorded pid.
"""
from __future__ import annotations

import pytest

from atlas_runtime import messaging_gateway_control as mgc


@pytest.fixture(autouse=True)
def _tmp_state(tmp_path, monkeypatch):
    monkeypatch.setattr(mgc, "STATE_FILE", tmp_path / "gateway-messaging.json")


class _FakeProc:
    def __init__(self, pid: int = 4321) -> None:
        self.pid = pid


def test_status_reports_stopped_when_no_pid() -> None:
    assert mgc.status() == {"running": False, "pid": None}


def test_start_spawns_detached_and_records_pid(monkeypatch) -> None:
    monkeypatch.setattr(mgc, "messaging_cli", lambda: ["atlas-agent"])
    captured: dict = {}

    def _fake_popen(args, **kwargs):
        captured["args"] = args
        return _FakeProc(pid=9100)

    monkeypatch.setattr(mgc.subprocess, "Popen", _fake_popen)

    ok, msg = mgc.start()
    assert ok is True
    assert "9100" in msg
    assert captured["args"][-2:] == ["gateway", "run"]
    assert mgc.read_pid() == 9100


def test_start_is_idempotent_when_already_running(monkeypatch) -> None:
    monkeypatch.setattr(mgc, "is_running", lambda: True)
    monkeypatch.setattr(mgc, "read_pid", lambda: 555)

    def _boom(*_a, **_k):  # must NOT spawn
        raise AssertionError("Popen should not be called when already running")

    monkeypatch.setattr(mgc.subprocess, "Popen", _boom)

    ok, msg = mgc.start()
    assert ok is True
    assert "already running" in msg


def test_start_fails_without_foundation_cli(monkeypatch) -> None:
    monkeypatch.setattr(mgc, "messaging_cli", lambda: None)
    ok, msg = mgc.start()
    assert ok is False
    assert "not found" in msg


def test_stop_kills_recorded_pid_and_clears_state(monkeypatch) -> None:
    mgc._write_state({"pid": 7007})
    killed: dict = {}

    if mgc.os.name == "nt":
        def _fake_run(cmd, **kwargs):
            killed["cmd"] = cmd
            return None

        monkeypatch.setattr(mgc.subprocess, "run", _fake_run)
    else:
        def _fake_kill(pid, sig):
            killed["pid"] = pid

        monkeypatch.setattr(mgc.os, "kill", _fake_kill)

    ok, msg = mgc.stop()
    assert ok is True
    assert "7007" in msg
    assert killed  # the platform kill path was exercised
    assert mgc.read_pid() is None


def test_stop_without_pid_is_idempotent_success() -> None:
    ok, msg = mgc.stop()
    assert ok is True
    assert "not running" in msg


def test_status_running_true_when_pid_alive(monkeypatch) -> None:
    mgc._write_state({"pid": 3030})
    monkeypatch.setattr(mgc, "_pid_alive", lambda pid: True)
    assert mgc.status() == {"running": True, "pid": 3030}
