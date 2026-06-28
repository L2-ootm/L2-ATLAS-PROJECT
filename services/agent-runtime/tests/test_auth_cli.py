"""Secret-safe local auth CLI with metadata-only audit."""
from __future__ import annotations

import json
import threading
from pathlib import Path

import pytest
from typer.testing import CliRunner

from atlas_runtime import auth_service
from atlas_runtime.cli import auth as cli_auth
from atlas_runtime.cli.main import app

runner = CliRunner()


def _wire(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    db,
    lock: threading.Lock,
) -> None:
    monkeypatch.setenv("ATLAS_HOME", str(tmp_path))
    monkeypatch.setattr(cli_auth, "_get_connection", lambda: db)
    monkeypatch.setattr(cli_auth, "_get_lock", lambda: lock)


def test_auth_add_uses_hidden_input_and_emits_secret_free_audit(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    db,
    lock: threading.Lock,
) -> None:
    _wire(monkeypatch, tmp_path, db, lock)
    secret = "sk-cli-secret-9876"

    result = runner.invoke(app, ["auth", "add", "openrouter"], input=f"{secret}\n")

    assert result.exit_code == 0, result.output
    assert secret not in result.output
    assert auth_service.resolve_secret("openrouter") == secret
    rows = db.execute(
        "SELECT event_type, data FROM audit_events WHERE event_type='auth_change'"
    ).fetchall()
    assert len(rows) == 1
    assert secret not in rows[0][1]
    assert json.loads(rows[0][1])["action"] == "add"
    assert json.loads(rows[0][1])["provider"] == "openrouter"


def test_auth_help_exposes_no_secret_argv_option() -> None:
    result = runner.invoke(app, ["auth", "add", "--help"])

    assert result.exit_code == 0
    assert "--api-key" not in result.output
    assert "--secret" not in result.output


def test_auth_add_stdin_reads_secret_without_prompt_or_argv(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    db,
    lock: threading.Lock,
) -> None:
    _wire(monkeypatch, tmp_path, db, lock)
    secret = "stdin-only-secret-9876"

    result = runner.invoke(
        app,
        ["auth", "add", "openrouter", "--stdin", "--source", "gateway"],
        input=secret + "\n",
    )

    assert result.exit_code == 0, result.output
    assert "API key" not in result.output
    assert secret not in result.output
    assert auth_service.resolve_secret("openrouter") == secret
    data = json.loads(
        db.execute(
            "SELECT data FROM audit_events WHERE event_type='auth_change'"
        ).fetchone()[0]
    )
    assert data["source"] == "gateway"


def test_auth_json_status_and_doctor_are_masked(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    db,
    lock: threading.Lock,
) -> None:
    _wire(monkeypatch, tmp_path, db, lock)
    secret = "private-value-4444"
    auth_service.set_api_key("openrouter", secret)

    for command in (
        ["auth", "list"],
        ["auth", "status", "openrouter"],
        ["auth", "json"],
        ["auth", "doctor", "openrouter"],
    ):
        result = runner.invoke(app, command)
        assert result.exit_code == 0, (command, result.output)
        assert secret not in result.output
        assert "…4444" in result.output


def test_auth_remove_is_explicit_idempotent_and_audited_once(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    db,
    lock: threading.Lock,
) -> None:
    _wire(monkeypatch, tmp_path, db, lock)
    auth_service.set_api_key("openrouter", "secret-1234")

    first = runner.invoke(app, ["auth", "remove", "openrouter"])
    second = runner.invoke(app, ["auth", "remove", "openrouter"])

    assert first.exit_code == 0
    assert "removed" in first.output
    assert second.exit_code == 0
    assert "already absent" in second.output
    actions = [
        json.loads(row[0])["action"]
        for row in db.execute(
            "SELECT data FROM audit_events WHERE event_type='auth_change'"
        )
    ]
    assert actions == ["remove"]


def test_auth_errors_include_code_and_remediation(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    db,
    lock: threading.Lock,
) -> None:
    _wire(monkeypatch, tmp_path, db, lock)
    (tmp_path / "auth.json").write_text("{bad", encoding="utf-8")

    result = runner.invoke(app, ["auth", "json"])

    assert result.exit_code == 1
    assert "auth_corrupt" in result.output
    assert "remediation" in result.output
