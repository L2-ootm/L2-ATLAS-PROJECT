"""ATLAS async run executor — drive a run to completion in the background.

Makes the run loop autonomous: a run can start, return its `run_id`
immediately, execute asynchronously via its AgentRuntime (P4), emit
AuditEvents/SSE as it goes, and transition to a terminal state — without the
caller blocking on the synchronous CLI `--execute` path (the only live executor
today; the gateway is currently record-only).

In-process daemon thread at single-operator scale: the existing
`threading.Lock` + SQLite WAL serialize writes. See
`.planning/prep/next-steps-db-runner-async-supabase.md` (§2) for the decision and
`.planning/milestones/v1.0.5-phases/10.0.3-command-center/PLAN.md` (WP-1).

Lifecycle ownership (per AgentRuntime contract): `execute()` emits audit and
returns a RunOutcome; THIS module owns the terminal transition
(`complete_run` / `fail_run`) and respects a run that was cancelled mid-flight
(the terminal transition is skipped so the cancellation wins). A run is never
left 'running': an unhandled agent error becomes a failed transition.
"""
from __future__ import annotations

import datetime
import json
import sqlite3
import threading
from typing import Callable, Optional

from atlas_core.schemas import provenance
from atlas_core.schemas.brain import BrainEdge, BrainNode
from atlas_core.schemas.core import Run
from atlas_runtime import brain_service, goal_service, mission_service, verification_gate
from atlas_runtime.agents import AgentRuntime, RunOutcome, get_agent
from atlas_runtime.db import connect
from atlas_runtime.memory_router import redact
from atlas_runtime.run_service import complete_run, start_run

_SUMMARY_CAP = 2000
_OBS_CAP = 600

# run_id -> worker thread, for await/graceful-shutdown and tests.
_active_threads: dict[str, threading.Thread] = {}
_active_lock = threading.Lock()


def execute_run(
    conn: sqlite3.Connection,
    lock: threading.Lock,
    *,
    agent: AgentRuntime,
    mission_id: str,
    run_id: str,
    prompt: str,
    cancel_token: Optional[threading.Event] = None,
) -> RunOutcome:
    """Drive an already-started run to a terminal state. Synchronous; reusable
    by both the CLI `--execute` path and the async executor below.

    Never leaves a run 'running': an unhandled agent error becomes a failed
    transition. If the run was cancelled while executing, the cancellation is
    preserved (the terminal transition is skipped). `cancel_token` is forwarded to
    the agent for cooperative cancellation; None preserves today's behavior exactly.
    """
    try:
        outcome = agent.execute(
            conn, lock, mission_id=mission_id, run_id=run_id, prompt=prompt,
            cancel_token=cancel_token,
        )
    except Exception as exc:  # agents should be fail-safe; defend anyway
        outcome = RunOutcome(
            status="failed", summary=f"executor: unhandled agent error: {exc}"[:_SUMMARY_CAP]
        )

    # Verification gate: the run's own claim of success is an inference; the
    # audit trail is evidence. Applied here rather than inside an agent so every
    # runtime (native/claude_code/codex) is held to the same standard, and
    # applied BEFORE complete_run so the verdict reaches the summary, the
    # compounding-loop observation and the brain graph below. Fail-open.
    outcome = verification_gate.apply(conn, lock, run_id=run_id, outcome=outcome)
    _adopt_scratch_files(conn, lock, run_id=run_id)

    try:
        complete_run(
            conn, lock, run_id=run_id, mission_id=mission_id, status=outcome.status, summary=outcome.summary
        )
    except ValueError:
        # Run is no longer 'running' (e.g. cancelled mid-flight) — respect the
        # existing terminal state; do not clobber it. Skip the compounding write.
        return outcome

    # Compounding loop (WP-5): record the outcome as a provenance-tracked
    # observation so the next run's context inherits it. Never mutates
    # operator-owned goals. Fail-open: a feedback-write error must not affect
    # the run's terminal state.
    try:
        _record_outcome_observation(conn, lock, run_id=run_id, outcome=outcome)
    except Exception:  # noqa: BLE001 — compounding feedback is best-effort
        pass

    # Brain graph (CTX-01 retrieval spine): persist the outcome as evidence so
    # the BrainRetriever can hand it to future runs. Fail-open like the
    # observation above — a graph-write error must not affect the terminal state.
    try:
        _record_brain_outcome(
            conn, lock, mission_id=mission_id, run_id=run_id, outcome=outcome
        )
    except Exception:  # noqa: BLE001 — brain writes are best-effort
        pass
    return outcome


def _adopt_scratch_files(
    conn: sqlite3.Connection, lock: threading.Lock, *, run_id: str
) -> None:
    """Take ownership of scripts the run left in ATLAS's scratch root.

    The agent reaches for `write_file`, not `atlas_scratchpad op=materialize` —
    measured over three live runs, including one where the doctrine demonstrably
    reached it. Rather than keep arguing, ATLAS does the bookkeeping for the tool
    the agent actually uses, so the file still gets a TTL, a sweep and a
    promotion record. Best-effort: this must never affect a run's outcome.
    """
    try:
        from atlas_runtime import scratchpad_service  # noqa: PLC0415

        session_row = conn.execute(
            "SELECT session_id FROM runs WHERE id=?", (run_id,)
        ).fetchone()
        scratchpad_service.adopt_scratch_files(
            conn, lock,
            run_id=run_id,
            session_id=str(session_row[0]) if session_row and session_row[0] else "",
        )
    except Exception:  # noqa: BLE001 — bookkeeping never fails a run
        pass


