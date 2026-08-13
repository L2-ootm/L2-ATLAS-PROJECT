"""Did the run verify its own work, or only claim it did?

Every terminal run today reports success on one fact: the harness said the
conversation completed. `NativeAtlasAgent._map_result` is explicit about it —
"final response reflects the agent's own account of its work" is filed as an
*inference*, not evidence, because ATLAS never checked. That is honest labelling
of a blind spot, not a fix for it.

This module closes it from the only source that cannot be talked around: the
run's own audit trail. Tool calls are recorded before ATLAS asks the model
anything about them, so `tool_requested`/`tool_call` (arguments) joined with
`tool_completed`/`tool_failed` (outcome) is a record of what the run *did*. From
that record the gate answers one question per run:

    did this run change state, and did it then check that the change worked?

Four verdicts, all facts rather than judgements:

  no_mutations   nothing observable changed — there was nothing to verify.
  verified       state changed and at least one strong check (tests, typecheck,
                 lint, build) ran and passed afterwards.
  contradicted   state changed, strong checks ran, and every one of them failed.
                 A run in this state that reports success is making a false claim.
  unverified     state changed and no strong check ran at all.

Deliberately NOT done here: the verdict does not change `RunOutcome.status`.
A heuristic classifier on its first day must not be able to fail runs that
worked — that is the same unverified self-modification this gate exists to
catch. It writes an audit event, extends the claim taxonomy (which
`run_executor` already funnels into the compounding-loop observation and the
brain graph, so the *next* run inherits the finding), and prefixes the summary
on `contradicted`. Turning `contradicted` into a failed run is a later change,
justified by what this one observes in anger.

Cross-runtime by construction: native emits `tool_requested`, claude_code and
codex emit `tool_call`; all three emit `tool_completed`/`tool_failed`. The tool
vocabularies differ (`terminal`/`Bash`/`shell`, `write_file`/`Write`/`apply_patch`)
so command and path extraction is normalised per runtime here rather than in
each agent.

Set ATLAS_VERIFICATION_GATE=0 to disable.
"""

from __future__ import annotations

import json
import logging
import os
import re
import sqlite3
import threading
from dataclasses import dataclass
from typing import Any, Iterable, Literal, Optional

logger = logging.getLogger(__name__)

GATE_VERSION = "2026-08-13"

VerdictState = Literal["no_mutations", "verified", "contradicted", "unverified"]

_MAX_LISTED = 5
_SUMMARY_CAP = 2000


# -- tool vocabulary ---------------------------------------------------------
# One name per concept per runtime. A tool absent from every set below is
# treated as neither mutating nor verifying, which is the safe default: the
# gate under-reports rather than inventing mutations it cannot see.

_SHELL_TOOLS = frozenset({"terminal", "Bash", "shell", "run_command"})
_WRITE_TOOLS = frozenset(
    {"write_file", "patch", "Write", "Edit", "MultiEdit", "NotebookEdit", "apply_patch"}
)
_READ_TOOLS = frozenset({"read_file", "Read", "view_file"})

# ATLAS's own tools. The scratchpad is the agent's working memory: writing a
# note is not a state change anyone needs verified. `materialize` is, because it
# puts an executable file on disk.
_ATLAS_MUTATING_OPS = {
    "atlas_scratchpad": frozenset({"materialize"}),
    "atlas_module": frozenset({"record_write", "record_create", "record_update", "install"}),
    "atlas_graph": frozenset({"write", "upsert", "link", "delete"}),
}


# -- command classification --------------------------------------------------
# Anchored to executable position (leading, or after a shell separator) so a
# command that merely *mentions* pytest in a grep pattern is not read as a
# test run. Same discipline as hardline_policy.py.

_ANCHOR = r"(?:^|[;&|]\s*|&&\s*|\|\|\s*)(?:sudo\s+)?(?:\S*[/\\])?"

