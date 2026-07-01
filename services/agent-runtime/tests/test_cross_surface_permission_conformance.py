"""Frozen cross-surface projection contract for Phase 10.7."""

from __future__ import annotations

import json
from pathlib import Path

from atlas_core.schemas.control_plane import PermissionConfig
from atlas_core.schemas.surface_session import SurfaceEvent
from atlas_core.schemas.tool import ToolManifest
from atlas_runtime.policy import PolicyFacts, decide

FIXTURES = Path(__file__).parent / "fixtures"
REPO_ROOT = Path(__file__).resolve().parents[3]


def test_normalized_event_fixture_preserves_identity_order_and_terminal_outcome() -> None:
    fixture = json.loads(
        (FIXTURES / "surface_event_parity.json").read_text(encoding="utf-8")
    )
    events = [SurfaceEvent.model_validate(item) for item in fixture["events"]]

    assert {event.session_id for event in events} == {fixture["session_id"]}
    assert {event.run_id for event in events} == {"fixture-run"}
    assert [event.seq for event in events] == list(range(len(events)))
    assert [event.kind for event in events] == [
        "text",
        "reasoning",
        "tool_call",
        "tool_result",
        "task",
        "retry",
        "retrieval",
        "approval",
        "error",
        "completion",
    ]
    assert json.loads(events[-1].payload_json)["status"] == fixture["terminal_outcome"]


def test_permission_fixture_has_one_canonical_receipt_projection() -> None:
    fixture = json.loads(
        (FIXTURES / "permission_policy_matrix.json").read_text(encoding="utf-8")
    )
    for case in fixture["cases"]:
        raw_facts = dict(case["facts"])
        tool = raw_facts.pop("tool")
        risk = raw_facts.pop("risk")
        capability = raw_facts.pop("capability", None)
        result = decide(
            ToolManifest(
                name=tool,
                risk_level=risk,
                permissions=[] if capability is None else [capability],
            ),
            config=PermissionConfig.model_validate(case["config"]),
            facts=PolicyFacts(
                tool=tool,
                risk=risk,
                capability=capability,
                **raw_facts,
            ),
        )
        actual = result.receipt.model_dump(mode="json", exclude_none=True)
        assert {
            key: actual[key] for key in case["expected"]
        } == case["expected"], case["id"]


def test_every_visual_surface_uses_session_owned_approval_routes() -> None:
    sources = {
        "rust": (
            REPO_ROOT
            / "native/atlas-core-rs/crates/atlas-gateway/src/lib.rs"
        ).read_text(encoding="utf-8"),
        "go": (
            REPO_ROOT / "services/atlas-tui/internal/client/client.go"
        ).read_text(encoding="utf-8"),
        "react": (
            REPO_ROOT / "services/web-ui-react/src/lib/api.ts"
        ).read_text(encoding="utf-8"),
    }
    route_fragment = "/v1/surface-sessions/"
    for surface, source in sources.items():
        assert route_fragment in source, surface
        assert "/v1/tools/approvals/{id}/approve" not in source, surface
        assert "/v1/tools/approvals/{id}/reject" not in source, surface
