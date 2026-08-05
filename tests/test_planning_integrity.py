from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
from datetime import date
from pathlib import Path


SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "planning_integrity.py"
SPEC = importlib.util.spec_from_file_location("planning_integrity", SCRIPT)
assert SPEC and SPEC.loader
planning_integrity = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(planning_integrity)


def write(root: Path, relative: str, text: str = "") -> Path:
    path = root / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return path


def make_tree(tmp_path: Path, *, debt: bool = True) -> Path:
    root = tmp_path / "repo"
    resume = ".planning/phases/10.8-cutover/.continue-here.md"
    state = f"""---
milestone: v1.1
current_phase: 10.8
current_phase_name: Cutover
current_plan: 2
total_plans_in_phase: 2
status: in_progress
progress: 50
paused_at: plan-02
last_activity: {date.today().isoformat()}
last_activity_desc: Stabilizing
---
# State

## Session
Resume File: `{resume}`
"""
    roadmap = """# Roadmap

## Milestones
- 🔨 **v1.1 Stable** — active

### 🔨 v1.1 Stable — ACTIVE
#### Phase 10.8: Cutover

| Phase | Milestone | Plans | Status |
|---|---|---|---|
| 10.8 Cutover | v1.1 | 1/2 | In Progress |
"""
    write(root, ".planning/STATE.md", state)
    write(root, ".planning/ROADMAP.md", roadmap)
    write(root, ".planning/phases/10.8-cutover/10.8-01-PLAN.md")
    write(root, ".planning/phases/10.8-cutover/10.8-01-SUMMARY.md")
    write(root, ".planning/phases/10.8-cutover/10.8-02-PLAN.md")
    write(root, ".planning/phases/10.8-cutover/.continue-here.md", "resume")
    if debt:
        write(
            root,
            ".planning/phases/10.8-cutover/10.8-UAT.md",
            """---
status: partial
phase: 10.8
---
# UAT
release-blocking
### 1. Rollback
expected: fallback restores
result: pending
""",
        )
    return root


def codes(report: dict, field: str) -> set[str]:
    return {item["code"] for item in report[field]}


def test_structural_integrity_is_separate_from_production_readiness(tmp_path: Path) -> None:
    root = make_tree(tmp_path)
    report = planning_integrity.inspect(root)

    assert report["schema_version"] == 1
    assert report["integrity_ok"] is True
    assert report["ok"] is True
    assert report["production_ready"] is False
    assert report["active_milestone"] == "v1.1"
    assert report["current_phase"] == "10.8"
    assert report["active_progress"] == {"plans": 2, "summaries": 1, "percent": 50}
    assert report["portfolio_progress"] == report["active_progress"]
    assert report["verification_debt"][0]["severity"] == "blocking"


def test_cli_exit_modes_and_stable_json(tmp_path: Path) -> None:
    root = make_tree(tmp_path)
    strict = subprocess.run(
        [sys.executable, str(SCRIPT), "--root", str(root), "--strict", "--json"],
        text=True,
        capture_output=True,
        check=False,
    )
    production = subprocess.run(
        [sys.executable, str(SCRIPT), "--root", str(root), "--production", "--json"],
        text=True,
        capture_output=True,
        check=False,
    )

    assert strict.returncode == 0
    assert production.returncode == 2

    format_json = subprocess.run(
        [sys.executable, str(SCRIPT), "--root", str(root), "--strict", "--format", "json"],
        check=False,
        capture_output=True,
        text=True,
    )
    assert format_json.returncode == 0
    assert json.loads(format_json.stdout)["integrity_ok"] is True
    payload = json.loads(strict.stdout)
    assert payload["ok"] == payload["integrity_ok"]
    assert list(payload) == sorted(payload)


def test_exact_pairing_rejects_orphans_and_noncurrent_missing_summary(tmp_path: Path) -> None:
    root = make_tree(tmp_path, debt=False)
    write(root, ".planning/phases/10.8-cutover/10.8-03-SUMMARY.md")
    write(root, ".planning/phases/10.8-cutover/10.8-04-PLAN.md")
    report = planning_integrity.inspect(root)

    assert "orphan_live_summary" in codes(report, "errors")
    assert "unpaired_live_plan" in codes(report, "errors")
    assert report["integrity_ok"] is False


def test_decimal_phase_tokens_and_duplicate_live_phases(tmp_path: Path) -> None:
    root = make_tree(tmp_path, debt=False)
    write(root, ".planning/phases/10.0.3-one/PHASE.md")
    write(root, ".planning/phases/10.0.3-two/PHASE.md")
    report = planning_integrity.inspect(root)

    duplicate = [item for item in report["errors"] if item["code"] == "duplicate_live_phase"]
    assert len(duplicate) == 1
    assert "10.0.3-one" in duplicate[0]["message"]
    assert "10.0.3-two" in duplicate[0]["message"]