_STRONG_SIGNALS: tuple[tuple[str, re.Pattern[str]], ...] = (
    ("tests", re.compile(_ANCHOR + r"(?:pytest|py\.test)\b", re.IGNORECASE)),
    ("tests", re.compile(r"\bpython3?(?:\.exe)?\s+-m\s+pytest\b", re.IGNORECASE)),
    ("tests", re.compile(r"\b(?:npm|pnpm|yarn|bun)\s+(?:run\s+)?test\b", re.IGNORECASE)),
    ("tests", re.compile(r"\bcargo\s+(?:test|nextest)\b", re.IGNORECASE)),
    ("tests", re.compile(r"\bgo\s+test\b", re.IGNORECASE)),
    ("tests", re.compile(r"\b(?:dotnet|mvn|gradlew?)\s+test\b", re.IGNORECASE)),
    ("tests", re.compile(r"\bmake\s+(?:test|check)\b", re.IGNORECASE)),
    ("typecheck", re.compile(_ANCHOR + r"(?:mypy|pyright|tsc)\b", re.IGNORECASE)),
    (
        "lint",
        re.compile(_ANCHOR + r"(?:ruff|eslint|flake8|golangci-lint)\b", re.IGNORECASE),
    ),
    ("lint", re.compile(r"\bcargo\s+clippy\b", re.IGNORECASE)),
    (
        "build",
        re.compile(
            r"\b(?:cargo\s+(?:build|check)|go\s+build|make\s+build"
            r"|(?:npm|pnpm|yarn|bun)\s+run\s+build)\b",
            re.IGNORECASE,
        ),
    ),
)

# Weak signals are recorded and reported but never on their own promote a run to
# `verified`. `git status` runs in a large share of sessions; if it counted, the
# gate would agree with every claim it was built to question.
_WEAK_SIGNALS: tuple[tuple[str, re.Pattern[str]], ...] = (
    ("review", re.compile(r"\bgit\s+(?:diff|status|show)\b", re.IGNORECASE)),
)

_MUTATING_COMMANDS: tuple[re.Pattern[str], ...] = (
    re.compile(_ANCHOR + r"(?:rm|mv|cp|mkdir|touch|chmod|chown|ln)\b", re.IGNORECASE),
    re.compile(
        r"\bgit\s+(?:commit|push|merge|rebase|reset|checkout|switch|apply|am"
        r"|cherry-pick|tag|clean|stash)\b",
        re.IGNORECASE,
    ),
    re.compile(
        r"\b(?:npm|pnpm|yarn|bun|pip|pip3|cargo|go)\s+"
        r"(?:i|install|add|remove|uninstall|get)\b",
        re.IGNORECASE,
    ),
    re.compile(r"\bsed\s+-i\b", re.IGNORECASE),
    re.compile(
        r"(?:^|[;&|]\s*)(?:New-Item|Set-Content|Add-Content|Out-File|Remove-Item"
        r"|Copy-Item|Move-Item|Rename-Item)\b",
        re.IGNORECASE,
    ),
    re.compile(r"\|\s*tee\b", re.IGNORECASE),
    # Output redirection to a real file. /dev/null, NUL and fd duplication
    # (2>&1) are discards, not writes.
    re.compile(r">>?\s*(?!\s*(?:/dev/null|&\d|NUL\b|nul\b))\S"),
)

# execute_code runs arbitrary code, so it is a mutation only when the code
# itself writes something. Treating every computation as a mutation would flag
# read-only analysis runs as unverified.
_MUTATING_CODE = re.compile(
    r"open\s*\([^)]*['\"][wax]|\.write_text\s*\(|\.write_bytes\s*\(|\bos\.(?:remove|rename|mkdir|makedirs)\b"
    r"|\bshutil\.(?:copy|move|rmtree)\b|\bPath\([^)]*\)\.(?:unlink|mkdir)\b",
    re.IGNORECASE,
)


@dataclass(frozen=True)
class ObservedCall:
    """One tool invocation as the audit trail recorded it."""

    tool: str
    args: dict[str, Any]
    failed: bool = False


@dataclass(frozen=True)
class VerificationVerdict:
    state: VerdictState
    mutations: tuple[str, ...] = ()
    signals: tuple[str, ...] = ()
    failed_signals: tuple[str, ...] = ()
    weak_signals: tuple[str, ...] = ()

    def as_payload(self) -> dict[str, Any]:
        return {
            "gate_version": GATE_VERSION,
            "state": self.state,
            "mutations": list(self.mutations[:_MAX_LISTED]),
            "mutation_count": len(self.mutations),
            "signals": list(self.signals),
            "failed_signals": list(self.failed_signals),
            "weak_signals": list(self.weak_signals),
        }


