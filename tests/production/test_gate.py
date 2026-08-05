from __future__ import annotations

import importlib.util
import json
import re
import subprocess
import sys
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[2]
SPEC = importlib.util.spec_from_file_location(
    "production_gate", ROOT / "scripts/production/gate.py"
)
assert SPEC and SPEC.loader
gate = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = gate
SPEC.loader.exec_module(gate)


def paths(tmp_path: Path, token: str = "1234abcd"):
    root = tmp_path / f"atlas-production-gate-{token}"
    return gate.GatePaths(
        root=root,
        atlas_home=root / "atlas-home",
        database=root / "data" / "atlas.db",
        config=root / "atlas-home" / "config.yaml",
        npm_prefix=root / "npm-prefix",
        install_root=None,
    )


def config(tmp_path: Path, **changes):
    gateway_binary = tmp_path / "gateway.exe"
    gateway_binary.touch(exist_ok=True)
    values = {
        "mode": "source",
        "repo": ROOT,
        "paths": paths(tmp_path),
        "ports": (18484, 15173, 13001),
        "gateway_binary": gateway_binary,
        "release_version": "0.1.5",
        "test_labels": (),
        "resume": False,
    }
    values.update(changes)
    return gate.GateConfig(**values)


def test_rejects_path_escape_and_relative_mutation_root(tmp_path: Path):
    safe = paths(tmp_path)
    with pytest.raises(gate.GateError, match="descendant"):
        gate.validate_paths(
            gate.GatePaths(
                safe.root,
                tmp_path / "escape",
                safe.database,
                safe.config,
                safe.npm_prefix,
            ),
            repo=ROOT,
            resume=False,
        )
    with pytest.raises(gate.GateError, match="explicit absolute"):
        gate.validate_paths(
            gate.GatePaths(
                safe.root, Path("relative"), safe.database, safe.config, safe.npm_prefix
            ),
            repo=ROOT,
            resume=False,
        )


def test_rejects_existing_root_live_environment_and_default_port(
    tmp_path: Path, monkeypatch
):
    safe = paths(tmp_path)
    safe.root.mkdir()
    with pytest.raises(gate.GateError, match="must not already exist"):
        gate.validate_paths(safe, repo=ROOT, resume=False)
    safe.root.rmdir()
    monkeypatch.setenv("ATLAS_HOME", str(safe.atlas_home))
    with pytest.raises(gate.GateError, match="live environment"):
        gate.validate_paths(safe, repo=ROOT, resume=False)
    with pytest.raises(gate.GateError, match="default"):
        gate.validate_ports((8484, 15173, 13001))
    monkeypatch.setenv("ATLAS_GATEWAY_URL", "http://127.0.0.1:18484")
    with pytest.raises(gate.GateError, match="live ATLAS"):
        gate.validate_ports((18484, 15173, 13001))


def test_command_catalog_rejects_unknown_and_contains_no_shell_strings(tmp_path: Path):
    with pytest.raises(gate.GateError, match="not allowlisted"):
        gate.validate_test_labels(("python-core; Remove-Item -Recurse C:\\",))
    commands = gate.build_commands(
        config(tmp_path, test_labels=("planning", "node-cli", "rust-gateway"))
    )
    assert [item.label for item in commands[:8]] == list(gate.REQUIRED_LABELS)
    assert all(isinstance(item.argv, tuple) and item.argv for item in commands)
    assert {item.label for item in commands[8:-3]} == {
        "test:planning",
        "test:node-cli",
        "test:rust-gateway",
    }
    assert commands[5].argv[-3:] == ("gateway", "status", "--json")
    assert commands[-3].label == "stop-ordered"
    assert commands[-2].expectation == "stopped"
    rust = next(item for item in commands if item.label == "test:rust-gateway")
    assert "native/atlas-core-rs/Cargo.toml" in rust.argv


def test_runner_never_uses_a_shell(tmp_path: Path, monkeypatch):
    observed = {}

    class Completed:
        returncode = 0
        stdout = b""

    def fake_run(argv, **kwargs):
        observed["argv"] = argv
        observed.update(kwargs)
        return Completed()

    monkeypatch.setattr(gate.subprocess, "run", fake_run)
    command = gate.Command("gate-99-test", "test:planning", ("python", "-V"), tmp_path)
    assert gate.default_runner(command, {}) == 0
    assert observed["argv"] == command.argv
    assert observed["shell"] is False


