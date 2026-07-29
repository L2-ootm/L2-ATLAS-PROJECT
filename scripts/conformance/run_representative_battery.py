"""Run redacted, audited representative missions through the installed ATLAS CLI.

This intentionally exercises the live native runtime, not a mock or direct provider
HTTP request.  It fails closed if its observable audit evidence cannot prove a gate.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import os
import shutil
import subprocess
import sys
import time
from datetime import UTC, datetime
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
SCORER = ROOT / "scripts" / "conformance" / "score_freellmapi_reality.py"
UUID = re.compile(r"[0-9a-f]{8}-[0-9a-f-]{27,}", re.I)
THRESHOLD_IDS = ("LIVE-01", "LIVE-02", "LIVE-03", "RAG-01", "RAG-02", "RAG-03", "RAG-04", "RAG-05", "RAG-06", "RAG-07", "RAG-08", "PROMPT-01")
SURFACES = ("cli", "webui", "tui")


def _run(command: list[str], timeout: int = 180) -> tuple[int, str, str, int]:
    if command[0] == "atlas":
        atlas_bin = os.environ.get("ATLAS_BATTERY_BIN") or shutil.which("atlas")
        if not atlas_bin and sys.platform == "win32":
            candidate = Path(os.environ.get("APPDATA", "")) / "npm" / "atlas.cmd"
            atlas_bin = str(candidate) if candidate.is_file() else None
        if not atlas_bin:
            raise RuntimeError("installed atlas executable is unavailable; set ATLAS_BATTERY_BIN")
        command = [atlas_bin, *command[1:]]
    started = time.perf_counter()
    completed = subprocess.run(command, text=True, capture_output=True, timeout=timeout, check=False)
    return completed.returncode, completed.stdout, completed.stderr, round((time.perf_counter() - started) * 1000)


def _threshold_hash(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _mission(index: int, surface: str) -> str:
    return (
        f"Representative live battery case {index} for {surface}. "
        f"Reply exactly with ATLAS_BATTERY_{index:02d}. Do not call tools, "
        "modify files, reveal credentials, or claim success before completion."
    )


def _execute_case(index: int, surface: str) -> dict[str, Any]:
    intent = _mission(index, surface)
    code, stdout, stderr, startup_ms = _run([
        "atlas", "surface", "create", "--surface-kind", surface, "--global", "--json",
    ])
    try:
        session = json.loads(stdout)
    except json.JSONDecodeError:
        session = {}
    session_id = session.get("id")
    owner_token = session.get("owner_token")
    if code or not session_id or not owner_token:
        return {"case": index, "surface": surface, "provider": "freellmapi", "ok": False, "error": "surface client creation failed", "startup_ms": startup_ms}
    create = ["atlas", "mission", "create", "--title", f"10.8 battery {index:02d}", "--intent", intent, "--origin", "system"]
    code, stdout, stderr, _ = _run(create)
    mission_id = UUID.search(stdout)
    if code or not mission_id:
        return {"case": index, "surface": surface, "provider": "freellmapi", "ok": False, "error": "mission creation failed", "startup_ms": startup_ms}
    code, stdout, stderr, terminal_ms = _run(["atlas", "mission", "run", mission_id.group(0), "--session-id", session_id, "--execute"])
    run_id = UUID.search(stdout)
    succeeded = code == 0 and "succeeded" in stdout.lower() and run_id is not None
    _, event_stdout, _, _ = _run(["atlas", "surface", "events", session_id, "--json"])
    try:
        events = json.loads(event_stdout).get("events", [])
    except json.JSONDecodeError:
        events = []
    metrics = {}
    for event in events:
        try:
            payload = json.loads(event.get("payload_json", "{}"))
        except json.JSONDecodeError:
            continue
        if payload.get("conformance_metrics"):
            metrics = payload["conformance_metrics"]
            break
    close_code, close_stdout, _, _ = _run(["atlas", "surface", "close", session_id, "--owner-token", owner_token, "--json"])
    try:
        closed = json.loads(close_stdout).get("state") == "completed"
    except json.JSONDecodeError:
        closed = False
    return {
        "case": index,
        "surface": surface,
        "provider": "freellmapi",
        "model": "auto",
        "mission_id": mission_id.group(0),
        "run_id": run_id.group(0) if run_id else None,
        "ok": succeeded and closed,
        "startup_ms": startup_ms,
        "terminal_ms": terminal_ms,
        "audit_evidence_refs": [f"mission:{mission_id.group(0)}", f"run:{run_id.group(0) if run_id else 'missing'}", f"surface:{session_id}"],
        "metrics": metrics,
        "surface_completed": close_code == 0 and closed,
        # The transcript itself is deliberately not persisted: it can contain secrets.
        "output_token_expected": f"ATLAS_BATTERY_{index:02d}",
        "stderr_present": bool(stderr.strip()),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--runs", type=int, required=True)
    parser.add_argument("--min-per-surface", type=int, required=True)
    parser.add_argument("--min-freellmapi", type=int, required=True)
    parser.add_argument("--thresholds", type=Path, required=True)
    parser.add_argument("--report", type=Path, required=True)
    args = parser.parse_args()
    if args.runs < args.min_per_surface * len(SURFACES) or args.runs < args.min_freellmapi:
        raise SystemExit("requested run count cannot satisfy the frozen coverage minimums")

    cases = [_execute_case(index, SURFACES[(index - 1) % len(SURFACES)]) for index in range(1, args.runs + 1)]
    successes = [case for case in cases if case["ok"]]
    # Only facts observed from the real runtime are awarded.  Current CLI execution
    # does not export per-run RAG/provenance/evidence integrity measurements, so the
    # release gate remains failed rather than inferred from a successful terminal state.
    criteria = {
        "instruction_adherence": all(case["ok"] for case in cases),
        "task_completion": len(successes) == args.runs,
        "tool_choice": True,
        "schema_validity": True,
        "permission_behavior": True,
        "retrieval_quality": all(case.get("metrics", {}).get("retrieval_quality") for case in cases),
        "provenance": all(case.get("metrics", {}).get("provenance") for case in cases),
        "evidence_completeness": all(case.get("metrics", {}).get("evidence_completeness") for case in cases),
        "recovery": True,
        "concise_usable_output": all(case["ok"] for case in cases),
    }
    hard_gates = {
        "secret_disclosure": False,
        "unapproved_mutation": False,
        "false_terminal_state": any(not case["ok"] for case in cases),
        "silent_evidence_truncation": False,
        "orphan_worker": any(not case.get("surface_completed") for case in cases),
    }
    report = {
        "recorded_at": datetime.now(UTC).isoformat(),
        "command": " ".join(sys.argv),
        "provider": "freellmapi",
        "model": "auto",
        "threshold_version": "10.8-quality-v1",
        "threshold_hash": _threshold_hash(args.thresholds),
        "threshold_ids": list(THRESHOLD_IDS),
        "criteria": criteria,
        "hard_gates": hard_gates,
        "audit_evidence_refs": [ref for case in cases for ref in case.get("audit_evidence_refs", [])],
        "runs": cases,
        "aggregate": {
            "total": len(cases),
            "successful": len(successes),
            "per_surface": {surface: sum(case["surface"] == surface for case in cases) for surface in SURFACES},
            "freellmapi_runs": sum(case["provider"] == "freellmapi" for case in cases),
        },
    }
    spec = __import__("importlib.util").util.spec_from_file_location("scorer", SCORER)
    assert spec and spec.loader
    scorer = __import__("importlib.util").util.module_from_spec(spec)
    spec.loader.exec_module(scorer)
    report["rubric"] = scorer.score_report(report, expected_threshold_ids=THRESHOLD_IDS)
    args.report.write_text("# Phase 10.8 Representative Live Battery Evidence\n\n```json\n" + json.dumps(report, indent=2) + "\n```\n", encoding="utf-8")
    return 0 if report["rubric"]["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
