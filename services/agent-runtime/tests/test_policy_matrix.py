"""Deterministic permission-policy matrix and scope tests."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from atlas_core.schemas.control_plane import PermissionConfig
from atlas_core.schemas.tool import ToolManifest
from atlas_runtime.policy import PolicyFacts, decide


def _manifest(tool: str, risk: str, capability: str | None) -> ToolManifest:
    return ToolManifest(
        name=tool,
        risk_level=risk,
        permissions=[] if capability is None else [capability],
    )


def test_frozen_permission_matrix() -> None:
    fixture = json.loads(
        (
            Path(__file__).parent / "fixtures" / "permission_policy_matrix.json"
        ).read_text(encoding="utf-8")
    )
    for case in fixture["cases"]:
        facts_data = dict(case["facts"])
        tool = facts_data.pop("tool")
        risk = facts_data.pop("risk")
        capability = facts_data.pop("capability", None)
        decision = decide(
            _manifest(tool, risk, capability),
            config=PermissionConfig.model_validate(case["config"]),
            facts=PolicyFacts(
                tool=tool,
                risk=risk,
                capability=capability,
                **facts_data,
            ),
        )
        expected = case["expected"]
        assert decision.receipt is not None, case["id"]
        actual = decision.receipt.model_dump(mode="json", exclude_none=True)
        for key, value in expected.items():
            assert actual[key] == value, case["id"]


def test_deny_rule_wins_over_later_allow_rule() -> None:
    config = PermissionConfig.model_validate(
        {
            "preset": "full_autonomy",
            "rules": [
                {
                    "id": "deny-shell",
                    "effect": "deny",
                    "selector": {"risks": ["shell"]},
                },
                {
                    "id": "allow-git",
                    "effect": "allow",
                    "selector": {
                        "risks": ["shell"],
                        "command_patterns": ["git *"],
                    },
                },
            ],
        }
    )

    result = decide(
        _manifest("shell", "shell", "command.execute"),
        config=config,
        facts=PolicyFacts(
            tool="shell",
            risk="shell",
            capability="command.execute",
            command="git status",
        ),
    )

    assert result.allowed is False
    assert result.requires_approval is False
    assert result.reason == "master_rule_denied"
    assert result.receipt.matched_rule_id == "deny-shell"


def test_scoped_allow_can_resolve_ask_but_not_deny() -> None:
    manual = PermissionConfig(preset="manual")
    facts = PolicyFacts(tool="write_file", risk="write", capability="filesystem.write")
    manifest = _manifest("write_file", "write", "filesystem.write")

    allowed = decide(
        manifest,
        config=manual,
        facts=facts,
        scoped_allow_rule_id="session-rule-1",
    )
    denied = decide(
        manifest,
        config=PermissionConfig.model_validate(
            {
                "preset": "manual",
                "rules": [
                    {
                        "id": "deny-write",
                        "effect": "deny",
                        "selector": {"risks": ["write"]},
                    }
                ],
            }
        ),
        facts=facts,
        scoped_allow_rule_id="forged-rule",
    )

    assert allowed.allowed is True
    assert allowed.receipt.source_layer == "scoped_allow"
    assert denied.allowed is False
    assert denied.receipt.source_layer == "master"


def test_workspace_only_allows_real_child_and_denies_escape(tmp_path: Path) -> None:
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    child = workspace / "notes" / "file.md"
    outside = tmp_path / "outside.txt"
    config = PermissionConfig(preset="full_autonomy", workspace_only=True)
    manifest = _manifest("write_file", "write", "filesystem.write")

    inside_result = decide(
        manifest,
        config=config,
        facts=PolicyFacts(
            tool="write_file",
            risk="write",
            capability="filesystem.write",
            workspace_root=str(workspace),
            target_paths=(str(child),),
        ),
    )
    outside_result = decide(
        manifest,
        config=config,
        facts=PolicyFacts(
            tool="write_file",
            risk="write",
            capability="filesystem.write",
            workspace_root=str(workspace),
            target_paths=(str(outside),),
        ),
    )

    assert inside_result.allowed is True
    assert outside_result.allowed is False
    assert outside_result.reason == "path_outside_workspace"


@pytest.mark.parametrize(
    ("explicit", "capability", "target_inside", "expected"),
    [
        (True, "atlas.config.write", True, True),
        (False, "atlas.config.write", True, False),
        (True, "filesystem.write", True, False),
        (True, "atlas.config.write", False, False),
    ],
)
def test_protected_maintenance_scope_requires_all_trusted_facts(
    tmp_path: Path,
    explicit: bool,
    capability: str,
    target_inside: bool,
    expected: bool,
) -> None:
    workspace = tmp_path / "work"
    atlas_root = tmp_path / "atlas"
    workspace.mkdir()
    atlas_root.mkdir()
    target = (
        atlas_root / "config.yaml"
        if target_inside
        else tmp_path / "unrelated" / "config.yaml"
    )
    result = decide(
        _manifest("write_file", "write", capability),
        config=PermissionConfig(
            preset="full_autonomy",
            workspace_only=True,
            maintenance_roots=(str(atlas_root),),
        ),
        facts=PolicyFacts(
            tool="write_file",
            risk="write",
            capability=capability,
            workspace_root=str(workspace),
            target_paths=(str(target),),
            explicit_user_maintenance=explicit,
        ),
    )

    assert result.allowed is expected
    assert result.receipt.maintenance_scope_used is expected


def test_smart_unavailable_fails_closed() -> None:
    result = decide(
        _manifest("write_file", "write", "filesystem.write"),
        config=PermissionConfig(preset="smart"),
        facts=PolicyFacts(
            tool="write_file",
            risk="write",
            capability="filesystem.write",
            smart_recommendation="unavailable",
        ),
    )

    assert result.allowed is False
    assert result.requires_approval is False
    assert result.reason == "smart_advisor_unavailable"
