"""Tests for atlas config + atlas setup CLI."""
from __future__ import annotations

import json
import threading

from typer.testing import CliRunner

from atlas_runtime import config_service as cfgsvc
from atlas_runtime.cli import config as cli_config
from atlas_runtime.cli.main import app

runner = CliRunner()


def _home(monkeypatch, tmp_path, db=None, lock: threading.Lock | None = None):
    monkeypatch.setenv("ATLAS_HOME", str(tmp_path))
    if db is not None:
        monkeypatch.setattr(cli_config, "_get_connection", lambda: db)
    if lock is not None:
        monkeypatch.setattr(cli_config, "_get_lock", lambda: lock)
    return tmp_path / "config.yaml"


def test_config_show_defaults(monkeypatch, tmp_path, db, lock):
    _home(monkeypatch, tmp_path, db, lock)
    result = runner.invoke(app, ["config", "show"])
    assert result.exit_code == 0
    assert "provider:" in result.output
    assert "openrouter" in result.output


def test_config_set_then_get(monkeypatch, tmp_path, db, lock):
    _home(monkeypatch, tmp_path, db, lock)
    r1 = runner.invoke(app, ["config", "set", "runtime.iteration_budget", "42"])
    assert r1.exit_code == 0
    r2 = runner.invoke(app, ["config", "get", "runtime.iteration_budget"])
    assert r2.exit_code == 0
    assert "42" in r2.output
    # Persisted to disk.
    assert cfgsvc.load_config(tmp_path / "config.yaml").runtime.iteration_budget == 42


def test_config_set_inline_secret_rejected(monkeypatch, tmp_path, db, lock):
    _home(monkeypatch, tmp_path, db, lock)
    result = runner.invoke(app, ["config", "set", "provider.api_key", "sk-leak123"])
    assert result.exit_code == 1
    assert "invalid value" in result.output


def test_config_get_unknown_key(monkeypatch, tmp_path):
    _home(monkeypatch, tmp_path)
    result = runner.invoke(app, ["config", "get", "provider.nope"])
    assert result.exit_code == 1
    assert "unknown key" in result.output


def test_config_has_context_defaults(monkeypatch, tmp_path):
    _home(monkeypatch, tmp_path)
    cfg = cfgsvc.load_config(tmp_path / "config.yaml")
    assert cfg.context.token_budget == 8000
    assert cfg.context.enable_semantic is True
    assert cfg.context.enable_skills is True


def test_config_get_context_token_budget(monkeypatch, tmp_path):
    _home(monkeypatch, tmp_path)
    result = runner.invoke(app, ["config", "get", "context.token_budget"])
    assert result.exit_code == 0
    assert "8000" in result.output


def test_config_export_to_stdout(monkeypatch, tmp_path):
    _home(monkeypatch, tmp_path)
    result = runner.invoke(app, ["config", "export"])
    assert result.exit_code == 0
    assert "provider:" in result.output
    assert "openrouter" in result.output


def test_config_export_import_round_trip(monkeypatch, tmp_path, db, lock):
    _home(monkeypatch, tmp_path, db, lock)
    # Mutate a value, export, reset, then import it back.
    runner.invoke(app, ["config", "set", "runtime.iteration_budget", "55"])
    out = tmp_path / "exported.yaml"
    r_exp = runner.invoke(app, ["config", "export", "-o", str(out)])
    assert r_exp.exit_code == 0
    assert out.is_file()

    runner.invoke(app, ["config", "set", "runtime.iteration_budget", "1"])
    r_imp = runner.invoke(app, ["config", "import", str(out)])
    assert r_imp.exit_code == 0
    assert cfgsvc.load_config(tmp_path / "config.yaml").runtime.iteration_budget == 55


def test_config_import_missing_file_exits_one(monkeypatch, tmp_path):
    _home(monkeypatch, tmp_path)
    result = runner.invoke(app, ["config", "import", str(tmp_path / "nope.yaml")])
    assert result.exit_code == 1
    assert "not found" in result.output


def test_config_import_inline_secret_rejected(monkeypatch, tmp_path):
    _home(monkeypatch, tmp_path)
    bad = tmp_path / "bad.yaml"
    bad.write_text("provider:\n  api_key: sk-leak123\n", encoding="utf-8")
    result = runner.invoke(app, ["config", "import", str(bad)])
    assert result.exit_code == 1
    assert "invalid config" in result.output


def test_setup_writes_config_accepting_defaults(monkeypatch, tmp_path, db, lock):
    _home(monkeypatch, tmp_path, db, lock)
    # Accept every default; decline the DB init prompt (final 'n').
    answers = "\n\n\n\n\n\n\n\nn\n"
    result = runner.invoke(app, ["setup"], input=answers)
    assert result.exit_code == 0, result.output
    assert "setup complete" in result.output
    cfg = cfgsvc.load_config(tmp_path / "config.yaml")
    assert cfg.provider.name == "openrouter"
    assert (tmp_path / "config.yaml").is_file()