def test_archived_pairing_debt_and_command_center_exception(tmp_path: Path) -> None:
    root = make_tree(tmp_path, debt=False)
    write(root, ".planning/milestones/v1.0.5-phases/10.0.3-command-center/PLAN.md")
    write(root, ".planning/milestones/v1.0.5-phases/10.0.3-command-center/SESSION-SUMMARY.md")
    write(root, ".planning/milestones/v1.0.5-phases/10.0.2-installer/10.0.2-01-PLAN.md")
    report = planning_integrity.inspect(root)

    assert report["integrity_ok"] is True
    assert report["portfolio_progress"] == {"plans": 4, "summaries": 2, "percent": 50}
    assert report["legacy_exceptions"][0]["path"].endswith("10.0.3-command-center")
    assert "legacy_pairing_exception" in codes(report, "warnings")
    assert "archived_pairing_debt" in codes(report, "warnings")


def test_archived_and_human_uat_debt_remain_visible(tmp_path: Path) -> None:
    root = make_tree(tmp_path, debt=False)
    write(
        root,
        ".planning/milestones/v1.0.5-phases/10.0.2-installer/10.0.2-VERIFICATION.md",
        """---
status: human_needed
---
- [ ] Confirm Docker path
environment-gated
""",
    )
    report = planning_integrity.inspect(root)

    assert report["integrity_ok"] is True
    assert report["production_ready"] is True
    assert report["verification_debt"] == [
        {
            "path": "milestones/v1.0.5-phases/10.0.2-installer/10.0.2-VERIFICATION.md",
            "status": "human_needed",
            "severity": "environment_gated",
            "items": 1,
            "archived": True,
        }
    ]


def test_canonical_uat_items_do_not_double_count_mirrored_table(tmp_path: Path) -> None:
    root = make_tree(tmp_path, debt=False)
    write(
        root,
        ".planning/phases/10.8-cutover/10.8-UAT.md",
        """---
status: partial
---
| Area | Result |
|---|---|
| Recovery | pending |
| Rollback | pending |

### 1. Recovery
expected: Gateway resumes safely.
result: pending

### 2. Rollback
expected: Candidate restores exactly.
result: pending
""",
    )

    report = planning_integrity.inspect(root)
    record = next(item for item in report["verification_debt"] if item["path"].endswith("10.8-UAT.md"))
    assert record["items"] == 2


def test_stale_root_handoff_and_broken_resume_are_structural_errors(tmp_path: Path) -> None:
    root = make_tree(tmp_path, debt=False)
    write(root, ".planning/HANDOFF.json", '{"next": "old"}')
    state_path = root / ".planning/STATE.md"
    state_path.write_text(
        state_path.read_text(encoding="utf-8").replace(
            ".planning/phases/10.8-cutover/.continue-here.md", ".planning/phases/10.8-cutover/missing.md"
        ),
        encoding="utf-8",
    )
    report = planning_integrity.inspect(root)

    assert {"multiple_handoffs", "stale_handoff", "resume_broken"} <= codes(report, "errors")
    assert report["handoff"]["resume_exists"] is False


def test_canonical_root_checkpoint_pointer_is_not_competing(tmp_path: Path) -> None:
    root = make_tree(tmp_path, debt=False)
    pointer = ".planning/phases/10.8-cutover/.continue-here.md"
    write(root, ".planning/.continue-here.md", f"Resume File: `{pointer}`\n")
    report = planning_integrity.inspect(root)

    assert "multiple_handoffs" not in codes(report, "errors")


def test_state_contract_and_line_ceiling(tmp_path: Path) -> None:
    root = make_tree(tmp_path, debt=False)
    state_path = root / ".planning/STATE.md"
    state = state_path.read_text(encoding="utf-8").replace("last_activity_desc: Stabilizing\n", "")
    state_path.write_text(state + ("extra\n" * 130), encoding="utf-8")
    report = planning_integrity.inspect(root)

    assert "state_field_missing" in codes(report, "errors")
    assert "state_too_long" in codes(report, "errors")


def test_human_output_is_compact_and_stable(tmp_path: Path) -> None:
    report = planning_integrity.inspect(make_tree(tmp_path))
    output = planning_integrity.render_human(report)

    assert output.splitlines()[:3] == [
        "Planning integrity",
        "  integrity_ok: true",
        "  production_ready: false",
    ]
    assert "active_progress: 1/2 (50%)" in output
