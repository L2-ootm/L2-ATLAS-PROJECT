"""Focused lifecycle and identity tests for cockpit_control."""
from __future__ import annotations

import io
import json
from unittest.mock import MagicMock, patch

import pytest

from atlas_runtime import cockpit_control
from atlas_runtime import service_supervision as supervision


def _response(body: bytes, status: int = 200) -> MagicMock:
    response = MagicMock()
    response.status = status
    response.getcode.return_value = status
    response.read.return_value = body
    response.__enter__.return_value = response
    response.__exit__.return_value = False
    return response


def _observation(pid: int, *, exists: bool = True, executable: str = "node"):
    return supervision.ProcessObservation(
        pid=pid,
        exists=exists,
        identity_available=exists,
        executable_path=executable if exists else None,
        process_creation_time=123456 if exists else None,
    )


def _record(tmp_path, pid: int = 4242):
    record = supervision.create_launch_record(
        service="cockpit",
        pid=pid,
        executable_path="node",
        process_creation_time=123456,
        argv=["node", "serve-dist.mjs"],
        host="127.0.0.1",
        port=5173,
        sensitive_log_path=tmp_path / "cockpit.log",
    )
    supervision.write_launch_record(record, tmp_path / "cockpit.service.json")
    (tmp_path / "cockpit.pid").write_text(str(pid), encoding="utf-8")
    return record


def test_parse_url_authority():
    assert cockpit_control._parse_port("http://127.0.0.1") == 5173
    assert cockpit_control._parse_port("http://127.0.0.1:6173") == 6173
    assert cockpit_control._parse_host("http://127.0.0.1:5173") == "127.0.0.1"
    assert cockpit_control._parse_host("") == "127.0.0.1"
    with pytest.raises(ValueError, match="invalid port"):
        cockpit_control._parse_port("http://127.0.0.1:abc")


def test_health_requires_typed_production_identity(monkeypatch):
    monkeypatch.setattr(cockpit_control, "_using_dist_server", lambda: True)
    valid = json.dumps({"service": "atlas-cockpit", "status": "ok"}).encode()
    with patch("urllib.request.urlopen", return_value=_response(valid)):
        assert cockpit_control.health_ok() is True
    wrong = json.dumps({"service": "some-other-app", "status": "ok"}).encode()
    with patch("urllib.request.urlopen", return_value=_response(wrong)):
        assert cockpit_control.health_ok() is False


def test_health_dev_fallback_requires_stable_html_marker(monkeypatch):
    monkeypatch.setattr(cockpit_control, "_using_dist_server", lambda: False)
    refused = OSError("no /health")
    valid_html = "<title>ATLAS — Cockpit</title>".encode()
    with patch(
        "urllib.request.urlopen",
        side_effect=[refused, _response(valid_html)],
    ):
        assert cockpit_control.health_ok() is True
    with patch(
        "urllib.request.urlopen",
        side_effect=[refused, _response(b"<title>another app</title>")],
    ):
        assert cockpit_control.health_ok() is False


def test_health_returns_false_when_unreachable():
    with patch("urllib.request.urlopen", side_effect=OSError("refused")):
        assert cockpit_control.health_ok() is False


def test_start_is_idempotent_for_identified_listener():
    with patch.object(cockpit_control, "health_ok", return_value=True), patch(
        "subprocess.Popen"
    ) as popen:
        assert cockpit_control.start() == (True, "cockpit already running")
    popen.assert_not_called()


def test_start_blocks_wrong_listener(tmp_path, monkeypatch):
    monkeypatch.setenv("ATLAS_HOME", str(tmp_path))
    monkeypatch.setattr(cockpit_control, "health_ok", lambda: False)
    monkeypatch.setattr(
        cockpit_control,
        "status",
        lambda: {"ready": False, "state": "wrong_listener"},
    )
    with patch("subprocess.Popen") as popen:
        ok, message = cockpit_control.start()
    assert ok is False and "wrong_listener" in message
    popen.assert_not_called()


