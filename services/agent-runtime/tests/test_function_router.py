"""Function-slot routing: curator/auxiliary autoconfig + reasoning effort."""
from __future__ import annotations

import datetime
import sqlite3
import uuid

import pytest
import yaml
from atlas_core.schemas.control_plane import AtlasConfig
from pydantic import ValidationError

from atlas_runtime import codex_auth, function_router
from atlas_runtime.agents import native as native_module

# Captured at import time, before the autouse offline-harness fixture patches
# the module attributes — lets us exercise the real implementations.
_REAL_DEFAULT_FACTORY = native_module._default_factory
_REAL_APPLY_AUTOCONFIG = function_router.apply_autoconfig


def _config(**provider: object) -> AtlasConfig:
    return AtlasConfig.model_validate({"provider": provider})


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


# --- lightest_model_for -------------------------------------------------------


def test_codex_mode_picks_mini_slug_from_discovery(monkeypatch) -> None:
    monkeypatch.setattr(
        codex_auth, "codex_model_ids", lambda: ["gpt-5.5", "gpt-5.4-mini"]
    )
    assert function_router.lightest_model_for("openrouter", "oauth_import", "gpt-5.5") == (
        "openai-codex",
        "gpt-5.4-mini",
    )


def test_codex_mode_falls_back_to_curated_light_model(monkeypatch) -> None:
    monkeypatch.setattr(codex_auth, "codex_model_ids", lambda: [])
    provider, model = function_router.lightest_model_for("x", "oauth_import", "gpt-5.5")
    assert provider == "openai-codex"
    assert "mini" in model


def test_claude_code_and_unknown_providers_are_left_alone() -> None:
    assert function_router.lightest_model_for("anthropic", "claude_code", "m") is None
    assert function_router.lightest_model_for("mystery-inc", "api_key", "m") is None


def test_api_key_and_freellmapi_bindings() -> None:
    assert function_router.lightest_model_for("anthropic", "api_key", "claude-fable-5") == (
        "anthropic",
        "claude-haiku-4-5",
    )
    assert function_router.lightest_model_for("any", "freellmapi", "free-model") == (
        "custom",
        "free-model",
    )


# --- resolve_bindings ---------------------------------------------------------


def test_bindings_cover_curator_and_auxiliary_tasks(monkeypatch) -> None:
    monkeypatch.setattr(codex_auth, "codex_model_ids", lambda: ["gpt-5.4-mini"])
    config = _config(auth_mode="oauth_import", model="gpt-5.5")
    bindings = function_router.resolve_bindings(config)
    assert set(bindings) == {"curator", "compression", "title_generation"}
    for slot in bindings.values():
        assert slot["provider"] == "openai-codex"
        assert slot["model"] == "gpt-5.4-mini"
        assert slot["managed_by"] == "atlas"


def test_judge_is_not_silently_bound_to_light_auxiliary_model() -> None:
    config = AtlasConfig.model_validate(
        {"provider": {"name": "anthropic"}, "functions": {"autoconfig": True}}
    )
    assert "goal_judge" not in function_router.resolve_bindings(config)


def test_explicit_judge_override_gets_its_own_slot() -> None:
    config = AtlasConfig.model_validate(
        {
            "provider": {"name": "anthropic"},
            "functions": {"judge_model": "openai-codex/gpt-5.5"},
        }
    )
    assert function_router.resolve_bindings(config)["goal_judge"] == {
        "provider": "openai-codex",
        "model": "gpt-5.5",
        "managed_by": "atlas",
    }


def test_overrides_beat_autoconfig(monkeypatch) -> None:
    monkeypatch.setattr(codex_auth, "codex_model_ids", lambda: ["gpt-5.4-mini"])
    config = AtlasConfig.model_validate(
        {
            "provider": {"auth_mode": "oauth_import", "model": "gpt-5.5"},
            "functions": {"curator_model": "anthropic/claude-haiku-4-5"},
        }
    )
    bindings = function_router.resolve_bindings(config)
    assert bindings["curator"] == {
        "provider": "anthropic",
        "model": "claude-haiku-4-5",
        "managed_by": "atlas",
    }
    assert bindings["compression"]["provider"] == "openai-codex"


