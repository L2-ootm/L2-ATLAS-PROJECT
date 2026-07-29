from __future__ import annotations

import importlib.util
import json
import pathlib


SCRIPT = pathlib.Path(__file__).resolve().parents[1] / "scripts" / "reality_test.py"
SPEC = importlib.util.spec_from_file_location("reality_test", SCRIPT)
assert SPEC and SPEC.loader
reality_test = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(reality_test)


def test_redact_removes_nested_and_inline_credentials() -> None:
    value = {
        "api_key": "freellmapi-should-never-appear",
        "output": "Authorization: Bearer visible-token-value",
        "nested": [{"password": "plaintext"}],
    }
    rendered = json.dumps(reality_test.redact(value))
    assert "should-never-appear" not in rendered
    assert "visible-token-value" not in rendered
    assert "plaintext" not in rendered
    assert rendered.count("[REDACTED]") == 3


def test_compare_snapshot_detects_content_and_status_changes() -> None:
    before = {
        "head": "a",
        "status_porcelain": "",
        "tracked_file_count": 2,
        "tracked_content_sha256": "old",
    }
    unchanged = reality_test.compare_snapshot(before, dict(before))
    assert unchanged == {"unchanged": True, "changes": {}}

    after = {**before, "status_porcelain": " M app.py\n", "tracked_content_sha256": "new"}
    changed = reality_test.compare_snapshot(before, after)
    assert changed["unchanged"] is False
    assert set(changed["changes"]) == {"status_porcelain", "tracked_content_sha256"}


def test_reality_scenarios_cover_required_surfaces_and_zero_tolerance() -> None:
    suite = json.loads(reality_test.SCENARIOS.read_text(encoding="utf-8"))
    surfaces = {surface for scenario in suite["scenarios"] for surface in scenario["surfaces"]}
    ids = {scenario["id"] for scenario in suite["scenarios"]}
    assert surfaces == {"cli", "browser"}
    assert {"parallel-leaves", "configured-team", "failure-honesty", "session-continuity"} <= ids
    assert "project_mutation" in suite["quality_policy"]["zero_tolerance"]
    assert len(suite["rubric"]) == 5
