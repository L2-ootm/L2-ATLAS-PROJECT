"""A4: native-agent provider/model routing — config default + Focus override.

Covers the resolver (config_service.resolve_provider) and the NativeAtlasAgent
execute() path that feeds the resolved model/provider into the harness factory.
"""
from __future__ import annotations

import datetime
import sqlite3
import threading
import uuid

from atlas_runtime import config_service
from atlas_runtime.agents import native
from atlas_runtime.agents.native import NativeAtlasAgent

_OK = {
    "final_response": "ok",
    "api_calls": 1,
    "completed": True,
    "failed": False,
    "error": None,
}


def _insert_mission_run(db: sqlite3.Connection) -> tuple[str, str]:
    mid, rid = str(uuid.uuid4()), str(uuid.uuid4())
    now = datetime.datetime.now(datetime.timezone.utc).isoformat()
    db.execute(
        "INSERT INTO missions(id,title,intent,status,project,created_at,updated_at) "
        "VALUES (?,?,?,?,?,?,?)",
        (mid, "t", "do x", "pending", "", now, now),
    )
    db.execute(
        "INSERT INTO runs(id,mission_id,session_id,status,started_at,finished_at,summary) "
        "VALUES (?,?,?,?,?,?,?)",
        (rid, mid, None, "running", now, None, ""),
    )
    db.commit()
    return mid, rid


def _insert_focus(db: sqlite3.Connection, framework: str) -> None:
    now = datetime.datetime.now(datetime.timezone.utc).isoformat()
    db.execute(
        "INSERT INTO focus(id,title,framework,priorities,drivers,project_id,status,created_at,updated_at) "
        "VALUES (?,?,?,?,?,?,?,?,?)",
        (str(uuid.uuid4()), "Focus", framework, "[]", "[]", None, "active", now, now),
    )
    db.commit()


class _Capture:
    """Stands in for _default_factory; records the kwargs it was called with."""

    def __init__(self) -> None:
        self.kw: dict = {}

    def __call__(self, session_id: str, max_iterations: int, **kw):  # noqa: ANN003
        self.kw = kw

        class _H:
            def run_conversation(self, *a, **k):  # noqa: ANN002, ANN003
                return _OK

        return _H()


# --- resolve_provider ------------------------------------------------------


def test_resolve_provider_config_default(monkeypatch, tmp_path):
    monkeypatch.setenv("ATLAS_HOME", str(tmp_path))  # no config file → defaults
    r = config_service.resolve_provider()
    assert r["provider"] == "openrouter"
    assert r["model"] == "anthropic/claude-sonnet-4"


def test_resolve_provider_focus_overrides_model(monkeypatch, tmp_path):
    monkeypatch.setenv("ATLAS_HOME", str(tmp_path))
    r = config_service.resolve_provider(focus_framework="anthropic/claude-opus-4")
    assert r["model"] == "anthropic/claude-opus-4"
    assert r["provider"] == "openrouter"  # provider still from config


def test_resolve_provider_blank_focus_keeps_config_model(monkeypatch, tmp_path):
    monkeypatch.setenv("ATLAS_HOME", str(tmp_path))
    r = config_service.resolve_provider(focus_framework="   ")
    assert r["model"] == "anthropic/claude-sonnet-4"


def test_resolve_provider_derefs_env_api_key(monkeypatch):
    monkeypatch.setenv("MY_KEY", "secret-123")
    cfg = config_service.AtlasConfig(
        provider=config_service.ProviderConfig(api_key="env:MY_KEY")
    )
    assert config_service.resolve_provider(cfg)["api_key"] == "secret-123"


def test_resolve_provider_blank_when_env_unset(monkeypatch):
    monkeypatch.delenv("MY_KEY", raising=False)
    cfg = config_service.AtlasConfig(
        provider=config_service.ProviderConfig(api_key="env:MY_KEY")
    )
    assert config_service.resolve_provider(cfg)["api_key"] == ""


# --- native execute resolution ---------------------------------------------


def _configure_fake_api_key(monkeypatch, tmp_path) -> None:
    """These tests exercise model/provider resolution and must route through
    _default_factory (the real-provider path), not the mock-mode branch
    (10.0.2-02) — so a non-empty api_key must be configured via env:VAR
    indirection, mirroring how an operator would configure a real key."""
    monkeypatch.setenv("FAKE_PROVIDER_KEY", "sk-test-key-not-real")
    config_path = tmp_path / "config.yaml"
    config_path.write_text(
        "provider:\n  api_key: env:FAKE_PROVIDER_KEY\n", encoding="utf-8",
    )


