#!/usr/bin/env python3
"""Read-only integrity and production-readiness checks for ``.planning``.

The checker deliberately has no YAML dependency.  STATE's front matter is a
small scalar contract; treating it as such prevents this diagnostic from
becoming a second planning authority.
"""

from __future__ import annotations

import argparse
import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


SCHEMA_VERSION = 1
STATE_FIELDS = (
    "milestone",
    "current_phase",
    "current_phase_name",
    "current_plan",
    "total_plans_in_phase",
    "status",
    "progress",
    "paused_at",
    "last_activity",
    "last_activity_desc",
)
DEBT_STATUSES = {"human_needed", "partial", "gaps_found", "pending", "blocked"}
PLAN_RE = re.compile(r"^(?P<base>.+-)?PLAN\.md$", re.IGNORECASE)
SUMMARY_RE = re.compile(r"^(?P<base>.+-)?SUMMARY\.md$", re.IGNORECASE)
PHASE_RE = re.compile(r"^(?P<phase>\d+(?:\.\d+)*)-(?P<name>.+)$")
LEGACY_PAIRING_EXCEPTIONS = {"10.0.3-command-center"}


def _scalar(value: str) -> Any:
    value = value.strip()
    if len(value) >= 2 and value[0] == value[-1] and value[0] in "\"'":
        value = value[1:-1]
    lowered = value.lower()
    if lowered in {"null", "none", "~"}:
        return None
    if lowered in {"true", "false"}:
        return lowered == "true"
    if re.fullmatch(r"-?\d+", value):
        return int(value)
    return value


def _frontmatter(text: str) -> dict[str, Any]:
    lines = text.splitlines()
    if not lines or lines[0].strip() != "---":
        return {}
    result: dict[str, Any] = {}
    for line in lines[1:]:
        if line.strip() == "---":
            break
        # Only top-level scalar keys are part of the STATE/UAT contract.
        if line[:1].isspace() or ":" not in line or line.lstrip().startswith("#"):
            continue
        key, value = line.split(":", 1)
        result[key.strip()] = _scalar(value)
    return result


def _phase_token(name: str) -> str | None:
    match = PHASE_RE.match(name)
    return match.group("phase") if match else None


def _pair_sets(directory: Path) -> tuple[set[str], set[str]]:
    plans: set[str] = set()
    summaries: set[str] = set()
    for item in directory.iterdir():
        if not item.is_file():
            continue
        plan = PLAN_RE.match(item.name)
        summary = SUMMARY_RE.match(item.name)
        if plan:
            plans.add((plan.group("base") or "").rstrip("-"))
        elif summary:
            summaries.add((summary.group("base") or "").rstrip("-"))
    return plans, summaries


def _progress(plans: int, summaries: int) -> dict[str, int]:
    return {
        "plans": plans,
        "summaries": summaries,
        "percent": round((summaries / plans) * 100) if plans else 0,
    }


def _relative(path: Path, planning: Path) -> str:
    return path.relative_to(planning).as_posix()


def _roadmap_truth(text: str) -> tuple[str | None, set[str], dict[str, str]]:
    active: str | None = None
    for line in text.splitlines():
        if "🔨" in line or re.search(r"\bACTIVE\b", line, re.IGNORECASE):
            match = re.search(r"\b(v\d+(?:\.\d+)*)\b", line)
            if match:
                active = match.group(1)
                break

    active_tokens: set[str] = set()
    if active:
        heading = re.compile(
            rf"^###(?!#).*\b{re.escape(active)}\b.*(?:ACTIVE|🔨)", re.IGNORECASE
        )
        in_active = False
        for line in text.splitlines():
            if heading.search(line):
                in_active = True
                continue
            if in_active and re.match(r"^###(?!#)\s", line):
                break
            if in_active:
                match = re.match(r"^####\s+Phase\s+(\d+(?:\.\d+)*)\b", line)
                if match:
                    active_tokens.add(match.group(1))

    table_map: dict[str, str] = {}
    for line in text.splitlines():
        match = re.match(
            r"^\|\s*(\d+(?:\.\d+)*)(?:\s+[^|]*)?\|\s*(v\d+(?:\.\d+)*)\s*\|",
            line,
        )
        if match:
            table_map[match.group(1)] = match.group(2)
    return active, active_tokens, table_map


