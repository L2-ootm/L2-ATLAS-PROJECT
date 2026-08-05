"""Tests for freellmapi_control — the external-sidecar process primitive.

Only the deterministic pieces (no real node process is started, no network).
"""

from __future__ import annotations

import pathlib
import subprocess
import json

from typer.testing import CliRunner

from atlas_runtime import freellmapi_control as fc
from atlas_runtime import service_supervision as supervision
from atlas_runtime.cli.main import app

runner = CliRunner()


def _offline(monkeypatch) -> None:
    monkeypatch.setattr(fc, "health_ok", lambda timeout=1.0: False)
    monkeypatch.setattr(
        fc,
        "_models_probe",
        lambda timeout=1.0: fc.ModelsProbe(False, False, "offline"),
    )


def test_status_shape(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(fc, "STATE_FILE", tmp_path / "freellmapi.json")
    _offline(monkeypatch)
    st = fc.status()
    assert {
        "running",
        "base_url",
        "dir",
        "installed",
        "api_key_configured",
        "remediation",
    } <= set(st)
    assert st["running"] is False
    assert st["state"] == "stopped"
    assert st["ready"] is False
    assert st["base_url"].startswith("http")


def test_metadata_path_late_binds_atlas_home(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(fc, "STATE_FILE", None)
    monkeypatch.setenv("ATLAS_HOME", str(tmp_path / "one"))
    assert fc._metadata_path() == tmp_path / "one" / "freellmapi.json"
    monkeypatch.setenv("ATLAS_HOME", str(tmp_path / "two"))
    assert fc._metadata_path() == tmp_path / "two" / "freellmapi.json"


def test_models_probe_rejects_wrong_http_listener(monkeypatch) -> None:
    class _Response:
        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return None

        def read(self, _limit):
            return json.dumps({"service": "not-freellmapi"}).encode()

    monkeypatch.setattr(fc, "get_api_key", lambda: None)
    monkeypatch.setattr(
        fc.urllib.request, "urlopen", lambda *_args, **_kwargs: _Response()
    )
    probe = fc._models_probe()
    assert probe.reachable is True
    assert probe.identity_valid is False
    assert fc.health_ok() is False


def test_models_probe_accepts_openai_models_document(monkeypatch) -> None:
    class _Response:
        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return None

        def read(self, _limit):
            return b'{"object":"list","data":[{"id":"gpt-free"}]}'

    monkeypatch.setattr(fc, "get_api_key", lambda: None)
    monkeypatch.setattr(
        fc.urllib.request, "urlopen", lambda *_args, **_kwargs: _Response()
    )
    assert fc._models_probe().identity_valid is True


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
    monkeypatch.setenv("ATLAS_HOME", str(tmp_path))
    monkeypatch.setattr(fc, "STATE_FILE", tmp_path / "freellmapi.json")
    ok, msg = fc.stop()
    assert ok is False
    assert "no pid" in msg


def test_cli_status_json(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("ATLAS_HOME", str(tmp_path))
    monkeypatch.setattr(fc, "STATE_FILE", tmp_path / "freellmapi.json")
    monkeypatch.setattr(fc, "get_api_key", lambda: "fk-secret-value")
    _offline(monkeypatch)
    result = runner.invoke(app, ["freellmapi", "status", "--json"])
    assert result.exit_code == 0
    assert '"running": false' in result.output
    assert '"api_key_configured": true' in result.output
    assert "fk-secret-value" not in result.output


def test_cli_start_not_installed_exits_nonzero(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("ATLAS_HOME", str(tmp_path))
    monkeypatch.setattr(fc, "STATE_FILE", tmp_path / "freellmapi.json")
    monkeypatch.setattr(fc, "resolve_dir", lambda: None)
    _offline(monkeypatch)
    result = runner.invoke(app, ["freellmapi", "start"])
    assert result.exit_code == 1
    assert "ATLAS_FREELLMAPI_DIR" in result.output


def test_status_reports_owned_process_starting_until_models_ready(
    tmp_path, monkeypatch
) -> None:
    monkeypatch.setenv("ATLAS_HOME", str(tmp_path))
    monkeypatch.setattr(fc, "STATE_FILE", tmp_path / "freellmapi.json")
    monkeypatch.setattr(fc, "resolve_dir", lambda: tmp_path)
    monkeypatch.setattr(fc, "get_api_key", lambda: None)
    _offline(monkeypatch)
    record = supervision.create_launch_record(
        service=fc.SERVICE,
        pid=321,
        executable_path="node",
        process_creation_time=42,
        argv=["node", "index.js"],
        host="127.0.0.1",
        port=fc.DEFAULT_PORT,
        sensitive_log_path=tmp_path / "freellmapi.log",
    )
    supervision.write_launch_record(record, fc._service_state_path())
    monkeypatch.setattr(
        supervision,
        "observe_process",
        lambda pid: supervision.ProcessObservation(pid, True, True, "node", 42),
    )
    monkeypatch.setattr(
        supervision,
        "observe_port",
        lambda host, port, timeout=0.2: supervision.PortObservation(host, port, False),
    )
    st = fc.status()
    assert st["state"] == "starting"
    assert st["owned"] is True
    assert st["running"] is False


def test_stop_identity_mismatch_retains_state(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("ATLAS_HOME", str(tmp_path))
    monkeypatch.setattr(fc, "STATE_FILE", tmp_path / "freellmapi.json")
    record = supervision.create_launch_record(
        service=fc.SERVICE,
        pid=321,
        executable_path="expected-node",
        process_creation_time=42,
        argv=["node", "index.js"],
        host="127.0.0.1",
        port=fc.DEFAULT_PORT,
        sensitive_log_path=tmp_path / "freellmapi.log",
    )
    supervision.write_launch_record(record, fc._service_state_path())
    monkeypatch.setattr(
        supervision,
        "observe_process",
        lambda pid: supervision.ProcessObservation(pid, True, True, "other-node", 42),
    )
    monkeypatch.setattr(
        supervision,
        "observe_port",
        lambda host, port, timeout=0.2: supervision.PortObservation(host, port, True),
    )
    ok, message = fc.stop()
    assert ok is False
    assert "refusing unsafe stop" in message
    assert fc._service_state_path().exists()


def test_start_writes_canonical_identity_and_legacy_projection(
    tmp_path, monkeypatch
) -> None:
    monkeypatch.setenv("ATLAS_HOME", str(tmp_path / "atlas"))
    monkeypatch.setattr(fc, "STATE_FILE", tmp_path / "metadata.json")
    checkout = tmp_path / "checkout"
    entry = checkout / "server" / "dist" / "index.js"
    entry.parent.mkdir(parents=True)
    entry.write_text("// built", encoding="utf-8")
    monkeypatch.setattr(fc, "resolve_dir", lambda: checkout)
    monkeypatch.setattr(
        fc,
        "status",
        lambda: {"state": "stopped", "owned": False, "pid": None, "remediation": None},
    )
    monkeypatch.setattr(fc.shutil, "which", lambda name: "C:/node/node.exe")

    class _Process:
        pid = 4321

        @staticmethod
        def poll():
            return None

    monkeypatch.setattr(fc.subprocess, "Popen", lambda *_args, **_kwargs: _Process())
    monkeypatch.setattr(
        supervision,
        "observe_process",
        lambda pid: supervision.ProcessObservation(
            pid, True, True, "C:/node/node.exe", 987654
        ),
    )

    ok, message = fc.start()

    assert ok is True
    assert "starting" in message
    record = supervision.load_launch_record(fc._service_state_path())
    assert record is not None
    assert record.pid == 4321
    assert record.process_creation_time == 987654
    assert fc._legacy_pid_path().read_text(encoding="ascii").strip() == "4321"


def test_verified_stop_removes_state_only_after_process_is_dead(
    tmp_path, monkeypatch
) -> None:
    monkeypatch.setenv("ATLAS_HOME", str(tmp_path))
    monkeypatch.setattr(fc, "STATE_FILE", tmp_path / "metadata.json")
    fc._write_state({"pid": 4321, "dir": str(tmp_path / "checkout")})
    record = supervision.create_launch_record(
        service=fc.SERVICE,
        pid=4321,
        executable_path="node",
        process_creation_time=99,
        argv=["node", "index.js"],
        host="127.0.0.1",
        port=fc.DEFAULT_PORT,
        sensitive_log_path=tmp_path / "freellmapi.log",
    )
    supervision.write_launch_record(record, fc._service_state_path())
    fc._legacy_pid_path().write_text("4321\n", encoding="ascii")
    monkeypatch.setattr(
        supervision,
        "observe_process",
        lambda pid: supervision.ProcessObservation(pid, True, True, "node", 99),
    )
    monkeypatch.setattr(
        supervision,
        "observe_port",
        lambda host, port, timeout=0.2: supervision.PortObservation(host, port, True),
    )
    terminated: list[int] = []
    monkeypatch.setattr(fc, "_terminate_pid", lambda pid: terminated.append(pid))
    monkeypatch.setattr(fc, "_wait_until_dead", lambda pid, timeout=5.0: True)

    ok, message = fc.stop()

    assert ok is True
    assert "stopped" in message
    assert terminated == [4321]
    assert not fc._service_state_path().exists()
    assert not fc._legacy_pid_path().exists()
    assert "pid" not in fc._read_state()


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
    monkeypatch.setattr(
        fc.shutil, "which", lambda name: "git" if "git" in name else None
    )
    ok, msg = fc.install(pathlib.Path("/tmp/wherever"))
    assert ok is False
    assert "npm" in msg


def test_install_rejects_existing_non_checkout_without_force(
    tmp_path, monkeypatch
) -> None:
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
    monkeypatch.setattr(
        fc, "install", lambda target=None, force=False: (True, "freellmapi installed")
    )
    result = runner.invoke(app, ["freellmapi", "install", "--json"])
    assert result.exit_code == 0
    assert '"ok": true' in result.output


def test_installed_redaction_probe_never_echoes_canary_on_setup_failure(
    tmp_path, monkeypatch
) -> None:
    canary = "ATLAS-SECRET-CANARY-DO-NOT-PRINT"
    monkeypatch.setenv("ATLAS_TEST_SECRET_CANARY", canary)
    result = subprocess.run(
        [
            "node",
            str(
                pathlib.Path(__file__).resolve().parents[3]
                / "scripts"
                / "ci"
                / "verify-clean-install.js"
            ),
            "--local-index",
            str(tmp_path / "missing.json"),
            "--home",
            str(tmp_path / "install"),
            "--version",
            "0.1.5",
            "--probe-freellmapi-redaction",
        ],
        cwd=tmp_path,
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode != 0
    assert canary not in result.stdout
    assert canary not in result.stderr
