"""Tests for cockpit_control.py — the cockpit's twin of gateway_control.py.

Covers health probing, idempotent start, the Windows console-flash regression
guard (CREATE_NO_WINDOW, per commit 62e9456's bug class), npm.cmd resolution,
and PID-file-based stop.
"""
from __future__ import annotations

import subprocess
from unittest.mock import MagicMock, patch

from atlas_runtime import cockpit_control


def test_health_ok_returns_false_when_nothing_listening():
    with patch("urllib.request.urlopen", side_effect=OSError("connection refused")):
        assert cockpit_control.health_ok() is False


def test_health_ok_returns_true_when_server_responds():
    mock_resp = MagicMock()
    mock_resp.__enter__.return_value = mock_resp
    mock_resp.__exit__.return_value = False
    with patch("urllib.request.urlopen", return_value=mock_resp):
        assert cockpit_control.health_ok() is True


def test_start_is_idempotent_when_already_healthy():
    with patch.object(cockpit_control, "health_ok", return_value=True):
        with patch("subprocess.Popen") as mock_popen:
            ok, message = cockpit_control.start()
    assert ok is True
    assert message == "cockpit already running"
    mock_popen.assert_not_called()


def test_start_on_windows_sets_console_flash_guard_flags(tmp_path, monkeypatch):
    monkeypatch.setattr(cockpit_control.os, "name", "nt")
    health_calls = iter([False, True])
    monkeypatch.setattr(cockpit_control, "health_ok", lambda timeout=1.0: next(health_calls))
    pid_file = tmp_path / "cockpit.pid"
    monkeypatch.setattr(cockpit_control, "PID_FILE", pid_file)

    mock_proc = MagicMock()
    mock_proc.pid = 4242
    with patch("subprocess.Popen", return_value=mock_proc) as mock_popen:
        ok, message = cockpit_control.start(poll_seconds=1.0)

    assert ok is True
    assert "4242" in message
    assert mock_popen.called
    _, kwargs = mock_popen.call_args
    assert kwargs["cwd"] == str(cockpit_control._COCKPIT_DIR)
    flags = kwargs["creationflags"]
    assert flags & subprocess.DETACHED_PROCESS
    assert flags & subprocess.CREATE_NEW_PROCESS_GROUP
    assert flags & subprocess.CREATE_NO_WINDOW


def test_start_resolves_npm_cmd_on_windows(tmp_path, monkeypatch):
    monkeypatch.setattr(cockpit_control.os, "name", "nt")
    health_calls = iter([False, True])
    monkeypatch.setattr(cockpit_control, "health_ok", lambda timeout=1.0: next(health_calls))
    monkeypatch.setattr(cockpit_control, "PID_FILE", tmp_path / "cockpit.pid")

    mock_proc = MagicMock()
    mock_proc.pid = 1
    with patch("subprocess.Popen", return_value=mock_proc) as mock_popen:
        cockpit_control.start(poll_seconds=1.0)

    args, _ = mock_popen.call_args
    assert args[0][0] == "npm.cmd"


def test_start_resolves_npm_on_posix(tmp_path, monkeypatch):
    monkeypatch.setattr(cockpit_control.os, "name", "posix")
    health_calls = iter([False, True])
    monkeypatch.setattr(cockpit_control, "health_ok", lambda timeout=1.0: next(health_calls))
    monkeypatch.setattr(cockpit_control, "PID_FILE", tmp_path / "cockpit.pid")

    mock_proc = MagicMock()
    mock_proc.pid = 1
    with patch("subprocess.Popen", return_value=mock_proc) as mock_popen:
        cockpit_control.start(poll_seconds=1.0)

    args, _ = mock_popen.call_args
    assert args[0][0] == "npm"


def test_stop_with_no_pid_file_returns_message(tmp_path, monkeypatch):
    monkeypatch.setattr(cockpit_control, "PID_FILE", tmp_path / "cockpit.pid")
    ok, message = cockpit_control.stop()
    assert ok is False
    assert message == "no pid file; cockpit not managed here"