# -- extraction --------------------------------------------------------------


def _command_of(call: ObservedCall) -> str:
    """The shell command a call ran, normalised across runtimes."""
    if call.tool not in _SHELL_TOOLS:
        return ""
    raw = call.args.get("command")
    if isinstance(raw, list):  # codex passes argv
        raw = " ".join(str(part) for part in raw)
    if not isinstance(raw, str):
        return ""
    return raw.strip()


def _paths_of(call: ObservedCall) -> tuple[str, ...]:
    """Filesystem paths a call touched, normalised across runtimes."""
    paths: list[str] = []
    for key in ("path", "file_path", "filename", "notebook_path"):
        value = call.args.get(key)
        if isinstance(value, str) and value.strip():
            paths.append(value.strip())
    changes = call.args.get("changes")  # codex file_change
    if isinstance(changes, dict):
        paths.extend(str(key) for key in changes)
    elif isinstance(changes, list):
        for change in changes:
            if isinstance(change, dict):
                for key in ("path", "file_path"):
                    value = change.get(key)
                    if isinstance(value, str) and value.strip():
                        paths.append(value.strip())
    return tuple(paths)


def _normalise_path(path: str) -> str:
    return path.replace("\\", "/").rstrip("/").lower()


def _atlas_mutation(call: ObservedCall) -> Optional[str]:
    ops = _ATLAS_MUTATING_OPS.get(call.tool)
    if ops is None:
        return None
    op = str(call.args.get("op") or "").strip()
    return f"{call.tool}:{op}" if op in ops else None


def _signal_kinds(
    command: str, table: Iterable[tuple[str, re.Pattern[str]]]
) -> tuple[str, ...]:
    kinds: list[str] = []
    for kind, pattern in table:
        if kind not in kinds and pattern.search(command):
            kinds.append(kind)
    return tuple(kinds)


# -- classification ----------------------------------------------------------


def classify(calls: Iterable[ObservedCall]) -> VerificationVerdict:
    """Reduce a run's tool calls to one verdict. Pure; order matters.

    A verification signal only counts when it ran *after* a mutation — tests run
    before any change was made say nothing about the change.
    """
    mutations: list[str] = []
    signals: list[str] = []
    failed_signals: list[str] = []
    weak: list[str] = []
    written: set[str] = set()

    for call in calls:
        command = _command_of(call)
        paths = _paths_of(call)

        if command:
            strong = _signal_kinds(command, _STRONG_SIGNALS)
            if strong and mutations:
                target = failed_signals if call.failed else signals
                for kind in strong:
                    if kind not in target:
                        target.append(kind)
            if not strong:
                for kind in _signal_kinds(command, _WEAK_SIGNALS):
                    if mutations and kind not in weak:
                        weak.append(kind)
                if any(pattern.search(command) for pattern in _MUTATING_COMMANDS):
                    mutations.append(f"{call.tool}: {command[:120]}")
            continue

        if call.tool in _WRITE_TOOLS:
            for path in paths:
                written.add(_normalise_path(path))
            mutations.append(
                f"{call.tool}: {paths[0] if paths else '(unnamed target)'}"
            )
            continue

        if call.tool in _READ_TOOLS:
            # Reading back a file this run wrote is a real, if weak, check.
            if mutations and any(_normalise_path(p) in written for p in paths):
                if "read_back" not in weak:
                    weak.append("read_back")
            continue

        if call.tool == "execute_code":
            code = call.args.get("code")
            if isinstance(code, str) and _MUTATING_CODE.search(code):
                mutations.append("execute_code: code writes to disk")
            continue

        atlas = _atlas_mutation(call)
        if atlas:
            mutations.append(atlas)

    if not mutations:
        state: VerdictState = "no_mutations"
    elif signals:
        state = "verified"
    elif failed_signals:
        state = "contradicted"
    else:
        state = "unverified"

    return VerificationVerdict(
        state=state,
        mutations=tuple(mutations),
        signals=tuple(signals),
        failed_signals=tuple(failed_signals),
        weak_signals=tuple(weak),
    )


