"""Configured/effective provider-model status projection tests."""
from __future__ import annotations

import json
import threading
from pathlib import Path

import pytest
from atlas_core.schemas.agent_contract import ModelIdentity

from atlas_runtime import (
    audit_service,
    auth_service,
    config_service,
    mission_service,
    model_registry,
)


def _register(
    db,
    lock: threading.Lock,
    *,
    provider: str,
    model: str,
    source: str = "test",
) -> None:
    model_registry.refresh(
        db,
        lock,
        source=source,
        fetcher=lambda: [{"id": model, "owned_by": provider}],
        auth_status_resolver=lambda _: "auth_present",
    )


def test_status_reports_configured_and_focus_or_session_effective_source(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    db,
    lock: threading.Lock,
) -> None:
    from atlas_runtime import model_control_service

    monkeypatch.setenv("ATLAS_HOME", str(tmp_path))
    auth_service.set_api_key("openrouter", "secret-1234")
    _register(db, lock, provider="openrouter", model="configured/model")
    _register(db, lock, provider="openrouter", model="focus/model", source="focus")
    config = config_service.AtlasConfig.model_validate(
        {"provider": {"name": "openrouter", "model": "configured/model"}}
    )

    configured = model_control_service.get_provider_model_status(db, config)
    focused = model_control_service.get_provider_model_status(
        db,
        config,
        focus_framework="focus/model",
    )
    session = model_control_service.get_provider_model_status(
        db,
        config,
        focus_framework="focus/model",
        session_model=ModelIdentity(
            provider="session-provider",
            model_id="session/model",
        ),
    )

    assert configured.configured_provider == "openrouter"
    assert configured.configured_model == "configured/model"
    assert configured.effective_model == "configured/model"
    assert configured.source == "config"
    assert focused.effective_model == "focus/model"
    assert focused.source == "focus"
    assert session.effective_provider == "session-provider"
    assert session.effective_model == "session/model"
    assert session.source == "session"


def test_status_joins_env_auth_presence_without_returning_value(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    db,
) -> None:
    from atlas_runtime import model_control_service

    monkeypatch.setenv("ATLAS_HOME", str(tmp_path))
    monkeypatch.setenv("MODEL_STATUS_KEY", "resolved-secret-value")
    config = config_service.AtlasConfig.model_validate(
        {
            "provider": {
                "name": "openrouter",
                "model": "missing/model",
                "api_key": "env:MODEL_STATUS_KEY",
            }
        }
    )

    status = model_control_service.get_provider_model_status(db, config)

    assert status.auth_status == "auth_present"
    assert "resolved-secret-value" not in json.dumps(status.model_dump())


def test_unavailable_configured_model_has_honest_health_and_remediation(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    db,
) -> None:
    from atlas_runtime import model_control_service

    monkeypatch.setenv("ATLAS_HOME", str(tmp_path))
    config = config_service.AtlasConfig.model_validate(
        {"provider": {"name": "openrouter", "model": "not/registered"}}
    )

    status = model_control_service.get_provider_model_status(db, config)

    assert status.model_health == "unknown"
    assert "not/registered" in (status.remediation or "")
    assert "refresh" in (status.remediation or "")


def test_fallback_status_reflects_recorded_event_only(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    db,
    lock: threading.Lock,
) -> None:
    from atlas_runtime import model_control_service

    monkeypatch.setenv("ATLAS_HOME", str(tmp_path))
    config = config_service.AtlasConfig()
    before = model_control_service.get_provider_model_status(db, config)
    run_id = mission_service.ensure_operator_run(db, lock)
    audit_service.emit(
        db,
        lock,
        run_id=run_id,
        event_type="provider_fallback",
        data={
            "from": "provider-a",
            "to": "openrouter",
            "reason": "timeout",
        },
    )
    after = model_control_service.get_provider_model_status(db, config)

    assert before.fallback_status == "not_used"
    assert after.fallback_status == "used"