@pytest.mark.parametrize(
    ("payload", "expected"),
    [
        ({"ready": True}, 0),
        ({"ready": False, "running": True}, 1),
        ({"running": True}, 0),
    ],
)
def test_status_is_a_readiness_gate(tmp_path: Path, monkeypatch, payload, expected):
    class Completed:
        returncode = 0
        stdout = json.dumps(payload).encode()

    monkeypatch.setattr(gate.subprocess, "run", lambda *_args, **_kwargs: Completed())
    command = gate.Command(
        "gate-06-ready",
        "status-ready",
        ("atlas", "gateway", "status"),
        tmp_path,
        "ready",
    )
    assert gate.default_runner(command, {}) == expected


@pytest.mark.parametrize(
    ("expectation", "payload", "expected"),
    [
        ("stopped", {"running": False, "state": "stopped"}, 0),
        ("stopped", {"running": True, "state": "ready"}, 1),
        (
            "idempotent",
            {
                "components": [
                    {"component": "gateway", "ok": True, "code": "already_ready"},
                    {"component": "cockpit", "ok": True, "code": "already_ready"},
                ]
            },
            0,
        ),
    ],
)
def test_structured_lifecycle_expectations(
    tmp_path: Path, monkeypatch, expectation, payload, expected
):
    class Completed:
        returncode = 0
        stdout = json.dumps(payload).encode()

    monkeypatch.setattr(gate.subprocess, "run", lambda *_args, **_kwargs: Completed())
    command = gate.Command("gate-x", "lifecycle", ("atlas",), tmp_path, expectation)
    assert gate.default_runner(command, {}) == expected


def test_prepare_config_is_atomic_and_idempotent(tmp_path: Path):
    target = tmp_path / "atlas-home" / "config.yaml"
    argv = [
        sys.executable,
        str(ROOT / "scripts/production/prepare_config.py"),
        "--path",
        str(target),
        "--gateway-port",
        "18484",
        "--cockpit-port",
        "15173",
    ]
    subprocess.run(argv, check=True)
    subprocess.run(argv, check=True)
    assert target.read_text(encoding="utf-8") == (
        "schema_version: 2\nrevision: 1\ngateway:\n  rust_port: 18484\n"
        "cockpit:\n  port: 15173\n"
    )
    assert not list(target.parent.glob("*.tmp"))


def test_secret_scanner_rejects_canary_and_credentials():
    gate.scan_for_secrets({"status": "passed"}, canary="never-store-me")
    with pytest.raises(gate.GateError, match="canary"):
        gate.scan_for_secrets({"detail": "never-store-me"}, canary="never-store-me")
    with pytest.raises(gate.GateError, match="credential"):
        gate.scan_for_secrets({"detail": "authorization: bearer abc"}, canary="unused")


def test_fail_fast_writes_bounded_evidence_without_command_output(tmp_path: Path):
    calls = []

    def runner(command, env):
        calls.append(command.label)
        assert env[gate.CANARY_NAME]
        return 23 if command.label == "gateway-identity" else 0

    with pytest.raises(gate.GateError, match="gateway-identity"):
        gate.execute_gate(config(tmp_path), runner=runner)
    assert calls == [
        "planning-integrity",
        "prepare-config",
        "prepare-database",
        "gateway-identity",
        "stop-ordered",
        "status-stopped",
        "recover-state",
    ]
    evidence_file = paths(tmp_path).root / "evidence" / "production-gate.json"
    evidence = json.loads(evidence_file.read_text(encoding="utf-8"))
    assert evidence["status"] == "failed"
    assert (
        next(step for step in evidence["steps"] if step["label"] == "gateway-identity")[
            "status"
        ]
        == "failed"
    )
    assert [step["label"] for step in evidence["steps"][-3:]] == [
        "stop-ordered",
        "status-stopped",
        "recover-state",
    ]
    rendered = evidence_file.read_text(encoding="utf-8").lower()
    for forbidden in (
        "stdout",
        "stderr",
        "argv",
        "environment",
        "prompt",
        "patch",
        "raw_log",
    ):
        assert forbidden not in rendered