def _resume_path(state_text: str, state: dict[str, Any]) -> str | None:
    match = re.search(
        r"(?im)^\s*(?:[-*]\s*)?\*{0,2}Resume File(?::\*{0,2}|\*{0,2}:)\s*`?([^`\n]+?)`?\s*$",
        state_text,
    )
    if match:
        return match.group(1).strip()
    paused = state.get("paused_at")
    if isinstance(paused, str) and ("/" in paused or "\\" in paused):
        return paused
    return None


def _resolve_resume(root: Path, planning: Path, raw: str) -> Path:
    candidate = Path(raw.replace("\\", "/"))
    if candidate.is_absolute():
        return candidate
    if candidate.parts and candidate.parts[0] == ".planning":
        return root / candidate
    return planning / candidate


def _debt_severity(text: str, *, archived: bool, current_phase: bool) -> str:
    lowered = text.lower()
    if "release-blocking" in lowered or "release blocking" in lowered:
        return "blocking"
    if "environment-gated" in lowered or "environment gated" in lowered:
        return "environment_gated"
    if current_phase and not archived:
        return "blocking"
    return "advisory"


def _verification_debt(planning: Path, current_phase: str | None) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    candidates = sorted(
        {
            *planning.rglob("*UAT*.md"),
            *planning.rglob("*VERIFICATION*.md"),
            *planning.rglob("*verification*debt*.md"),
        },
        key=lambda item: item.as_posix().lower(),
    )
    for path in candidates:
        text = path.read_text(encoding="utf-8", errors="replace")
        meta = _frontmatter(text)
        scan_text = re.sub(r"\A---\s*\n[\s\S]*?\n---\s*\n?", "", text, count=1)
        status = str(meta.get("status", "")).lower()
        pending_results = len(
            re.findall(
                r"(?im)^\s*(?:result|decision)\s*:\s*(?:pending|blocked|human_needed|not[_ -]?run)\b",
                scan_text,
            )
        )
        human_verification_items = len(
            re.findall(r"(?m)^\s*-\s+(?:test|name):\s+.+$", text)
        )
        unchecked = len(re.findall(r"(?m)^\s*[-*]\s*\[ \]\s+", scan_text))
        pending_words = len(re.findall(r"(?im)^\s*\|[^\n|]+\|\s*(?:pending|blocked)\s*\|", scan_text))
        # Prefer one canonical machine-readable representation. Human tables
        # and checklists often mirror the same pending tests and must not
        # inflate debt counts by double-counting the mirrors.
        if pending_results:
            item_count = pending_results
        elif human_verification_items:
            item_count = human_verification_items
        else:
            item_count = max(unchecked, pending_words)
        if status not in DEBT_STATUSES and item_count == 0:
            continue
        relative = _relative(path, planning)
        archived = relative.startswith("milestones/") or "/milestones/" in relative
        in_current = bool(current_phase and f"/{current_phase}-" in f"/{relative}")
        records.append(
            {
                "path": relative,
                "status": status or "pending",
                "severity": _debt_severity(text, archived=archived, current_phase=in_current),
                "items": item_count,
                "archived": archived,
            }
        )
    return records


