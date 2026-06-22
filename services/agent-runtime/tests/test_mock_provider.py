"""Tests for the deterministic mock provider (MockAtlasAgent/mock_factory) and
its wiring into NativeAtlasAgent.execute()'s factory-selection branch.

Test 5 is the single most important assertion in this suite: a configured-but-
wrong api_key (non-empty, invalid) MUST still flow to the real provider path
(_default_factory) — mock mode never masks a credential error (Phase A4
honest-failure contract).
"""
from __future__ import annotations

import sqlite3
import threading
import uuid
import datetime

import pytest

from atlas_runtime.agents.mock import MockAtlasAgent, mock_factory
from atlas_runtime.agents.native import NativeAtlasAgent


def _pending_mission(db: sqlite3.Connection) -> str:
    mid = str(uuid.uuid4())
    now = datetime.datetime.now(datetime.timezone.utc).isoformat()
    db.execute(
        "INSERT INTO missions(id, title, intent, status, project, created_at, updated_at) "
        "VALUES (?, ?, ?, 'pending', '', ?, ?)",
        (mid, "t", "do the thing", now, now),
    )
    db.commit()
    return mid


def _running_run(db: sqlite3.Connection, mission_id: str) -> str:
    rid = str(uuid.uuid4())
    now = datetime.datetime.now(datetime.timezone.utc).isoformat()
    db.execute(
        "INSERT INTO runs(id, mission_id, session_id, status, started_at, finished_at, summary) "
        "VALUES (?, ?, NULL, 'running', ?, NULL, '')",
        (rid, mission_id, now),
    )
    db.commit()
    return rid


# --- Test 1: shape + determinism markers ------------------------------------


def test_mock_agent_run_conversation_shape() -> None:
    result = MockAtlasAgent().run_conversation("hello")
    assert set(result.keys()) == {"final_response", "api_calls", "completed", "failed", "error"}
    assert result["completed"] is True
    assert result["failed"] is False
    assert result["error"] is None
    assert "MOCK MODE" in result["final_response"]


# --- Test 2: determinism (no interpolation/randomization) -------------------


def test_mock_agent_is_deterministic() -> None:
    agent = MockAtlasAgent()
    r1 = agent.run_conversation("first message")
    r2 = agent.run_conversation("a completely different message")
    assert r1["final_response"] == r2["final_response"]


# --- Test 3: mock_factory duck-type construction -----------------------------


def test_mock_factory_returns_runnable_object() -> None:
    obj = mock_factory(session_id="x", model="gpt-4", provider="openai")
    assert hasattr(obj, "run_conversation")
    assert callable(obj.run_conversation)


# --- Test 4: empty api_key routes to mock ------------------------------------


def test_native_execute_routes_to_mock_when_api_key_empty(
    db: sqlite3.Connection, lock: threading.Lock, monkeypatch
) -> None:
    mid = _pending_mission(db)
    rid = _running_run(db, mid)

    monkeypatch.setattr(
        NativeAtlasAgent,
        "_resolve_provider",
        lambda self, conn: ("gpt-4", "openai", None, ""),
    )

    from atlas_runtime.agents import mock as mock_module
    from atlas_runtime.agents import native as native_module

    mock_spy_calls: list[tuple] = []
    default_spy_calls: list[tuple] = []

    real_mock_factory = mock_module.mock_factory
    real_default_factory = native_module._default_factory

    def spy_mock_factory(*args, **kwargs):
        mock_spy_calls.append((args, kwargs))
        return real_mock_factory(*args, **kwargs)

    def spy_default_factory(*args, **kwargs):
        default_spy_calls.append((args, kwargs))
        return real_default_factory(*args, **kwargs)

    monkeypatch.setattr(mock_module, "mock_factory", spy_mock_factory)
    monkeypatch.setattr(native_module, "_default_factory", spy_default_factory)

    agent = NativeAtlasAgent()
    outcome = agent.execute(db, lock, mission_id=mid, run_id=rid, prompt="hello")

    assert mock_spy_calls, "mock_factory was never invoked"
    assert not default_spy_calls, "_default_factory must NOT be invoked when api_key is empty"
    assert outcome.status == "succeeded"


# --- Test 5: THE honest-failure regression guard -----------------------------


def test_native_execute_routes_to_real_provider_when_key_present_but_wrong(
    db: sqlite3.Connection, lock: threading.Lock, monkeypatch
) -> None:
    mid = _pending_mission(db)
    rid = _running_run(db, mid)

    monkeypatch.setattr(
        NativeAtlasAgent,
        "_resolve_provider",
        lambda self, conn: ("gpt-4", "openai", None, "sk-wrong-key-still-present"),
    )

    from atlas_runtime.agents import mock as mock_module
    from atlas_runtime.agents import native as native_module

    mock_spy_calls: list[tuple] = []

    def spy_mock_factory(*args, **kwargs):
        mock_spy_calls.append((args, kwargs))
        raise AssertionError("mock_factory must not be invoked for a non-empty api_key")

    # _default_factory will attempt to build the real foundation AIAgent, which
    # may not be importable/constructible in this test env. We only care that
    # it is the path selected (not mock) — patch it to a benign stand-in so the
    # assertion is purely about routing, not foundation availability.
    default_spy_calls: list[tuple] = []

    class _StubHarness:
        def run_conversation(self, user_message, system_message=None):  # noqa: ANN001
            return {
                "final_response": "stub",
                "api_calls": 0,
                "completed": True,
                "failed": False,
                "error": None,
            }

    def spy_default_factory(*args, **kwargs):
        default_spy_calls.append((args, kwargs))
        return _StubHarness()

    monkeypatch.setattr(mock_module, "mock_factory", spy_mock_factory)
    monkeypatch.setattr(native_module, "_default_factory", spy_default_factory)

    agent = NativeAtlasAgent()
    agent.execute(db, lock, mission_id=mid, run_id=rid, prompt="hello")

    assert not mock_spy_calls, "mock_factory must never be invoked for a configured-but-wrong key"
    assert default_spy_calls, "_default_factory (real provider path) must be invoked"