# -- audit trail reader ------------------------------------------------------

_ARG_EVENTS = ("tool_requested", "tool_call")
_OUTCOME_EVENTS = ("tool_completed", "tool_failed")


def _as_args(raw: Any) -> dict[str, Any]:
    """Tool arguments as a dict, however the trail happens to hold them.

    Runtimes differ (`arguments` vs `input`, dict vs pre-serialized string), and
    an over-cap audit preview can arrive as encoded JSON rather than a mapping.
    Treating any non-dict as "no arguments" loses the path or command, which is
    the only part the classifier needs.
    """
    if isinstance(raw, dict):
        return raw
    if isinstance(raw, str) and raw.lstrip().startswith("{"):
        try:
            parsed = json.loads(raw)
        except (TypeError, ValueError):
            return {}
        if isinstance(parsed, dict):
            return parsed
    return {}


def observed_calls(conn: sqlite3.Connection, run_id: str) -> tuple[ObservedCall, ...]:
    """Rebuild a run's tool calls from its audit events, in execution order.

    Arguments arrive on the request event and the outcome on a later event, so
    the two are joined on call id. A request with no outcome (the run died
    mid-call) is kept and treated as not-failed: it still happened.
    """
    rows = conn.execute(
        "SELECT event_type, tool_name, tool_call_id, data FROM audit_events "
        "WHERE run_id=? AND event_type IN (?,?,?,?) ORDER BY timestamp, rowid",
        (run_id, *_ARG_EVENTS, *_OUTCOME_EVENTS),
    ).fetchall()

    ordered: list[str] = []
    tools: dict[str, str] = {}
    args: dict[str, dict[str, Any]] = {}
    failed: dict[str, bool] = {}

    for index, (event_type, tool_name, tool_call_id, data) in enumerate(rows):
        payload: dict[str, Any] = {}
        if isinstance(data, str):
            try:
                parsed = json.loads(data)
                if isinstance(parsed, dict):
                    payload = parsed
            except (TypeError, ValueError):
                payload = {}
        call_id = str(
            tool_call_id
            or payload.get("call_id")
            or payload.get("tool_call_id")
            or f"anon-{index}"
        )
        if event_type in _ARG_EVENTS:
            name = str(tool_name or payload.get("tool") or payload.get("tool_name") or "")
            if not name:
                continue
            if call_id not in tools:
                ordered.append(call_id)
            tools[call_id] = name
            raw_args = payload.get("arguments")
            if raw_args is None:
                raw_args = payload.get("input")
            args[call_id] = _as_args(raw_args)
        elif payload.get("is_error") or event_type == "tool_failed":
            failed[call_id] = True

    return tuple(
        ObservedCall(tool=tools[call_id], args=args.get(call_id, {}), failed=failed.get(call_id, False))
        for call_id in ordered
    )


def classify_run(conn: sqlite3.Connection, run_id: str) -> VerificationVerdict:
    return classify(observed_calls(conn, run_id))


# -- claim taxonomy ----------------------------------------------------------


def _listed(items: tuple[str, ...]) -> str:
    shown = "; ".join(items[:_MAX_LISTED])
    extra = len(items) - _MAX_LISTED
    return f"{shown} (+{extra} more)" if extra > 0 else shown


def describe(verdict: VerificationVerdict) -> dict[str, tuple[str, ...]]:
    """Map a verdict onto the L2 claim taxonomy (evidence/inference/uncertainty)."""
    evidence: list[str] = []
    inferences: list[str] = []
    uncertainties: list[str] = []

    if verdict.state == "no_mutations":
        inferences.append(
            "no state-changing tool call observed in this run; nothing required verification"
        )
    elif verdict.state == "verified":
        evidence.append(
            f"verification ran after {len(verdict.mutations)} state change(s) and passed: "
            f"{', '.join(verdict.signals)}"
        )
        if verdict.failed_signals:
            uncertainties.append(
                f"some verification also failed: {', '.join(verdict.failed_signals)}"
            )
    elif verdict.state == "contradicted":
        uncertainties.append(
            f"run reported success but every verification it ran failed "
            f"({', '.join(verdict.failed_signals)}) after {len(verdict.mutations)} "
            f"state change(s): {_listed(verdict.mutations)}"
        )
    else:
        uncertainties.append(
            f"unverified: {len(verdict.mutations)} state change(s) with no test, build, "
            f"lint or typecheck run afterwards — {_listed(verdict.mutations)}"
        )

    if verdict.weak_signals and verdict.state != "no_mutations":
        inferences.append(
            f"weaker checks observed ({', '.join(verdict.weak_signals)}); "
            "these do not establish the change works"
        )

    return {
        "evidence": tuple(evidence),
        "inferences": tuple(inferences),
        "uncertainties": tuple(uncertainties),
    }