@pytest.mark.parametrize(
    ("windows", "expected"),
    [(True, "npm.cmd"), (False, "npm")],
)
def test_start_uses_platform_preview_command(tmp_path, monkeypatch, windows, expected):
    monkeypatch.setenv("ATLAS_HOME", str(tmp_path))
    monkeypatch.setattr(cockpit_control, "_is_windows", lambda: windows)
    monkeypatch.setattr(cockpit_control, "_DIST_INDEX", tmp_path / "missing")
    monkeypatch.setattr(cockpit_control, "health_ok", lambda: False)
    monkeypatch.setattr(cockpit_control, "status", lambda: {"ready": False, "state": "stopped"})
    monkeypatch.setattr(cockpit_control, "recover", lambda: {"recovered": False})
    monkeypatch.setattr(cockpit_control, "_observe_spawn", lambda pid: _observation(pid))
    monkeypatch.setattr(supervision, "open_sensitive_log", lambda path: io.BytesIO())
    health = iter([True])
    monkeypatch.setattr(cockpit_control, "health_ok", lambda: next(health))
    # The top-level idempotency probe must be false, then the readiness probe true.
    health = iter([False, True])
    monkeypatch.setattr(cockpit_control, "health_ok", lambda: next(health))
    proc = MagicMock(pid=77)
    proc.poll.return_value = None
    with patch("subprocess.Popen", return_value=proc) as popen:
        ok, _ = cockpit_control.start(poll_seconds=1)
    assert ok is True
    assert popen.call_args.args[0][0] == expected
    kwargs = popen.call_args.kwargs
    if windows:
        assert kwargs["creationflags"] & cockpit_control.CREATE_NO_WINDOW
    else:
        assert kwargs["start_new_session"] is True
    assert (tmp_path / "cockpit.service.json").is_file()
    assert (tmp_path / "cockpit.pid").read_text() == "77"


def test_start_prefers_dependency_free_dist_server(tmp_path, monkeypatch):
    index = tmp_path / "dist" / "index.html"
    server = tmp_path / "scripts" / "serve-dist.mjs"
    index.parent.mkdir()
    server.parent.mkdir()
    index.write_text("ok")
    server.write_text("// server")
    monkeypatch.setattr(cockpit_control, "_DIST_INDEX", index)
    monkeypatch.setattr(cockpit_control, "_DIST_SERVER", server)
    command = cockpit_control._command("127.0.0.1", 5173)
    assert command[1:] == [str(server), "--port", "5173", "--host", "127.0.0.1"]
    assert "npm" not in command[0].lower()


def test_start_detects_early_child_exit_and_reports_sanitized_log(tmp_path, monkeypatch):
    monkeypatch.setenv("ATLAS_HOME", str(tmp_path))
    monkeypatch.setattr(cockpit_control, "health_ok", lambda: False)
    monkeypatch.setattr(cockpit_control, "status", lambda: {"ready": False, "state": "stopped"})
    monkeypatch.setattr(cockpit_control, "recover", lambda: {"recovered": False})
    monkeypatch.setattr(cockpit_control, "_observe_spawn", lambda pid: _observation(pid, exists=False))
    log = tmp_path / "logs" / "cockpit.log"
    log.parent.mkdir()
    log.write_text("token=super-secret\nboom", encoding="utf-8")
    monkeypatch.setattr(supervision, "open_sensitive_log", lambda path: io.BytesIO())
    proc = MagicMock(pid=88)
    proc.poll.return_value = 1
    with patch("subprocess.Popen", return_value=proc):
        ok, message = cockpit_control.start(poll_seconds=0)
    assert ok is False and "exited during startup" in message
    assert "super-secret" not in message
    assert "[REDACTED]" in message


def test_status_reports_wrong_listener_without_state(tmp_path, monkeypatch):
    monkeypatch.setenv("ATLAS_HOME", str(tmp_path))
    monkeypatch.setattr(cockpit_control, "_health_kind", lambda: "none")
    monkeypatch.setattr(
        supervision,
        "observe_port",
        lambda *args, **kwargs: supervision.PortObservation("127.0.0.1", 5173, True),
    )
    result = cockpit_control.status()
    assert result["state"] == "wrong_listener"
    assert result["ready"] is False


def test_status_reports_ready_only_for_exact_process_and_health(tmp_path, monkeypatch):
    monkeypatch.setenv("ATLAS_HOME", str(tmp_path))
    _record(tmp_path)
    monkeypatch.setattr(cockpit_control, "_health_kind", lambda: "production")
    monkeypatch.setattr(supervision, "observe_process", lambda pid: _observation(pid))
    monkeypatch.setattr(
        supervision,
        "observe_port",
        lambda *args, **kwargs: supervision.PortObservation("127.0.0.1", 5173, True),
    )
    result = cockpit_control.status()
    assert result["state"] == "ready"
    assert result["ready"] is True
    assert result["identity"]["matches"] is True