def test_dry_run_has_stable_evidence_schema_and_cleanup_is_manifest_only(
    tmp_path: Path,
):
    evidence = gate.execute_gate(config(tmp_path), dry_run=True)
    assert set(evidence) == {
        "schema_version",
        "gate_id",
        "mode",
        "started_at",
        "finished_at",
        "status",
        "steps",
    }
    assert evidence["schema_version"] == 1
    assert evidence["status"] == "dry_run"
    assert all(
        set(step) == {"id", "label", "status", "duration_ms"}
        for step in evidence["steps"]
    )
    assert all(re.fullmatch(r"gate-\d{2}-.+", step["id"]) for step in evidence["steps"])
    cleanup = json.loads(
        (paths(tmp_path).root / "cleanup-manifest.json").read_text(encoding="utf-8")
    )
    assert cleanup["policy"] == "manifest-only-no-delete"
    assert not any("delete" in key.lower() for key in cleanup if key != "policy")


def test_resume_skips_passed_steps_and_rejects_changed_plan(tmp_path: Path):
    first = config(tmp_path)
    seen = []
    gate.execute_gate(first, runner=lambda command, _env: seen.append(command.id) or 0)
    resumed = config(tmp_path, resume=True)
    rerun = []
    evidence = gate.execute_gate(
        resumed, runner=lambda command, _env: rerun.append(command.id) or 0
    )
    assert rerun == ["gate-90-stop", "gate-91-stopped", "gate-92-recover"]
    assert all(step["status"] == "resumed" for step in evidence["steps"][:-3])
    assert all(step["status"] == "passed" for step in evidence["steps"][-3:])
    changed = config(tmp_path, resume=True, release_version="9.9.9")
    with pytest.raises(gate.GateError, match="does not match"):
        gate.execute_gate(changed, runner=lambda *_: 0)


def test_failed_lifecycle_resume_replays_start_after_guaranteed_stop(tmp_path: Path):
    def fail_doctor(command, _env):
        return 1 if command.label == "doctor" else 0

    with pytest.raises(gate.GateError, match="doctor"):
        gate.execute_gate(config(tmp_path), runner=fail_doctor)
    state = json.loads((paths(tmp_path).root / "gate-state.json").read_text())
    assert state["passed"] == [
        "gate-01-planning",
        "gate-02-config",
        "gate-03-database",
        "gate-04-identity",
    ]
    replayed = []
    gate.execute_gate(
        config(tmp_path, resume=True),
        runner=lambda command, _env: replayed.append(command.label) or 0,
    )
    assert replayed[0] == "start-core"
    assert replayed[-3:] == ["stop-ordered", "status-stopped", "recover-state"]


def test_runner_exception_still_executes_all_teardown_steps(tmp_path: Path):
    seen = []

    def crashing_runner(command, _env):
        seen.append(command.label)
        if command.label == "status-ready":
            raise RuntimeError("sensitive output must not escape")
        return 0

    with pytest.raises(gate.GateError, match="status-ready"):
        gate.execute_gate(config(tmp_path), runner=crashing_runner)
    assert seen[-3:] == ["stop-ordered", "status-stopped", "recover-state"]
    evidence = json.loads(
        (paths(tmp_path).root / "evidence" / "production-gate.json").read_text()
    )
    failed = next(step for step in evidence["steps"] if step["label"] == "status-ready")
    assert failed["failure_kind"] == "RuntimeError"
    assert "sensitive output" not in json.dumps(evidence)


def test_installed_mode_requires_launcher_and_binary_below_install_root(tmp_path: Path):
    isolated = paths(tmp_path)
    install_root = isolated.root / "installed"
    installed_paths = gate.GatePaths(
        isolated.root,
        isolated.atlas_home,
        isolated.database,
        isolated.config,
        isolated.npm_prefix,
        install_root,
    )
    with pytest.raises(gate.GateError, match="launcher"):
        gate.execute_gate(
            config(tmp_path, mode="installed", paths=installed_paths), dry_run=True
        )
    with pytest.raises(gate.GateError, match="gateway binary"):
        gate.execute_gate(
            config(
                tmp_path,
                mode="installed",
                paths=installed_paths,
                installed_launcher=install_root / "atlas.exe",
            ),
            dry_run=True,
        )
