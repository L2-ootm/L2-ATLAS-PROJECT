"""Tests for cockpit_control.py — the cockpit's twin of gateway_control.py.

Covers health probing, idempotent start, the Windows console-flash regression
guard (CREATE_NO_WINDOW, per commit 62e9456's bug class), npm.cmd resolution,
and PID-file-based stop.
"""
from __future__ import annotations

import subprocess
from unittest.mock import MagicMock, patch

import pytest

from atlas_runtime import cockpit_control


def test_parse_port_returns_default_for_portless_url():
    assert cockpit_control._parse_port("http://127.0.0.1") == 5173


def test_parse_port_returns_explicit_port():
    assert cockpit_control._parse_port("http://127.0.0.1:6173") == 6173


def test_parse_port_raises_on_invalid_port():
    with pytest.raises(ValueError, match="invalid port"):
        cockpit_control._parse_port("http://127.0.0.1:abc")


def test_parse_host_returns_explicit_host():
    assert cockpit_control._parse_host("http://127.0.0.1:5173") == "127.0.0.1"


def test_parse_host_defaults_when_hostless():
    assert cockpit_control._parse_host("") == "127.0.0.1"


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
    # The bind host must be passed so Vite binds the interface health_ok probes
    # (Windows IPv4/IPv6 localhost split — see _parse_host).
    spawn_cmd = args[0]
    assert "--host" in spawn_cmd
    assert spawn_cmd[spawn_cmd.index("--host") + 1] == "127.0.0.1"


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


def test_stop_skips_signal_and_unlinks_when_pid_already_gone(tmp_path, monkeypatch):
    pid_file = tmp_path / "cockpit.pid"
    pid_file.write_text("99999")
    monkeypatch.setattr(cockpit_control, "PID_FILE", pid_file)
    monkeypatch.setattr(cockpit_control, "_pid_alive", lambda pid: False)
    with patch("subprocess.run") as mock_run, patch("os.kill") as mock_kill:
        ok, message = cockpit_control.stop()
    assert ok is False
    assert "already gone" in message
    assert "99999" in message
    assert not pid_file.exists()
    mock_run.assert_not_called()
    mock_kill.assert_not_called()


def test_stop_signals_when_pid_is_alive(tmp_path, monkeypatch):
    pid_file = tmp_path / "cockpit.pid"
    pid_file.write_text("4242")
    monkeypatch.setattr(cockpit_control, "PID_FILE", pid_file)
    monkeypatch.setattr(cockpit_control, "_pid_alive", lambda pid: True)
    monkeypatch.setattr(cockpit_control.os, "name", "posix")
    with patch("os.kill") as mock_kill:
        ok, message = cockpit_control.stop()
    assert ok is True
    assert "4242" in message
    mock_kill.assert_called_once_with(4242, 15)
    assert not pid_file.exists()


def test_pid_alive_posix_returns_false_for_dead_pid(monkeypatch):
    monkeypatch.setattr(cockpit_control.os, "name", "posix")
    with patch("os.kill", side_effect=ProcessLookupError):
        assert cockpit_control._pid_alive(123) is False


def test_pid_alive_posix_returns_true_for_live_pid(monkeypatch):
    monkeypatch.setattr(cockpit_control.os, "name", "posix")
    with patch("os.kill", return_value=None):
        assert cockpit_control._pid_alive(123) is True


def test_pid_alive_windows_checks_tasklist_output(monkeypatch):
    monkeypatch.setattr(cockpit_control.os, "name", "nt")
    mock_result = MagicMock()
    mock_result.stdout = "node.exe                      4242 Console"
    with patch("subprocess.run", return_value=mock_result) as mock_run:
        assert cockpit_control._pid_alive(4242) is True
        args = mock_run.call_args[0][0]
        assert args[0] == "tasklist"
        assert "PID eq 4242" in args


def test_pid_alive_windows_returns_false_when_pid_absent(monkeypatch):
    monkeypatch.setattr(cockpit_control.os, "name", "nt")
    mock_result = MagicMock()
    mock_result.stdout = "INFO: No tasks are running which match the specified criteria."
    with patch("subprocess.run", return_value=mock_result):
        assert cockpit_control._pid_alive(4242) is False
