"""Authority, redaction, dependency, cleanup, and donor-provenance gates."""

from __future__ import annotations

import json
from pathlib import Path

from atlas_core.schemas.control_plane import PermissionConfig
from atlas_core.schemas.tool import ToolManifest
from atlas_runtime.policy import PolicyFacts, decide

REPO_ROOT = Path(__file__).resolve().parents[3]


def _read(path: str) -> str:
    return (REPO_ROOT / path).read_text(encoding="utf-8")


def test_guarded_tool_execution_reaches_policy_and_broker_authority() -> None:
    source = _read("services/agent-runtime/atlas_runtime/tool_service.py")
    assert "policy.decide(" in source
    assert "permission_broker." in source
    assert source.count("decision = policy.decide(") == 1


def test_receipts_exclude_secrets_raw_arguments_and_chain_of_thought() -> None:
    result = decide(
        ToolManifest(
            name="write_file",
            risk_level="write",
            permissions=["filesystem.write"],
        ),
        config=PermissionConfig(preset="manual"),
        facts=PolicyFacts(
            tool="write_file",
            risk="write",
            capability="filesystem.write",
            target_paths=("redacted/example.txt",),
            surface="webui",
        ),
    )
    receipt = result.receipt.model_dump(mode="json")
    forbidden = {
        "api_key",
        "password",
        "secret",
        "token",
        "owner_token",
        "raw_arguments",
        "chain_of_thought",
        "reasoning_content",
    }
    assert forbidden.isdisjoint(receipt)


def test_no_parallel_actionable_or_legacy_console_route_survives() -> None:
    rust = _read("native/atlas-core-rs/crates/atlas-gateway/src/lib.rs")
    react = _read("services/web-ui-react/src/lib/api.ts")
    go = _read("services/atlas-tui/internal/client/client.go")

    assert '.route("/v1/tools/approvals", get(tool_approval_outcomes))' in rust
    assert 'const SURFACE_OWNER_HEADER: &str = "x-atlas-surface-owner"' in rust
    assert "require_surface_owner(&state, &headers" in rust
    assert "X-Atlas-Surface-Owner" in react + go
    assert "/v1/console/chat" not in rust + react
    assert "/v1/console/stream" not in rust + react
    for source in (rust, react, go):
        assert "/v1/tools/approvals/{id}/approve" not in source
        assert "/v1/tools/approvals/{id}/reject" not in source


def test_retired_terminal_generations_and_dependencies_are_absent() -> None:
    assert not (REPO_ROOT / "apps/atlas-tui").exists()
    assert not (
        REPO_ROOT / "services/agent-runtime/atlas_runtime/tui"
    ).exists()

    python_project = _read("services/agent-runtime/pyproject.toml")
    assert '"prompt_toolkit' not in python_project
    assert '"rich' not in python_project

    web_package = json.loads(_read("services/web-ui-react/package.json"))
    production = web_package.get("dependencies", {})
    assert {"@opentui/core", "@opentui/solid", "solid-js"}.isdisjoint(production)
    assert {"vitest", "jsdom", "@testing-library/react"}.isdisjoint(production)


def test_hermes_is_provenance_not_user_facing_permission_identity() -> None:
    policy = _read("services/agent-runtime/atlas_runtime/policy.py")
    go_ui = _read("services/atlas-tui/internal/tui/model.go")
    web_ui = "".join(
        path.read_text(encoding="utf-8")
        for path in (REPO_ROOT / "services/web-ui-react/src/components/agent").glob("*.tsx")
    )

    assert "Hermes" not in policy
    assert "HERMES" not in go_ui
    assert "Hermes" not in web_ui