def test_autoconfig_off_without_overrides_yields_nothing() -> None:
    config = AtlasConfig.model_validate(
        {
            "provider": {"auth_mode": "api_key", "name": "anthropic"},
            "functions": {"autoconfig": False},
        }
    )
    assert function_router.resolve_bindings(config) == {}


# --- apply_autoconfig ---------------------------------------------------------


def test_apply_writes_managed_slots_idempotently(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(codex_auth, "codex_model_ids", lambda: ["gpt-5.4-mini"])
    config = _config(auth_mode="oauth_import", model="gpt-5.5")
    path = tmp_path / "config.yaml"
    path.write_text(
        yaml.safe_dump(
            {
                "model": {"provider": "openai-codex", "default": "gpt-5.5"},
                "auxiliary": {
                    "vision": {"provider": "openrouter", "model": "some/vision"},
                    "compression": {
                        "provider": "openrouter",
                        "model": "operator/choice",
                    },
                },
            }
        ),
        encoding="utf-8",
    )

    report = _REAL_APPLY_AUTOCONFIG(config, config_path=path)
    assert report["applied"] is True
    assert report["tasks"]["curator"] == "updated"
    assert report["tasks"]["compression"] == "operator-owned"

    raw = yaml.safe_load(path.read_text(encoding="utf-8"))
    aux = raw["auxiliary"]
    assert aux["curator"]["model"] == "gpt-5.4-mini"
    assert aux["curator"]["managed_by"] == "atlas"
    # Operator-authored slots and unrelated sections survive untouched.
    assert aux["compression"]["model"] == "operator/choice"
    assert aux["vision"]["model"] == "some/vision"
    assert raw["model"]["default"] == "gpt-5.5"

    second = _REAL_APPLY_AUTOCONFIG(config, config_path=path)
    assert second["applied"] is True
    assert second["tasks"]["curator"] == "current"


def test_apply_adopts_unstamped_slot_matching_desired_binding(
    tmp_path, monkeypatch
) -> None:
    monkeypatch.setattr(codex_auth, "codex_model_ids", lambda: ["gpt-5.4-mini"])
    config = _config(auth_mode="oauth_import", model="gpt-5.5")
    path = tmp_path / "config.yaml"
    path.write_text(
        yaml.safe_dump(
            {
                "auxiliary": {
                    # Already holds exactly what autoconfig would write, but
                    # without the atlas stamp — gets adopted, not skipped.
                    "curator": {
                        "provider": "openai-codex",
                        "model": "gpt-5.4-mini",
                        "timeout": 600,
                    },
                },
            }
        ),
        encoding="utf-8",
    )

    report = _REAL_APPLY_AUTOCONFIG(config, config_path=path)
    assert report["applied"] is True
    assert report["tasks"]["curator"] == "updated"

    aux = yaml.safe_load(path.read_text(encoding="utf-8"))["auxiliary"]
    assert aux["curator"]["managed_by"] == "atlas"
    # Adjacent slot keys (timeouts etc.) survive the merge.
    assert aux["curator"]["timeout"] == 600


def test_apply_retargets_previously_managed_slots(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(codex_auth, "codex_model_ids", lambda: ["gpt-5.4-mini"])
    path = tmp_path / "config.yaml"
    path.write_text(
        yaml.safe_dump(
            {
                "auxiliary": {
                    "curator": {
                        "provider": "openai-codex",
                        "model": "gpt-5.4-mini",
                        "managed_by": "atlas",
                    }
                }
            }
        ),
        encoding="utf-8",
    )
    config = _config(auth_mode="api_key", name="anthropic", model="claude-fable-5")
    report = _REAL_APPLY_AUTOCONFIG(config, config_path=path)
    assert report["tasks"]["curator"] == "updated"
    raw = yaml.safe_load(path.read_text(encoding="utf-8"))
    assert raw["auxiliary"]["curator"]["model"] == "claude-haiku-4-5"


def test_apply_never_raises_on_broken_store(tmp_path) -> None:
    config = _config(auth_mode="api_key", name="anthropic")
    path = tmp_path / "nested" / "config.yaml"
    report = _REAL_APPLY_AUTOCONFIG(config, config_path=path)
    assert report["applied"] is True
    assert path.exists()


# --- reasoning effort ---------------------------------------------------------


def test_reasoning_effort_schema_validation() -> None:
    assert _config(reasoning_effort="high").provider.reasoning_effort == "high"
    with pytest.raises(ValidationError):
        _config(reasoning_effort="turbo")


def test_default_factory_threads_reasoning_config(monkeypatch) -> None:
    captured: dict[str, object] = {}

    class _FakeAgent:
        def __init__(self, **kwargs: object) -> None:
            captured.update(kwargs)

    import sys
    import types

    fake = types.ModuleType("run_agent")
    fake.AIAgent = _FakeAgent
    monkeypatch.setitem(sys.modules, "run_agent", fake)

    _REAL_DEFAULT_FACTORY(
        "session-1", 5, model="m", provider="anthropic", reasoning_effort="low"
    )
    assert captured["reasoning_config"] == {"effort": "low"}

    captured.clear()
    _REAL_DEFAULT_FACTORY("session-2", 5, model="m", provider="anthropic")
    assert "reasoning_config" not in captured


def test_default_factory_threads_subagent_progress_callback(monkeypatch) -> None:
    captured: dict[str, object] = {}

    class _FakeAgent:
        def __init__(self, **kwargs: object) -> None:
            captured.update(kwargs)

    import sys
    import types

    fake = types.ModuleType("run_agent")
    fake.AIAgent = _FakeAgent
    monkeypatch.setitem(sys.modules, "run_agent", fake)
    callback = lambda *_args, **_kwargs: None

    _REAL_DEFAULT_FACTORY("session-actor", 5, tool_progress_callback=callback)

    assert captured["tool_progress_callback"] is callback


def test_execute_passes_effort_and_syncs_functions(db, lock, monkeypatch) -> None:
    from atlas_runtime import function_router as router_module
    from atlas_runtime.agents.native import NativeAtlasAgent

    monkeypatch.setattr(
        NativeAtlasAgent,
        "_resolve_provider",
        lambda self, conn, run_id=None: ("m", "anthropic", None, "key", "api_key"),
    )
    monkeypatch.setattr(native_module, "_resolve_reasoning_effort", lambda: "high")
    sync_calls: list[bool] = []
    monkeypatch.setattr(
        router_module,
        "apply_autoconfig",
        lambda *a, **k: sync_calls.append(True) or {"applied": True, "tasks": {}},
    )
    factory_kwargs: dict[str, object] = {}

    def _capture(session_id, max_iterations, **kwargs):
        factory_kwargs.update(kwargs)

        class _Done:
            def run_conversation(self, prompt, system_message=None):  # noqa: ANN001
                return {
                    "final_response": "ok",
                    "api_calls": 1,
                    "completed": True,
                    "failed": False,
                    "error": None,
                }

        return _Done()

    monkeypatch.setattr(native_module, "_default_factory", _capture)

    mid = _pending_mission(db)
    rid = _running_run(db, mid)
    outcome = NativeAtlasAgent().execute(db, lock, mission_id=mid, run_id=rid, prompt="go")
    assert outcome.status == "succeeded"
    assert factory_kwargs["reasoning_effort"] == "high"
    assert sync_calls, "function autoconfig was not applied at the run boundary"


def test_active_status_surfaces_effort_and_privacy(monkeypatch, tmp_path) -> None:
    monkeypatch.setenv("ATLAS_HOME", str(tmp_path))
    (tmp_path / "config.yaml").write_text(
        "provider:\n"
        "  auth_mode: freellmapi\n"
        "  base_url: https://free.example/v1\n"
        "  reasoning_effort: low\n",
        encoding="utf-8",
    )
    from atlas_runtime import provider_service

    status = provider_service.active_status()
    assert status["reasoning_effort"] == "low"
    assert status["privacy_warning"]
    assert status["mock_mode"] is False
