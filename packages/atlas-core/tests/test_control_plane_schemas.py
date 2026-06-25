"""Frozen public contracts for the ATLAS configuration control plane."""
from __future__ import annotations

import json

import pytest
from pydantic import ValidationError

from atlas_core.schemas import AuditEvent
from atlas_core.schemas.control_plane import (
    AtlasConfig,
    AuthStatus,
    ConfigPatchRequest,
    ControlPlaneSnapshot,
    ProviderModelStatus,
    SettingStatus,
)


def test_atlas_config_defaults_are_versioned_and_backward_compatible():
    config = AtlasConfig()

    assert config.schema_version == 1
    assert config.revision == 0
    assert config.provider.name == "openrouter"
    assert config.runtime.default_agent == "native"
    assert config.gateway.rust_port == 8484
    assert config.cockpit.port == 3000
    assert config.context.token_budget == 8000
    assert config.permission.mode == "ask"
    assert config.modules["wiki"] is True


def test_config_contracts_are_frozen_and_forbid_unknown_fields():
    config = AtlasConfig()

    with pytest.raises(ValidationError):
        config.revision = 2
    with pytest.raises(ValidationError):
        AtlasConfig.model_validate({"surprise": True})


@pytest.mark.parametrize("value", ["sk-live-secret", "token-value", " env:KEY"])
def test_provider_api_key_rejects_inline_or_ambiguous_values(value):
    with pytest.raises(ValidationError):
        AtlasConfig.model_validate({"provider": {"api_key": value}})


@pytest.mark.parametrize("value", ["", "env:OPENROUTER_API_KEY", "env:KEY_2"])
def test_provider_api_key_accepts_only_empty_or_env_reference(value):
    config = AtlasConfig.model_validate({"provider": {"api_key": value}})
    assert config.provider.api_key == value


def test_patch_request_requires_nonnegative_revision_and_json_object():
    request = ConfigPatchRequest(
        expected_revision=3,
        changes_json='{"provider.model":"anthropic/claude-sonnet-4"}',
    )
    assert request.changes() == {
        "provider.model": "anthropic/claude-sonnet-4",
    }

    with pytest.raises(ValidationError):
        ConfigPatchRequest(expected_revision=-1, changes_json="{}")
    with pytest.raises(ValidationError):
        ConfigPatchRequest(expected_revision=0, changes_json="[]")
    with pytest.raises(ValidationError):
        ConfigPatchRequest(expected_revision=0, changes_json="{bad json")


def test_public_status_contracts_are_json_stable_and_secret_free():
    setting = SettingStatus(
        path="provider.model",
        configured_json='"anthropic/claude-sonnet-4"',
        effective_json='"anthropic/claude-sonnet-4"',
        source="config",
        validation_status="valid",
        restart_required=False,
    )
    auth = AuthStatus(
        provider="openrouter",
        auth_type="api_key",
        status="auth_present",
        source="env",
        health="available",
        redacted_hint="…1234",
    )
    effective = ProviderModelStatus(
        configured_provider="openrouter",
        effective_provider="openrouter",
        configured_model="anthropic/claude-sonnet-4",
        effective_model="anthropic/claude-sonnet-4",
        source="config",
        auth_status="auth_present",
        provider_health="available",
        model_health="available",
        fallback_status="not_used",
    )
    snapshot = ControlPlaneSnapshot(
        settings=(setting,),
        auth=(auth,),
        effective=effective,
        mock_mode=False,
    )

    rendered = json.dumps(snapshot.model_dump())
    assert "sk-secret" not in rendered
    assert "token-value" not in rendered
    assert json.loads(rendered)["provider"]["name"] == "openrouter"


@pytest.mark.parametrize(
    "event_type",
    [
        "config_change",
        "auth_change",
        "model_call_start",
        "model_call_end",
        "provider_fallback",
    ],
)
def test_audit_event_accepts_control_plane_event_types(event_type):
    event = AuditEvent(run_id="run-1", event_type=event_type)
    assert event.event_type == event_type