def test_config_json_emits_shared_masked_snapshot(monkeypatch, tmp_path, db, lock):
    _home(monkeypatch, tmp_path, db, lock)

    result = runner.invoke(app, ["config", "json"])

    assert result.exit_code == 0
    payload = json.loads(result.output)
    assert payload["schema_version"] == cfgsvc.CONFIG_SCHEMA_VERSION
    assert payload["revision"] == 0
    assert payload["provider"]["name"] == "openrouter"
    assert payload["settings"]
    assert "mock_mode" in payload


def test_config_patch_multi_field_and_stale_conflict(
    monkeypatch,
    tmp_path,
    db,
    lock,
):
    _home(monkeypatch, tmp_path, db, lock)
    changes = json.dumps(
        {
            "provider.model": "patched/model",
            "context.token_budget": 6000,
        },
        separators=(",", ":"),
    )

    success = runner.invoke(
        app,
        [
            "config",
            "patch",
            "--expected-revision",
            "0",
            "--changes-json",
            changes,
        ],
    )
    conflict = runner.invoke(
        app,
        [
            "config",
            "patch",
            "--expected-revision",
            "0",
            "--changes-json",
            '{"provider.model":"stale/model"}',
        ],
    )

    assert success.exit_code == 0, success.output
    assert json.loads(success.output)["revision"] == 1
    assert cfgsvc.load_config().provider.model == "patched/model"
    assert cfgsvc.load_config().context.token_budget == 6000
    assert conflict.exit_code == 2
    error = json.loads(conflict.output)
    assert error["error"]["code"] == "config_revision_conflict"
    assert error["current_revision"] == 1
    assert error["error"]["remediation"]


def test_config_patch_visible_to_subsequent_json_read_without_restart(
    monkeypatch,
    tmp_path,
    db,
    lock,
):
    """Cross-surface conformance (Phase 10.4-05 Task 3): the same control-plane
    contract that the Rust gateway dispatches PATCH/GET against must show a
    patch's new revision/value to a subsequent independent CLI read — proving
    there is no process-global config cache only the CLI process benefits from.
    """
    _home(monkeypatch, tmp_path, db, lock)
    changes = json.dumps({"provider.model": "conformance/model"}, separators=(",", ":"))

    patched = runner.invoke(
        app,
        ["config", "patch", "--expected-revision", "0", "--changes-json", changes],
    )
    assert patched.exit_code == 0, patched.output
    patched_snapshot = json.loads(patched.output)
    assert patched_snapshot["revision"] == 1
    assert patched_snapshot["provider"]["model"] == "conformance/model"

    # A fresh `config json` read (the same call the gateway's GET /v1/config
    # dispatches) must reflect the patch without any restart or extra step.
    read_back = runner.invoke(app, ["config", "json"])
    assert read_back.exit_code == 0, read_back.output
    read_snapshot = json.loads(read_back.output)
    assert read_snapshot["revision"] == 1
    assert read_snapshot["provider"]["model"] == "conformance/model"
    # Same object shape consumed by both surfaces (settings/auth/effective present).
    assert read_snapshot["settings"]
    assert "effective" in read_snapshot


def test_config_patch_stale_second_writer_rejected_not_silently_applied(
    monkeypatch,
    tmp_path,
    db,
    lock,
):
    """A stale second writer must be rejected (409-equivalent exit 2), never
    silently accepted and overwrite the first writer's already-committed change
    — the same invariant the Rust gateway's conformance smoke proves at HTTP level.
    """
    _home(monkeypatch, tmp_path, db, lock)
    first = runner.invoke(
        app,
        [
            "config",
            "patch",
            "--expected-revision",
            "0",
            "--changes-json",
            '{"provider.model":"first-writer"}',
        ],
    )
    assert first.exit_code == 0, first.output
    assert json.loads(first.output)["revision"] == 1

    stale_second = runner.invoke(
        app,
        [
            "config",
            "patch",
            "--expected-revision",
            "0",
            "--changes-json",
            '{"provider.model":"stale-second-writer"}',
        ],
    )
    assert stale_second.exit_code == 2
    error = json.loads(stale_second.output)
    assert error["error"]["code"] == "config_revision_conflict"
    assert error["current_revision"] == 1
    # First writer's value must remain committed and unharmed.
    assert cfgsvc.load_config().provider.model == "first-writer"


def test_setup_preserves_context_permission_modules_and_untouched_sections(
    monkeypatch,
    tmp_path,
    db,
    lock,
):
    _home(monkeypatch, tmp_path, db, lock)
    cfgsvc.patch_config(
        expected_revision=0,
        changes={
            "context.token_budget": 4321,
            "permission.mode": "deny",
            "modules.graph": False,
            "gateway.messaging_port": 9090,
        },
    )
    answers = "\n\n\n\n\n\n\n\nn\n"

    result = runner.invoke(app, ["setup"], input=answers)

    assert result.exit_code == 0, result.output
    config = cfgsvc.load_config()
    assert config.context.token_budget == 4321
    assert config.permission.mode == "deny"
    assert config.modules["graph"] is False
    assert config.gateway.messaging_port == 9090
