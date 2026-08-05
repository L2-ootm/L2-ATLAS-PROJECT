"""Frozen public contracts for the ATLAS configuration control plane."""
from __future__ import annotations

import json

import pytest
from pydantic import ValidationError

from atlas_core.schemas import AuditEvent
from atlas_core.schemas.control_plane import (
    AtlasConfig,
    AuthStatus,
    ConfigChangeReceipt,
    ConfigPatchRequest,
    ConfigPatchResult,
    ConfigReloadMetadata,
    ControlPlaneError,
    ControlPlaneSnapshot,
    ProviderModelStatus,
    SettingStatus,
)


def test_control_plane_error_can_report_partial_commit_without_guessing() -> None:
    error = ControlPlaneError(
        "config_audit_failed",
        "config committed but audit failed",
        "reconcile before retrying",
        current_revision=7,
        committed=True,
    )

    assert error.as_dict()["committed"] is True
    assert error.as_dict()["current_revision"] == 7


def test_atlas_config_defaults_are_versioned_and_backward_compatible() -> None:
    config = AtlasConfig()

    assert config.schema_version == 2
    assert config.revision == 0
    assert config.provider.name == "openrouter"
    assert config.runtime.default_agent == "native"
    assert config.gateway.rust_port == 8484
    assert config.cockpit.port == 3000
    assert config.context.token_budget == 8000
    assert config.permission.mode == "ask"
    assert config.modules["wiki"] is True


def test_config_contracts_are_frozen_and_forbid_unknown_fields() -> None:
    config = AtlasConfig()

    with pytest.raises(ValidationError):
        config.revision = 2
    with pytest.raises(ValidationError):
        AtlasConfig.model_validate({"surprise": True})


@pytest.mark.parametrize("value", ["sk-live-secret", "token-value", " env:KEY"])
def test_provider_api_key_rejects_inline_or_ambiguous_values(value: str) -> None:
    with pytest.raises(ValidationError):
        AtlasConfig.model_validate({"provider": {"api_key": value}})


@pytest.mark.parametrize("value", ["", "env:OPENROUTER_API_KEY", "env:KEY_2"])
def test_provider_api_key_accepts_only_empty_or_env_reference(value: str) -> None:
    config = AtlasConfig.model_validate({"provider": {"api_key": value}})
    assert config.provider.api_key == value


def test_patch_request_requires_nonnegative_revision_and_json_object() -> None:
    request = ConfigPatchRequest(
        expected_revision=3,
        changes_json='{"provider.model":"anthropic/claude-sonnet-4"}',
    )
    assert request.changes() == {
        "provider.model": "anthropic/claude-sonnet-4",
    }
    assert request.reason == "configuration update"

    with pytest.raises(ValidationError):
        ConfigPatchRequest(expected_revision=-1, changes_json="{}")
    with pytest.raises(ValidationError):
        ConfigPatchRequest(expected_revision=0, changes_json="[]")
    with pytest.raises(ValidationError):
        ConfigPatchRequest(expected_revision=0, changes_json="{bad json")


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("reason", ""),
        ("reason", "x" * 241),
        ("reason", "line one\nline two"),
        ("source_surface", ""),
        ("source_surface", "x" * 97),
        ("source_session_id", "BAD SESSION"),
    ],
)
def test_patch_request_bounds_untrusted_audit_text(field: str, value: str) -> None:
    with pytest.raises(ValidationError):
        ConfigPatchRequest(
            expected_revision=0,
            changes_json="{}",
            **{field: value},
        )


def _config_receipt(**overrides: object) -> ConfigChangeReceipt:
    defaults: dict[str, object] = {
        "event_id": "63bf2f11-56cf-4e9c-80f8-1660f50917ec",
        "committed_revision": 4,
        "changed_paths": (
            "context.enable_brain",
            "provider.base_url",
            "provider.model",
        ),
        "before": {
            "context.enable_brain": False,
            "provider.base_url": None,
            "provider.model": "old/model",
        },
        "after": {
            "context.enable_brain": True,
            "provider.base_url": None,
            "provider.model": "新しい/model ✨",
        },
        "reload": {
            "context.enable_brain": ConfigReloadMetadata(
                restart_required=False,
                visibility="next_read_or_new_execution",
            ),
            "provider.base_url": ConfigReloadMetadata(
                restart_required=True,
                visibility="restart",
            ),
            "provider.model": ConfigReloadMetadata(
                restart_required=False,
                visibility="next_read_or_new_execution",
            ),
        },
        "authenticated_actor": "operator",
        "asserted_source_surface": "webui; $(not-executed)",
        "asserted_source_session_id": "surf-1",
        "reason": "Switch model; $(still-not-executed) — revisão",
        "timestamp": "2026-08-05T12:30:00+00:00",
    }
    defaults.update(overrides)
    return ConfigChangeReceipt(**defaults)


def test_config_receipt_preserves_typed_values_and_json_stability() -> None:
    receipt = _config_receipt()
    dumped = receipt.model_dump(mode="json")
    encoded = json.dumps(dumped, ensure_ascii=False, sort_keys=True, separators=(",", ":"))

    restored = ConfigChangeReceipt.model_validate_json(encoded)
    assert restored == receipt
    assert restored.before["context.enable_brain"] is False
    assert restored.after["context.enable_brain"] is True
    assert restored.before["provider.base_url"] is None
    assert restored.after["provider.model"] == "新しい/model ✨"


def test_config_receipt_is_frozen_and_has_no_secret_or_owner_token_fields() -> None:
    receipt = _config_receipt(
        before={
            "context.enable_brain": False,
            "provider.base_url": None,
            "provider.model": "[REDACTED]",
        }
    )
    rendered = json.dumps(receipt.model_dump(mode="json"), sort_keys=True)

    with pytest.raises(ValidationError):
        receipt.reason = "changed"  # type: ignore[misc]
    assert "owner_token" not in ConfigChangeReceipt.model_fields
    assert "credential" not in receipt.before
    assert "sk-live-token-canary" not in rendered
    assert receipt.credential_status == "not_in_scope"
    assert receipt.config_status == "committed"

    with pytest.raises(ValidationError, match="secret-masked"):
        _config_receipt(
            after={
                "context.enable_brain": True,
                "provider.base_url": None,
                "provider.model": "sk-live-token-canary",
            }
        )


@pytest.mark.parametrize(
    "overrides",
    [
        {"reason": "line one\nline two"},
        {"reason": "x" * 241},
        {"asserted_source_surface": "x" * 97},
        {"asserted_source_session_id": "../../owner"},
        {"timestamp": "2026-08-05T12:30:00"},
        {"before": {"context.enable_brain": False}},
        {"changed_paths": ("context.enable_brain", "context.enable_brain")},
    ],
)
def test_config_receipt_rejects_ambiguous_or_unbounded_payloads(
    overrides: dict[str, object],
) -> None:
    with pytest.raises(ValidationError):
        _config_receipt(**overrides)


def test_config_patch_result_is_additive_and_accepts_legacy_snapshot() -> None:
    legacy = ControlPlaneSnapshot().model_dump(mode="json")
    result = ConfigPatchResult.model_validate(legacy)

    assert result.receipt is None
    assert result.revision == legacy["revision"]
    assert result.provider.name == legacy["provider"]["name"]
    assert result.model_dump(mode="json")["settings"] == legacy["settings"]


def test_public_status_contracts_are_json_stable_and_secret_free() -> None:
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
def test_audit_event_accepts_control_plane_event_types(event_type: str) -> None:
    event = AuditEvent(run_id="run-1", event_type=event_type)
    assert event.event_type == event_type
