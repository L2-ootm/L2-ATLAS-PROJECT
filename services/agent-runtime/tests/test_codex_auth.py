"""P2: Codex (ChatGPT OAuth) credential adapter — delegates to the foundation.

The foundation owns the real OAuth lifecycle (import from ~/.codex, refresh in
~/.hermes). These tests verify the ATLAS boundary: secret-free CLI status, the
import delegation, runtime credential resolution, and that native execute()
routes auth_mode="oauth_import" through the Codex resolver. The foundation is
injected (set_foundation_loader) so no real tokens or network are touched.
"""
from __future__ import annotations

import base64
import datetime
import json
import sqlite3
import threading
import time
import uuid

import pytest

from atlas_runtime import codex_auth
from atlas_runtime.agents import native
from atlas_runtime.agents.native import NativeAtlasAgent

_OK = {
    "final_response": "ok", "api_calls": 1, "completed": True,
    "failed": False, "error": None,
}


def _jwt(exp: int, email: str = "op@example.com") -> str:
    def seg(d: dict) -> str:
        return base64.urlsafe_b64encode(json.dumps(d).encode()).decode().rstrip("=")
    return f"{seg({'alg':'RS256'})}.{seg({'exp': exp, 'email': email})}.sig"


class _FakeFoundationAuth:
    """Stands in for foundation hermes_cli.auth."""

    def __init__(self, *, import_tokens=None, resolved=None):
        self._import_tokens = import_tokens
        self._resolved = resolved or {}
        self.saved = None

    def _import_codex_cli_tokens(self):
        return self._import_tokens

    def _save_codex_tokens(self, tokens):
        self.saved = tokens

    def resolve_codex_runtime_credentials(self, *, force_refresh=False):
        return self._resolved


@pytest.fixture(autouse=True)
def _reset_loader():
    yield
    codex_auth.set_foundation_loader(None)


# --- cli_status (secret-free read of ~/.codex) -----------------------------


def test_cli_status_absent(monkeypatch, tmp_path):
    monkeypatch.setenv("CODEX_HOME", str(tmp_path))  # empty dir → no auth.json
    assert codex_auth.cli_status() == {"present": False, "reason": "no_codex_login"}


def test_cli_status_reports_expiry_without_leaking_tokens(monkeypatch, tmp_path):
    monkeypatch.setenv("CODEX_HOME", str(tmp_path))
    future = int(time.time()) + 3600
    (tmp_path / "auth.json").write_text(json.dumps({
        "auth_mode": "chatgpt",
        "tokens": {
            "access_token": _jwt(future),
            "id_token": _jwt(future, email="op@example.com"),
            "refresh_token": "rt-secret",
        },
    }), encoding="utf-8")
    st = codex_auth.cli_status()
    assert st["present"] and st["readable"]
    assert st["auth_mode"] == "chatgpt"
    assert st["email"] == "op@example.com"
    assert st["has_access_token"] and st["has_refresh_token"]
    assert st["access_token_expired"] is False
    # no raw token bytes anywhere in the status payload
    assert "rt-secret" not in json.dumps(st)


def test_cli_status_marks_expired(monkeypatch, tmp_path):
    monkeypatch.setenv("CODEX_HOME", str(tmp_path))
    past = int(time.time()) - 10
    (tmp_path / "auth.json").write_text(json.dumps({
        "auth_mode": "chatgpt",
        "tokens": {"access_token": _jwt(past), "refresh_token": "x"},
    }), encoding="utf-8")
    assert codex_auth.cli_status()["access_token_expired"] is True


# --- import delegation ------------------------------------------------------


def test_import_no_valid_tokens(monkeypatch):
    fake = _FakeFoundationAuth(import_tokens=None)
    codex_auth.set_foundation_loader(lambda: fake)
    assert codex_auth.import_from_codex_cli() == {
        "imported": False, "reason": "no_valid_codex_tokens"
    }
    assert fake.saved is None


def test_import_saves_into_foundation_store(monkeypatch):
    fake = _FakeFoundationAuth(import_tokens={"access_token": "at", "refresh_token": "rt"})
    codex_auth.set_foundation_loader(lambda: fake)
    assert codex_auth.import_from_codex_cli() == {"imported": True}
    assert fake.saved == {"access_token": "at", "refresh_token": "rt"}


# --- runtime resolution -----------------------------------------------------


def test_resolve_credentials_delegates(monkeypatch):
    fake = _FakeFoundationAuth(resolved={
        "provider": "openai-codex",
        "base_url": "https://chatgpt.com/backend-api/codex",
        "api_key": "live-access-token",
    })
    codex_auth.set_foundation_loader(lambda: fake)
    creds = codex_auth.resolve_codex_credentials()
    assert creds == {
        "provider": "openai-codex",
        "base_url": "https://chatgpt.com/backend-api/codex",
        "api_key": "live-access-token",
    }


# --- native execute routes oauth_import through Codex -----------------------


def _insert_mission_run(db: sqlite3.Connection) -> tuple[str, str]:
    mid, rid = str(uuid.uuid4()), str(uuid.uuid4())
    now = datetime.datetime.now(datetime.timezone.utc).isoformat()
    db.execute(
        "INSERT INTO missions(id,title,intent,status,project,created_at,updated_at) "
        "VALUES (?,?,?,?,?,?,?)", (mid, "t", "do x", "pending", "", now, now),
    )
    db.execute(
        "INSERT INTO runs(id,mission_id,session_id,status,started_at,finished_at,summary) "
        "VALUES (?,?,?,?,?,?,?)", (rid, mid, None, "running", now, None, ""),
    )
    db.commit()
    return mid, rid


