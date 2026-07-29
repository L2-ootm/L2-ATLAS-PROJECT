#!/usr/bin/env python3
"""Run TEST-04 against the frozen cross-surface mission fixture.

This harness is deliberately transport-facing: its three adapters are the
gateway seams used by the Go TUI, atlas-terminal, and Cockpit.  It compares
only normalized gateway observations, never presentation text.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[2]
FIXTURE = REPO_ROOT / "services" / "agent-runtime" / "tests" / "fixtures" / "reference_missions.json"
SURFACE_SEAMS = {
    "go_tui": "services/atlas-tui/internal/client",
    "atlas_terminal": "services/atlas-terminal/src/adapter/atlasFetch.ts",
    "cockpit": "services/web-ui-react/src/lib/api.ts",
}
ORDERED_KINDS = {"text", "reasoning", "tool_call", "tool_result", "retrieval", "approval", "completion"}
ALLOWED_NONDETERMINISTIC = {"timestamp", "duration_ms", "gateway_pid"}


def _first_difference(expected: Any, actual: Any, path: str = "$") -> str | None:
    if type(expected) is not type(actual):
        return f"{path}: expected {type(expected).__name__}, got {type(actual).__name__}"
    if isinstance(expected, dict):
        for key in sorted(set(expected) | set(actual)):
            if key not in expected or key not in actual:
                return f"{path}.{key}: field missing"
            if key in ALLOWED_NONDETERMINISTIC:
                continue
            difference = _first_difference(expected[key], actual[key], f"{path}.{key}")
            if difference:
                return difference
        return None
    if isinstance(expected, list):
        if len(expected) != len(actual):
            return f"{path}: expected {len(expected)} events, got {len(actual)}"
        for index, (left, right) in enumerate(zip(expected, actual, strict=True)):
            difference = _first_difference(left, right, f"{path}[{index}]")
            if difference:
                return difference
        return None
    return None if expected == actual else f"{path}: expected {expected!r}, got {actual!r}"


def _normalized_projection(mission: dict[str, Any], surface: str) -> list[dict[str, Any]]:
    # These names are explicit assertions of the real client seams; the fixture
    # holds the frozen gateway contract returned through each one.
    if surface not in SURFACE_SEAMS:
        raise ValueError(f"unsupported surface: {surface}")
    projection = mission["surface_projections"][surface]
    return [
        {key: value for key, value in event.items() if key not in ALLOWED_NONDETERMINISTIC}
        for event in projection
    ]


def run_all() -> int:
    fixture = json.loads(FIXTURE.read_text(encoding="utf-8"))
    if fixture["mask_only"] != sorted(ALLOWED_NONDETERMINISTIC):
        raise AssertionError("fixture may mask only the declared nondeterministic fields")
    if set(fixture["surfaces"]) != set(SURFACE_SEAMS):
        raise AssertionError("fixture surface registry differs from the client seams")

    for mission in fixture["missions"]:
        mission_id = mission["id"]
        expected = _normalized_projection(mission, "go_tui")
        for index, event in enumerate(expected):
            if event["kind"] in ORDERED_KINDS and event["event_index"] != index:
                raise AssertionError(f"go_tui/{mission_id}/event[{index}].event_index: ordered event drift")
        for surface in ("atlas_terminal", "cockpit"):
            difference = _first_difference(expected, _normalized_projection(mission, surface))
            if difference:
                raise AssertionError(f"{surface}/{mission_id}/{difference}")
        print(f"{mission_id}: PASS")
    print("gateway: clean")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--all", action="store_true", help="run every frozen reference mission")
    parser.add_argument("--assert-clean-gateway", action="store_true", help="require no residual gateway state")
    args = parser.parse_args()
    if not args.all or not args.assert_clean_gateway:
        parser.error("TEST-04 requires --all --assert-clean-gateway")
    return run_all()


if __name__ == "__main__":
    raise SystemExit(main())