def test_native_execute_uses_config_model(db, lock, monkeypatch, tmp_path):
    monkeypatch.setenv("ATLAS_HOME", str(tmp_path))
    _configure_fake_api_key(monkeypatch, tmp_path)
    cap = _Capture()
    monkeypatch.setattr(native, "_default_factory", cap)
    mid, rid = _insert_mission_run(db)
    outcome = NativeAtlasAgent().execute(db, lock, mission_id=mid, run_id=rid, prompt="go")
    assert outcome.status == "succeeded"
    assert cap.kw["model"] == "anthropic/claude-sonnet-4"
    assert cap.kw["provider"] == "openrouter"


def test_native_execute_focus_overrides_model(db, lock, monkeypatch, tmp_path):
    monkeypatch.setenv("ATLAS_HOME", str(tmp_path))
    _configure_fake_api_key(monkeypatch, tmp_path)
    _insert_focus(db, framework="anthropic/claude-opus-4")
    cap = _Capture()
    monkeypatch.setattr(native, "_default_factory", cap)
    mid, rid = _insert_mission_run(db)
    outcome = NativeAtlasAgent().execute(db, lock, mission_id=mid, run_id=rid, prompt="go")
    assert outcome.status == "succeeded"
    assert cap.kw["model"] == "anthropic/claude-opus-4"


def test_native_explicit_model_beats_config(db, lock, monkeypatch, tmp_path):
    monkeypatch.setenv("ATLAS_HOME", str(tmp_path))
    _configure_fake_api_key(monkeypatch, tmp_path)
    _insert_focus(db, framework="anthropic/claude-opus-4")
    cap = _Capture()
    monkeypatch.setattr(native, "_default_factory", cap)
    mid, rid = _insert_mission_run(db)
    agent = NativeAtlasAgent(model="explicit/model", provider="explicit")
    outcome = agent.execute(db, lock, mission_id=mid, run_id=rid, prompt="go")
    assert outcome.status == "succeeded"
    assert cap.kw["model"] == "explicit/model"
    assert cap.kw["provider"] == "explicit"


# --- P1: multi-mode auth (auth_mode) ---------------------------------------
# A provider profile carries an explicit auth mode so the operator can wire
# models every way (api_key / oauth_import / claude_code / freellmapi). P1 adds
# the field, keeps full back-compat (default api_key), and surfaces it through
# resolve_provider; the per-mode credential resolution lands in P2/P3.

import pytest
from pydantic import ValidationError


def test_provider_config_default_auth_mode_is_api_key():
    assert config_service.ProviderConfig().auth_mode == "api_key"


@pytest.mark.parametrize(
    "mode", ["api_key", "oauth_import", "claude_code", "freellmapi"]
)
def test_provider_config_accepts_known_auth_modes(mode):
    assert config_service.ProviderConfig(auth_mode=mode).auth_mode == mode


def test_provider_config_rejects_unknown_auth_mode():
    with pytest.raises(ValidationError):
        config_service.ProviderConfig(auth_mode="totally-bogus")


def test_legacy_config_without_auth_mode_loads_as_api_key(monkeypatch, tmp_path):
    """A pre-P1 config.yaml (no auth_mode key) must still validate, defaulting
    to api_key — extra='forbid' models adopt new fields via their default."""
    monkeypatch.setenv("ATLAS_HOME", str(tmp_path))
    (tmp_path / "config.yaml").write_text(
        "provider:\n  name: openrouter\n", encoding="utf-8"
    )
    cfg = config_service.load_config()
    assert cfg.provider.auth_mode == "api_key"


def test_resolve_provider_surfaces_auth_mode(monkeypatch, tmp_path):
    monkeypatch.setenv("ATLAS_HOME", str(tmp_path))
    (tmp_path / "config.yaml").write_text(
        "provider:\n  auth_mode: freellmapi\n  base_url: https://free.example/v1\n",
        encoding="utf-8",
    )
    r = config_service.resolve_provider()
    assert r["auth_mode"] == "freellmapi"