def inspect(root: str | Path) -> dict[str, Any]:
    """Return the stable planning-integrity report for *root*."""

    root_path = Path(root).resolve()
    planning = root_path if root_path.name == ".planning" else root_path / ".planning"
    if planning == root_path:
        root_path = planning.parent
    errors: list[dict[str, str]] = []
    warnings: list[dict[str, str]] = []
    legacy: list[dict[str, str]] = []

    def problem(target: list[dict[str, str]], code: str, message: str) -> None:
        target.append({"code": code, "message": message})

    state_path = planning / "STATE.md"
    roadmap_path = planning / "ROADMAP.md"
    if not planning.is_dir():
        problem(errors, "planning_missing", f"Planning directory does not exist: {planning}")
        return _report(None, None, 0, 0, 0, 0, [], errors, warnings, legacy, {})

    state_text = state_path.read_text(encoding="utf-8", errors="replace") if state_path.exists() else ""
    roadmap_text = roadmap_path.read_text(encoding="utf-8", errors="replace") if roadmap_path.exists() else ""
    if not state_path.exists():
        problem(errors, "state_missing", "STATE.md is missing")
    if not roadmap_path.exists():
        problem(errors, "roadmap_missing", "ROADMAP.md is missing")

    state = _frontmatter(state_text)
    for field in STATE_FIELDS:
        if field not in state or state[field] in (None, ""):
            problem(errors, "state_field_missing", f"STATE.md is missing canonical field: {field}")
    line_count = len(state_text.splitlines())
    if line_count > 120:
        problem(errors, "state_too_long", f"STATE.md has {line_count} lines; maximum is 120")

    last_activity = state.get("last_activity")
    if isinstance(last_activity, str):
        try:
            parsed = datetime.fromisoformat(last_activity.replace("Z", "+00:00"))
            age = (datetime.now(timezone.utc).date() - parsed.date()).days
            if age > 30:
                problem(warnings, "state_stale", f"STATE.md last_activity is {age} days old")
            elif age < -1:
                problem(errors, "state_future", "STATE.md last_activity is in the future")
        except ValueError:
            problem(errors, "state_date_invalid", "STATE.md last_activity is not an ISO date")

    milestone = str(state.get("milestone")) if state.get("milestone") is not None else None
    current_phase = str(state.get("current_phase")) if state.get("current_phase") is not None else None
    roadmap_milestone, roadmap_tokens, table_map = _roadmap_truth(roadmap_text)
    if milestone and roadmap_milestone and milestone != roadmap_milestone:
        problem(errors, "milestone_mismatch", f"STATE milestone {milestone} != ROADMAP active milestone {roadmap_milestone}")
    active_milestone = roadmap_milestone or milestone

    phases_root = planning / "phases"
    live_dirs = sorted((item for item in phases_root.iterdir() if item.is_dir()), key=lambda p: p.name) if phases_root.is_dir() else []
    token_dirs: dict[str, list[Path]] = {}
    for directory in live_dirs:
        token = _phase_token(directory.name)
        if token:
            token_dirs.setdefault(token, []).append(directory)
    for token, directories in token_dirs.items():
        if len(directories) > 1:
            problem(errors, "duplicate_live_phase", f"Live phase token {token} appears in: {', '.join(p.name for p in directories)}")
        if roadmap_tokens and token not in roadmap_tokens:
            problem(errors, "inactive_phase_live", f"Live phase {directories[0].name} is outside the active ROADMAP milestone")
        mapped = table_map.get(token)
        if mapped and active_milestone and mapped != active_milestone:
            problem(errors, "roadmap_phase_mismatch", f"Live phase {token} belongs to {mapped}, not {active_milestone}")

    active_plans = active_summaries = 0
    incomplete: list[tuple[Path, str]] = []
    for directory in live_dirs:
        plans, summaries = _pair_sets(directory)
        active_plans += len(plans)
        active_summaries += len(summaries)
        for base in sorted(summaries - plans):
            problem(errors, "orphan_live_summary", f"{_relative(directory, planning)} has SUMMARY without PLAN: {base or 'bare'}")
        for base in sorted(plans - summaries):
            incomplete.append((directory, base))

    expected_plan = state.get("current_plan")
    expected_missing = False
    for directory, base in incomplete:
        token = _phase_token(directory.name)
        base_plan = re.search(r"(?:^|-)(\d+)$", base)
        matches_plan = expected_plan is not None and base_plan and int(base_plan.group(1)) == int(expected_plan)
        if token == current_phase and matches_plan:
            expected_missing = True
        else:
            problem(errors, "unpaired_live_plan", f"{_relative(directory, planning)} has PLAN without SUMMARY: {base or 'bare'}")
    if len(incomplete) > 1 or (incomplete and not expected_missing):
        problem(errors, "active_phase_ambiguous", "Live planning root does not have exactly one attributable active plan")
    if str(state.get("status", "")).lower() in {"in_progress", "paused"} and not incomplete:
        problem(warnings, "active_plan_complete", "STATE is active but every live PLAN has a SUMMARY")

    current_dirs = token_dirs.get(current_phase or "", [])
    if current_phase and len(current_dirs) != 1:
        problem(errors, "current_phase_resolution", f"STATE current phase {current_phase} resolves to {len(current_dirs)} live directories")
    elif current_dirs:
        plans, summaries = _pair_sets(current_dirs[0])
        total = state.get("total_plans_in_phase")
        if isinstance(total, int) and total != len(plans):
            problem(errors, "phase_plan_count_mismatch", f"STATE total_plans_in_phase {total} != live count {len(plans)}")

    calculated = _progress(active_plans, active_summaries)
    progress = state.get("progress")
    if isinstance(progress, int) and progress != calculated["percent"]:
        problem(errors, "progress_mismatch", f"STATE progress {progress} != active milestone progress {calculated['percent']}")

    resume = _resume_path(state_text, state)
    phase_checkpoints = sorted(phases_root.glob("*/.continue-here.md")) if phases_root.is_dir() else []
    current_checkpoints = [p for p in phase_checkpoints if _phase_token(p.parent.name) == current_phase]
    root_handoffs = [p for p in (planning / "HANDOFF.json", planning / ".continue-here.md") if p.exists()]
    root_pointer = planning / ".continue-here.md"
    canonical_pointer = False
    if root_pointer.exists() and len(current_checkpoints) == 1:
        pointer_text = root_pointer.read_text(encoding="utf-8", errors="replace")
        target_relative = _relative(current_checkpoints[0], planning)
        canonical_pointer = (
            target_relative in pointer_text.replace("\\", "/")
            or pointer_text == current_checkpoints[0].read_text(encoding="utf-8", errors="replace")
        )
    competing_root = (planning / "HANDOFF.json").exists() or (root_pointer.exists() and not canonical_pointer)
    if len(root_handoffs) > 1 or (competing_root and current_checkpoints):
        problem(errors, "multiple_handoffs", "Competing root and phase-local handoffs exist")
    if (planning / "HANDOFF.json").exists() and current_checkpoints:
        problem(errors, "stale_handoff", "HANDOFF.json shadows the current phase checkpoint")
    stale_checkpoints = [p for p in phase_checkpoints if p not in current_checkpoints]
    if stale_checkpoints:
        problem(errors, "stale_checkpoint", f"Non-current phase checkpoints: {', '.join(_relative(p, planning) for p in stale_checkpoints)}")
    if current_phase and not current_checkpoints and not (planning / ".continue-here.md").exists():
        problem(errors, "checkpoint_missing", f"Current phase {current_phase} has no checkpoint")
    resume_exists = None
    if not resume:
        problem(errors, "resume_missing", "STATE Session has no Resume File")
    else:
        resolved = _resolve_resume(root_path, planning, resume)
        resume_exists = resolved.is_file()
        if not resume_exists:
            problem(errors, "resume_broken", f"STATE Resume File does not exist: {resume}")

    archive_dirs: list[Path] = []
    milestones = planning / "milestones"
    if milestones.is_dir():
        for archive in sorted(milestones.glob("*-phases")):
            archive_dirs.extend(item for item in archive.iterdir() if item.is_dir())
    portfolio_plans, portfolio_summaries = active_plans, active_summaries
    for directory in sorted(archive_dirs, key=lambda p: p.as_posix()):
        plans, summaries = _pair_sets(directory)
        portfolio_plans += len(plans)
        portfolio_summaries += len(summaries)
        missing = sorted(plans - summaries)
        orphaned = sorted(summaries - plans)
        if not missing and not orphaned:
            continue
        relative = _relative(directory, planning)
        if (
            directory.name in LEGACY_PAIRING_EXCEPTIONS
            and missing == [""]
            and orphaned in ([], ["SESSION"])
        ):
            item = {"path": relative, "reason": "bare PLAN.md is historically represented by SESSION-SUMMARY.md"}
            legacy.append(item)
            problem(warnings, "legacy_pairing_exception", f"Archived legacy pairing exception: {relative}")
        else:
            problem(warnings, "archived_pairing_debt", f"Archived PLAN/SUMMARY debt in {relative}")

    debt = _verification_debt(planning, current_phase)
    handoff = {
        "resume_file": resume,
        "resume_exists": resume_exists,
        "current_phase_checkpoints": [_relative(p, planning) for p in current_checkpoints],
        "root_handoffs": [_relative(p, planning) for p in root_handoffs],
    }
    return _report(
        active_milestone,
        current_phase,
        active_plans,
        active_summaries,
        portfolio_plans,
        portfolio_summaries,
        debt,
        errors,
        warnings,
        legacy,
        handoff,
    )