class _Capture:
    def __init__(self) -> None:
        self.kw: dict = {}

    def __call__(self, session_id: str, max_iterations: int, **kw):  # noqa: ANN003
        self.kw = kw

        class _H:
            def run_conversation(self, *a, **k):  # noqa: ANN002, ANN003
                return _OK

        return _H()


# --- owned_status (secret-free read of the foundation store) ---------------


def test_owned_status_absent_when_foundation_raises():
    class _Raising:
        def _read_codex_tokens(self):
            raise RuntimeError("No Codex credentials stored.")

    codex_auth.set_foundation_loader(lambda: _Raising())
    st = codex_auth.owned_status()
    assert st["present"] is False


def test_owned_status_present_without_leaking_tokens():
    future = int(time.time()) + 3600

    class _Store:
        def _read_codex_tokens(self):
            return {"tokens": {
                "access_token": _jwt(future), "refresh_token": "rt-secret",
            }}

    codex_auth.set_foundation_loader(lambda: _Store())
    st = codex_auth.owned_status()
    assert st["present"] is True
    assert st["has_refresh_token"] is True
    assert st["access_token_expired"] is False
    assert "rt-secret" not in json.dumps(st)


def test_owned_status_expired_access_token_still_present():
    past = int(time.time()) - 10

    class _Store:
        def _read_codex_tokens(self):
            return {"tokens": {"access_token": _jwt(past), "refresh_token": "rt"}}

    codex_auth.set_foundation_loader(lambda: _Store())
    st = codex_auth.owned_status()
    assert st["present"] is True
    assert st["access_token_expired"] is True
    assert st["has_refresh_token"] is True  # foundation can refresh at run time


# --- oauth_import model compatibility ---------------------------------------


def test_native_oauth_import_swaps_incompatible_model_to_codex_default(
    db, lock, monkeypatch, tmp_path
):
    monkeypatch.setenv("ATLAS_HOME", str(tmp_path))
    (tmp_path / "config.yaml").write_text(
        "provider:\n  auth_mode: oauth_import\n  model: anthropic/claude-sonnet-4\n",
        encoding="utf-8",
    )
    cap = _Capture()
    monkeypatch.setattr(native, "_default_factory", cap)
    monkeypatch.setattr(
        codex_auth, "resolve_codex_credentials",
        lambda **_: {
            "provider": "openai-codex",
            "base_url": "https://chatgpt.com/backend-api/codex",
            "api_key": "codex-access-token",
        },
    )
    monkeypatch.setattr(codex_auth, "codex_model_ids", lambda: ["gpt-5.5", "gpt-5.4"])
    mid, rid = _insert_mission_run(db)
    outcome = NativeAtlasAgent().execute(db, lock, mission_id=mid, run_id=rid, prompt="go")
    assert outcome.status == "succeeded"
    assert cap.kw["model"] == "gpt-5.5"


def test_native_oauth_import_keeps_codex_capable_model(db, lock, monkeypatch, tmp_path):
    """A gpt-* id newer than the offline list must survive (no silent downgrade)."""
    monkeypatch.setenv("ATLAS_HOME", str(tmp_path))
    (tmp_path / "config.yaml").write_text(
        "provider:\n  auth_mode: oauth_import\n  model: gpt-6-codex\n",
        encoding="utf-8",
    )
    cap = _Capture()
    monkeypatch.setattr(native, "_default_factory", cap)
    monkeypatch.setattr(
        codex_auth, "resolve_codex_credentials",
        lambda **_: {
            "provider": "openai-codex",
            "base_url": "https://chatgpt.com/backend-api/codex",
            "api_key": "codex-access-token",
        },
    )
    monkeypatch.setattr(codex_auth, "codex_model_ids", lambda: ["gpt-5.5"])
    mid, rid = _insert_mission_run(db)
    outcome = NativeAtlasAgent().execute(db, lock, mission_id=mid, run_id=rid, prompt="go")
    assert outcome.status == "succeeded"
    assert cap.kw["model"] == "gpt-6-codex"


def test_native_oauth_import_routes_through_codex(db, lock, monkeypatch, tmp_path):
    monkeypatch.setenv("ATLAS_HOME", str(tmp_path))
    (tmp_path / "config.yaml").write_text(
        "provider:\n  auth_mode: oauth_import\n", encoding="utf-8"
    )
    cap = _Capture()
    monkeypatch.setattr(native, "_default_factory", cap)
    monkeypatch.setattr(
        codex_auth, "resolve_codex_credentials",
        lambda **_: {
            "provider": "openai-codex",
            "base_url": "https://chatgpt.com/backend-api/codex",
            "api_key": "codex-access-token",
        },
    )
    mid, rid = _insert_mission_run(db)
    outcome = NativeAtlasAgent().execute(db, lock, mission_id=mid, run_id=rid, prompt="go")
    assert outcome.status == "succeeded"
    assert cap.kw["provider"] == "openai-codex"
    assert cap.kw["base_url"] == "https://chatgpt.com/backend-api/codex"
    assert cap.kw["api_key"] == "codex-access-token"
