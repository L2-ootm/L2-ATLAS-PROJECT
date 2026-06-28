"""Provider-mesh service + `atlas provider` / `atlas version` CLI."""
from __future__ import annotations

import json
from pathlib import Path

import pytest
from typer.testing import CliRunner

from atlas_runtime import provider_service
from atlas_runtime.cli.main import app

runner = CliRunner()


# --- provider_service.active_status ----------------------------------------


def test_active_status_mock_when_no_key(monkeypatch, tmp_path: Path):
    monkeypatch.setenv("ATLAS_HOME", str(tmp_path))  # defaults, no api_key
    info = provider_service.active_status()
    assert info["auth_mode"] == "api_key"
    assert info["mock_mode"] is True
    assert info["credentials_present"] is False
    assert info["remediation"]


def test_active_status_live_with_env_key(monkeypatch, tmp_path: Path):
    monkeypatch.setenv("ATLAS_HOME", str(tmp_path))
    monkeypatch.setenv("PROBE_KEY", "sk-real")
    (tmp_path / "config.yaml").write_text(
        "provider:\n  api_key: env:PROBE_KEY\n", encoding="utf-8"
    )
    info = provider_service.active_status()
    assert info["credentials_present"] is True
    assert info["mock_mode"] is False
    assert info["remediation"] is None


def test_active_status_freellmapi_is_live_without_key(monkeypatch, tmp_path: Path):
    monkeypatch.setenv("ATLAS_HOME", str(tmp_path))
    (tmp_path / "config.yaml").write_text(
        "provider:\n  auth_mode: freellmapi\n  base_url: https://free.example/v1\n",
        encoding="utf-8",
    )
    info = provider_service.active_status()
    assert info["auth_mode"] == "freellmapi"
    assert info["mock_mode"] is False  # keyless endpoint still calls a real provider


# --- provider_service.modes_status -----------------------------------------


def test_modes_status_covers_all_four_with_active_flag(monkeypatch, tmp_path: Path):
    monkeypatch.setenv("ATLAS_HOME", str(tmp_path))
    monkeypatch.setenv("CODEX_HOME", str(tmp_path / "no-codex"))
    board = provider_service.modes_status()
    modes = {m["mode"] for m in board}
    assert modes == {"api_key", "oauth_import", "claude_code", "freellmapi"}
    active = [m["mode"] for m in board if m["active"]]
    assert active == ["api_key"]  # default
    for m in board:
        assert set(m) >= {"mode", "label", "active", "available", "detail", "remediation"}


# --- CLI -------------------------------------------------------------------


def test_provider_status_json(monkeypatch, tmp_path: Path):
    monkeypatch.setenv("ATLAS_HOME", str(tmp_path))
    result = runner.invoke(app, ["provider", "status", "--json"])
    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    assert payload["auth_mode"] == "api_key"
    assert payload["mock_mode"] is True


def test_provider_modes_human_readable(monkeypatch, tmp_path: Path):
    monkeypatch.setenv("ATLAS_HOME", str(tmp_path))
    monkeypatch.setenv("CODEX_HOME", str(tmp_path / "no-codex"))
    result = runner.invoke(app, ["provider", "modes"])
    assert result.exit_code == 0, result.output
    assert "oauth_import" in result.output
    assert "freellmapi" in result.output


def test_provider_test_exits_nonzero_in_mock_mode(monkeypatch, tmp_path: Path):
    monkeypatch.setenv("ATLAS_HOME", str(tmp_path))
    result = runner.invoke(app, ["provider", "test", "--json"])
    assert result.exit_code == 1
    assert json.loads(result.output)["ready"] is False


def test_version_json(monkeypatch):
    result = runner.invoke(app, ["version", "--json"])
    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    assert payload["name"] == "atlas"
    assert payload["version"]


def test_help_lists_provider_group(monkeypatch):
    result = runner.invoke(app, ["--help"])
    assert result.exit_code == 0
    assert "provider" in result.output


def test_provider_output_is_ascii_safe_for_windows_consoles(monkeypatch, tmp_path: Path):
    """Default human output must encode on Windows cp1252 / non-UTF terminals
    (no Unicode glyphs) — a real bug a UTF-capturing CliRunner would otherwise hide."""
    monkeypatch.setenv("ATLAS_HOME", str(tmp_path))
    monkeypatch.setenv("CODEX_HOME", str(tmp_path / "no-codex"))
    for argv in (["provider", "modes"], ["provider", "status"], ["version"]):
        out = runner.invoke(app, argv).output
        out.encode("ascii")  # pure ASCII — raises if any non-ASCII glyph slips in
