"""Frozen contract tests for the Phase 10.7 permission policy schema."""
from __future__ import annotations

import json

import pytest
from pydantic import ValidationError

from atlas_core.schemas.control_plane import (
    AtlasConfig,
    PermissionExplainReceipt,
    PermissionPolicyProfile,
    PermissionPolicyRule,
    PermissionRuleSelector,
)


def test_legacy_config_keeps_safe_manual_defaults() -> None:
    config = AtlasConfig.model_validate({"permission": {"mode": "ask"}})

    assert config.permission.preset == "manual"
    assert config.permission.rules == ()
    assert config.permission.profiles == ()
    assert config.permission.workspace_only is False
    assert config.permission.hardline_version == "2026-06-29"


def test_policy_contract_roundtrips_as_stable_json() -> None:
    config = AtlasConfig.model_validate(
        {
            "permission": {
                "preset": "full_autonomy",
                "workspace_only": True,
                "rules": [
                    {
                        "id": "deny-shell-rm",
                        "effect": "deny",
                        "selector": {
                            "tools": ["shell"],
                            "command_patterns": ["rm *"],
                        },
                        "description": "Keep destructive shell commands gated.",
                    }
                ],
                "profiles": [
                    {
                        "id": "webui-strict",
                        "preset": "manual",
                        "surfaces": ["webui"],
                    }
                ],
            }
        }
    )

    dumped = config.model_dump(mode="json")
    encoded = json.dumps(dumped, sort_keys=True, separators=(",", ":"))
    reloaded = AtlasConfig.model_validate_json(encoded)

    assert reloaded == config
    assert isinstance(dumped["permission"]["rules"], list)
    assert dumped["permission"]["rules"][0]["selector"]["tools"] == ["shell"]


def test_policy_models_are_frozen_and_forbid_executable_or_unknown_fields() -> None:
    rule = PermissionPolicyRule(
        id="deny-outside",
        effect="deny",
        selector=PermissionRuleSelector(path_patterns=("..*",)),
    )
    with pytest.raises(ValidationError):
        rule.effect = "allow"  # type: ignore[misc]

    with pytest.raises(ValidationError):
        PermissionPolicyRule.model_validate(
            {
                "id": "bad-callback",
                "effect": "allow",
                "selector": {},
                "callback": "module:function",
            }
        )


def test_profile_more_permissive_than_master_is_rejected() -> None:
    with pytest.raises(ValidationError, match="may only narrow"):
        AtlasConfig.model_validate(
            {
                "permission": {
                    "preset": "manual",
                    "profiles": [
                        {
                            "id": "bad-web",
                            "preset": "full_autonomy",
                            "surfaces": ["webui"],
                        }
                    ],
                }
            }
        )


def test_profile_allow_requires_master_authority() -> None:
    profile = PermissionPolicyProfile(
        id="cli-profile",
        preset="manual",
        surfaces=("cli",),
        rules=(
            PermissionPolicyRule(
                id="profile-allow-shell",
                effect="allow",
                selector=PermissionRuleSelector(tools=("shell",)),
            ),
        ),
    )
    with pytest.raises(ValidationError, match="allow rule"):
        AtlasConfig.model_validate(
            {
                "permission": {
                    "preset": "manual",
                    "profiles": [profile.model_dump(mode="json")],
                }
            }
        )


def test_profile_can_reuse_exact_master_allow_or_narrow_full_autonomy() -> None:
    master_rule = PermissionPolicyRule(
        id="master-allow-read",
        effect="allow",
        selector=PermissionRuleSelector(risks=("read",)),
    )

    manual = AtlasConfig.model_validate(
        {
            "permission": {
                "preset": "manual",
                "rules": [master_rule.model_dump(mode="json")],
                "profiles": [
                    {
                        "id": "same-read",
                        "preset": "manual",
                        "rules": [
                            {
                                **master_rule.model_dump(mode="json"),
                                "id": "profile-allow-read",
                            }
                        ],
                    }
                ],
            }
        }
    )
    autonomous = AtlasConfig.model_validate(
        {
            "permission": {
                "preset": "full_autonomy",
                "profiles": [{"id": "manual-web", "preset": "manual"}],
            }
        }
    )

    assert manual.permission.profiles[0].rules[0].effect == "allow"
    assert autonomous.permission.profiles[0].preset == "manual"


def test_explain_receipt_is_json_stable_and_contains_no_prompt_field() -> None:
    receipt = PermissionExplainReceipt(
        decision="deny",
        reason_code="hardline_block_device",
        matched_rule_id="hardline:block-device",
        source_layer="hardline",
        effective_preset="full_autonomy",
        effective_profile_id="webui",
        tool="shell",
        capability="command.execute",
        risk="shell",
        workspace_root="C:/work",
        target_paths=("C:/work/file",),
        maintenance_scope_used=False,
    )
    payload = receipt.model_dump(mode="json")

    assert payload["decision"] == "deny"
    assert payload["target_paths"] == ["C:/work/file"]
    assert "prompt" not in payload
    assert "chain_of_thought" not in payload