def _record_outcome_observation(
    conn: sqlite3.Connection,
    lock: threading.Lock,
    *,
    run_id: str,
    outcome: RunOutcome,
) -> None:
    """Append a compounding-loop observation summarizing a terminal run."""
    parts = [f"run {outcome.status}: {outcome.summary}".strip()]
    if outcome.stop_reason:
        parts.append(f"stop_reason={outcome.stop_reason}")
    if outcome.uncertainties:
        parts.append("uncertainties: " + "; ".join(outcome.uncertainties))
    body = " | ".join(p for p in parts if p)[:_OBS_CAP]
    goal_service.add_observation(
        conn, lock, body=body, run_id=run_id, source="compounding-loop"
    )


_BRAIN_LABEL_CAP = 200


def _record_brain_outcome(
    conn: sqlite3.Connection,
    lock: threading.Lock,
    *,
    mission_id: str,
    run_id: str,
    outcome: RunOutcome,
) -> None:
    """Upsert this terminal run into the Brain graph: a mission node and a run
    node joined by a `produced` edge, project-scoped to the mission. Labels are
    secret-redacted before storage (the router redacts again at retrieval)."""
    mission = mission_service.get_mission(conn, mission_id)
    if mission is None:
        return
    now = datetime.datetime.now(datetime.timezone.utc).isoformat()
    summary = redact(outcome.summary or "")[:_BRAIN_LABEL_CAP]
    with lock:
        brain_service.upsert_node(
            conn,
            BrainNode(
                id=f"mission:{mission_id}",
                entity_type="mission",
                label=redact(mission.title)[:_BRAIN_LABEL_CAP] or mission_id,
                project_id=mission.project_id,
                source_id=f"mission:{mission_id}",
                source_version="1",
                updated_at=now,
                confidence=1.0,
                # ATLAS projecting a row it already owns. Machine-written record
                # of what happened, so `observed` — and stated explicitly because
                # BrainNode floors an undeclared grade at `asserted`, which sits
                # below the retrieval floor and would keep every run and mission
                # out of every future brief.
                grade=provenance.OBSERVED,
            ),
        )
        brain_service.upsert_node(
            conn,
            BrainNode(
                id=f"run:{run_id}",
                entity_type="run",
                label=f"run {outcome.status}: {summary}".strip(),
                project_id=mission.project_id,
                source_id=f"run:{run_id}",
                source_version="1",
                updated_at=now,
                confidence=0.9 if outcome.status == "succeeded" else 0.5,
                grade=provenance.OBSERVED,  # the run happened; this records it
                metadata_json=json.dumps(
                    {"status": outcome.status, "stop_reason": outcome.stop_reason or ""}
                ),
            ),
        )
        brain_service.upsert_edge(
            conn,
            BrainEdge(
                source_id=f"mission:{mission_id}",
                target_id=f"run:{run_id}",
                relation="produced",
                project_id=mission.project_id,
            ),
        )


def start_and_execute_async(
    conn: sqlite3.Connection,
    lock: threading.Lock,
    *,
    mission_id: str,
    agent_name: str = "native",
    prompt: str = "",
    session_id: Optional[str] = None,
    agent: Optional[AgentRuntime] = None,
    conn_factory: Optional[Callable[[], sqlite3.Connection]] = None,
    cancel_token: Optional[threading.Event] = None,
) -> Run:
    """Start a run and execute it on a background daemon thread.

    Returns the Run immediately (status 'running') so the caller (gateway /
    Command Center) gets the `run_id` without blocking. The worker opens its own
    SQLite connection (WAL; writes serialized by `lock`) and closes it when done.

    `agent` may be injected (tests / a pre-resolved runtime); otherwise it is
    resolved from the registry by `agent_name` BEFORE the run is created, so an
    invalid agent fails fast without leaving an orphaned 'running' run.
    """
    resolved = agent or get_agent(agent_name)
    run = start_run(
        conn, lock, mission_id=mission_id, session_id=session_id, agent_runtime=agent_name  # type: ignore[arg-type]
    )
    factory = conn_factory or connect

    def _worker() -> None:
        wconn = factory()
        try:
            execute_run(
                wconn, lock, agent=resolved, mission_id=mission_id, run_id=run.id,
                prompt=prompt, cancel_token=cancel_token,
            )
        finally:
            try:
                wconn.close()
            except Exception:
                pass
            with _active_lock:
                _active_threads.pop(run.id, None)

    thread = threading.Thread(target=_worker, name=f"atlas-run-{run.id[:8]}", daemon=True)
    with _active_lock:
        _active_threads[run.id] = thread
    thread.start()
    return run


def await_run(run_id: str, timeout: Optional[float] = None) -> bool:
    """Block until the run's worker thread finishes (or `timeout` elapses).

    Returns True if no worker is tracked or it completed, False if it is still
    running. For graceful shutdown and tests.
    """
    with _active_lock:
        thread = _active_threads.get(run_id)
    if thread is None:
        return True
    thread.join(timeout)
    return not thread.is_alive()


def active_run_ids() -> list[str]:
    """run_ids with a live executor thread (for shutdown / introspection)."""
    with _active_lock:
        return [rid for rid, t in _active_threads.items() if t.is_alive()]