def test_stop_without_state_preserves_legacy_compatibility(tmp_path, monkeypatch):
    monkeypatch.setenv("ATLAS_HOME", str(tmp_path))
    assert cockpit_control.stop() == (False, "no pid file; cockpit not managed here")


def test_stop_removes_invalid_legacy_pid(tmp_path, monkeypatch):
    monkeypatch.setenv("ATLAS_HOME", str(tmp_path))
    pid = tmp_path / "cockpit.pid"
    pid.write_text("not-a-pid")
    assert cockpit_control.stop() == (False, "invalid pid file (removed)")
    assert not pid.exists()


def test_stop_refuses_live_legacy_pid_without_identity(tmp_path, monkeypatch):
    monkeypatch.setenv("ATLAS_HOME", str(tmp_path))
    (tmp_path / "cockpit.pid").write_text("4242")
    monkeypatch.setattr(supervision, "observe_process", lambda pid: _observation(pid))
    with patch.object(cockpit_control, "_signal_posix_process_tree") as kill:
        ok, message = cockpit_control.stop()
    assert ok is False and "refusing" in message
    assert (tmp_path / "cockpit.pid").exists()
    kill.assert_not_called()


def test_stop_refuses_reused_pid_and_retains_state(tmp_path, monkeypatch):
    monkeypatch.setenv("ATLAS_HOME", str(tmp_path))
    _record(tmp_path)
    monkeypatch.setattr(supervision, "observe_process", lambda pid: _observation(pid, executable="other"))
    with patch.object(cockpit_control, "_signal_posix_process_tree") as kill:
        ok, message = cockpit_control.stop()
    assert ok is False and "executable_mismatch" in message
    assert (tmp_path / "cockpit.service.json").exists()
    kill.assert_not_called()


def test_stop_signals_exact_posix_process_and_verifies_exit(tmp_path, monkeypatch):
    monkeypatch.setenv("ATLAS_HOME", str(tmp_path))
    _record(tmp_path)
    monkeypatch.setattr(cockpit_control, "_is_windows", lambda: False)
    monkeypatch.setattr(supervision, "observe_process", lambda pid: _observation(pid))
    monkeypatch.setattr(cockpit_control, "_wait_for_record_exit", lambda record: True)
    with patch.object(cockpit_control, "_signal_posix_process_tree") as kill:
        ok, message = cockpit_control.stop()
    assert ok is True and "4242" in message
    kill.assert_called_once_with(4242)
    assert not (tmp_path / "cockpit.service.json").exists()
    assert not (tmp_path / "cockpit.pid").exists()


def test_stop_retains_state_when_termination_unverified(tmp_path, monkeypatch):
    monkeypatch.setenv("ATLAS_HOME", str(tmp_path))
    _record(tmp_path)
    monkeypatch.setattr(cockpit_control, "_is_windows", lambda: False)
    monkeypatch.setattr(supervision, "observe_process", lambda pid: _observation(pid))
    monkeypatch.setattr(cockpit_control, "_wait_for_record_exit", lambda record: False)
    with patch.object(cockpit_control, "_signal_posix_process_tree"):
        ok, message = cockpit_control.stop()
    assert ok is False and "state retained" in message
    assert (tmp_path / "cockpit.service.json").exists()


def test_recover_removes_only_confirmed_dead_state(tmp_path, monkeypatch):
    monkeypatch.setenv("ATLAS_HOME", str(tmp_path))
    _record(tmp_path)
    monkeypatch.setattr(supervision, "observe_process", lambda pid: _observation(pid, exists=False))
    assert cockpit_control.recover()["recovered"] is True
    assert not (tmp_path / "cockpit.service.json").exists()


def test_recover_refuses_live_process(tmp_path, monkeypatch):
    monkeypatch.setenv("ATLAS_HOME", str(tmp_path))
    _record(tmp_path)
    monkeypatch.setattr(supervision, "observe_process", lambda pid: _observation(pid))
    result = cockpit_control.recover()
    assert result == {"recovered": False, "reason": "process_exists", "pid": 4242}
    assert (tmp_path / "cockpit.service.json").exists()