def _report(
    milestone: str | None,
    phase: str | None,
    active_plans: int,
    active_summaries: int,
    portfolio_plans: int,
    portfolio_summaries: int,
    debt: list[dict[str, Any]],
    errors: list[dict[str, str]],
    warnings: list[dict[str, str]],
    legacy: list[dict[str, str]],
    handoff: dict[str, Any],
) -> dict[str, Any]:
    errors.sort(key=lambda item: (item["code"], item["message"]))
    warnings.sort(key=lambda item: (item["code"], item["message"]))
    integrity_ok = not errors
    production_ready = integrity_ok and not any(item["severity"] == "blocking" for item in debt)
    return {
        "schema_version": SCHEMA_VERSION,
        "integrity_ok": integrity_ok,
        "ok": integrity_ok,
        "production_ready": production_ready,
        "errors": errors,
        "warnings": warnings,
        "active_milestone": milestone,
        "current_phase": phase,
        "active_progress": _progress(active_plans, active_summaries),
        "portfolio_progress": _progress(portfolio_plans, portfolio_summaries),
        "verification_debt": debt,
        "handoff": handoff,
        "legacy_exceptions": legacy,
    }


def render_human(report: dict[str, Any]) -> str:
    """Render a stable, compact operator summary."""

    active = report["active_progress"]
    portfolio = report["portfolio_progress"]
    lines = [
        "Planning integrity",
        f"  integrity_ok: {str(report['integrity_ok']).lower()}",
        f"  production_ready: {str(report['production_ready']).lower()}",
        f"  active: {report['active_milestone'] or '-'} / phase {report['current_phase'] or '-'}",
        f"  active_progress: {active['summaries']}/{active['plans']} ({active['percent']}%)",
        f"  portfolio_progress: {portfolio['summaries']}/{portfolio['plans']} ({portfolio['percent']}%)",
        f"  verification_debt: {len(report['verification_debt'])}",
        f"  errors: {len(report['errors'])}",
        f"  warnings: {len(report['warnings'])}",
    ]
    for kind in ("errors", "warnings"):
        for item in report[kind]:
            lines.append(f"  {kind[:-1]}[{item['code']}]: {item['message']}")
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", default=Path(__file__).resolve().parents[1], help="repository or .planning root")
    parser.add_argument("--json", action="store_true", help="emit stable JSON instead of human output")
    parser.add_argument(
        "--format",
        choices=("human", "json"),
        help="explicit output format; --format json is equivalent to --json",
    )
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--strict", action="store_true", help="fail on structural integrity errors")
    mode.add_argument("--production", action="store_true", help="fail on structural errors or blocking verification debt")
    args = parser.parse_args(argv)
    report = inspect(args.root)
    if args.json or args.format == "json":
        print(json.dumps(report, indent=2, sort_keys=True))
    else:
        print(render_human(report))
    if args.production:
        return 0 if report["production_ready"] else 2
    if args.strict:
        return 0 if report["integrity_ok"] else 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