# -- gate --------------------------------------------------------------------


def verdict_for(conn: sqlite3.Connection, run_id: str) -> Optional[dict[str, Any]]:
    """The recorded verdict payload for a finished run, or None.

    Every consumer reads the durable audit event rather than re-deriving or
    parsing prose, so an operator surface and the record cannot drift apart.
    Returns None for `no_mutations` as well as for an unclassified run: callers
    display a verdict when there is something to answer for, and a read-only run
    is not a finding.
    """
    try:
        row = conn.execute(
            "SELECT data FROM audit_events WHERE run_id=? AND "
            "event_type='verification_verdict' ORDER BY timestamp DESC, rowid DESC LIMIT 1",
            (run_id,),
        ).fetchone()
    except Exception:  # noqa: BLE001 — a reporting read must never raise
        return None
    if not row or not row[0]:
        return None
    try:
        payload = json.loads(row[0])
    except (TypeError, ValueError):
        return None
    if not isinstance(payload, dict) or payload.get("state") == "no_mutations":
        return None
    return payload


def summarize(payload: dict[str, Any]) -> str:
    """One operator-readable line for a verdict payload."""
    state = payload.get("state")
    changes = payload.get("mutation_count") or 0
    if state == "verified":
        detail = f"passed {', '.join(payload.get('signals') or []) or 'a check'}"
    elif state == "contradicted":
        detail = (
            f"every check failed ({', '.join(payload.get('failed_signals') or [])}) "
            f"after {changes} change(s)"
        )
    elif state == "unverified":
        detail = f"{changes} change(s), no test/build/lint/typecheck ran after them"
    else:
        return str(state or "unknown")
    return f"{state} — {detail}"


def enabled() -> bool:
    return os.environ.get("ATLAS_VERIFICATION_GATE", "1").strip().lower() not in {
        "0",
        "false",
        "no",
        "off",
    }


def apply(
    conn: sqlite3.Connection,
    lock: threading.Lock,
    *,
    run_id: str,
    outcome: Any,
) -> Any:
    """Attach the verification verdict to a terminal RunOutcome.

    Fail-open by contract: this is a reporting layer, and a classifier bug must
    never change whether a run completes. Any error returns the outcome as-is.
    """
    if not enabled():
        return outcome
    try:
        from dataclasses import replace  # noqa: PLC0415

        from atlas_runtime import audit_service  # noqa: PLC0415

        verdict = classify_run(conn, run_id)
        claims = describe(verdict)
        try:
            audit_service.emit(
                conn,
                lock,
                run_id=run_id,
                event_type="verification_verdict",
                data=verdict.as_payload(),
            )
        except Exception as exc:  # noqa: BLE001 — the verdict still rides the outcome
            logger.debug("verification verdict audit emit failed for %s: %s", run_id, exc)

        summary = outcome.summary
        if verdict.state == "contradicted" and outcome.status == "succeeded":
            summary = f"[verification failed] {summary}"[:_SUMMARY_CAP]

        return replace(
            outcome,
            summary=summary,
            evidence=tuple(outcome.evidence) + claims["evidence"],
            inferences=tuple(outcome.inferences) + claims["inferences"],
            uncertainties=tuple(outcome.uncertainties) + claims["uncertainties"],
        )
    except Exception as exc:  # noqa: BLE001 — reporting must not break the run
        logger.warning("verification gate failed for run %s: %s", run_id, exc)
        return outcome


__all__ = [
    "GATE_VERSION",
    "ObservedCall",
    "VerificationVerdict",
    "apply",
    "classify",
    "classify_run",
    "describe",
    "enabled",
    "observed_calls",
    "summarize",
    "verdict_for",
]
