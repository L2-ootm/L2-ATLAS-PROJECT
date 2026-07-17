"""Durable judge-and-continue orchestration for long-horizon missions.

The runtime worker is the sole continuation owner. Surfaces configure a loop;
this module judges terminal successful runs, records immutable receipts, and
atomically returns a mission to ``pending`` when another run is warranted.
"""
from __future__ import annotations

import datetime
import json
import sqlite3
import threading
import uuid
from dataclasses import dataclass
from typing import Callable, Literal

from atlas_runtime import config_service
from atlas_runtime.audit_service import emit

DEFAULT_MAX_RUNS = 12
MAX_RUNS = 100
MAX_PARSE_FAILURES = 3

Verdict = Literal["done", "continue"]
Judge = Callable[[str, str, dict[str, str]], tuple[Verdict, str, bool, str, str]]


@dataclass(frozen=True)
class LoopDecision:
    action: Literal["done", "continue", "paused", "exhausted", "stopped"]
    verdict: str
    reason: str


def configure_loop(
    conn: sqlite3.Connection,
    lock: threading.Lock,
    *,
    mission_id: str,
    session_id: str | None = None,
    judge_model: str = "",
    max_runs: int = DEFAULT_MAX_RUNS,
) -> None:
    """Enable goal mode for a pending mission."""
    if not 1 <= max_runs <= MAX_RUNS:
        raise ValueError(f"max_runs must be between 1 and {MAX_RUNS}")
    judge_model = judge_model.strip()
    if judge_model and "/" not in judge_model:
        raise ValueError("judge_model must use provider/model form")
    now = _now()
    with lock:
        with conn:
            row = conn.execute(
                "SELECT intent, status FROM missions WHERE id=?", (mission_id,)
            ).fetchone()
            if row is None:
                raise ValueError(f"Mission {mission_id!r} not found")
            if row[1] != "pending":
                raise ValueError("goal mode can only be configured before the first run")
            conn.execute(
                "INSERT INTO mission_loops"
                "(mission_id,session_id,objective,state,max_runs,runs_used,judge_model,"
                "consecutive_parse_failures,last_run_id,last_verdict,last_reason,created_at,updated_at) "
                "VALUES (?,?,?,?,?,0,?,0,NULL,'','',?,?) "
                "ON CONFLICT(mission_id) DO UPDATE SET session_id=excluded.session_id,"
                "objective=excluded.objective,state='active',max_runs=excluded.max_runs,"
                "judge_model=excluded.judge_model,updated_at=excluded.updated_at",
                (mission_id, session_id, row[0] or "", "active", max_runs, judge_model, now, now),
            )


def get_loop(conn: sqlite3.Connection, mission_id: str) -> dict[str, object] | None:
    cursor = conn.execute("SELECT * FROM mission_loops WHERE mission_id=?", (mission_id,))
    row = cursor.fetchone()
    if row is None:
        return None
    return dict(zip((d[0] for d in cursor.description), row))


def pause_loop(conn: sqlite3.Connection, lock: threading.Lock, mission_id: str) -> None:
    _set_state(conn, lock, mission_id, "paused")


def resume_loop(conn: sqlite3.Connection, lock: threading.Lock, mission_id: str) -> None:
    with lock:
        with conn:
            row = conn.execute(
                "SELECT ml.state, m.status FROM mission_loops ml JOIN missions m ON m.id=ml.mission_id "
                "WHERE ml.mission_id=?", (mission_id,)
            ).fetchone()
            if row is None:
                raise ValueError(f"Mission loop {mission_id!r} not found")
            if row[0] not in {"paused", "exhausted", "failed"}:
                raise ValueError(f"Cannot resume loop in state {row[0]!r}")
            if conn.execute(
                "SELECT 1 FROM runs WHERE mission_id=? AND status='running' LIMIT 1", (mission_id,)
            ).fetchone():
                raise ValueError("mission already has a running run")
            now = _now()
            conn.execute("UPDATE mission_loops SET state='active',updated_at=? WHERE mission_id=?", (now, mission_id))
            conn.execute("UPDATE missions SET status='pending',updated_at=? WHERE id=?", (now, mission_id))


def evaluate_after_run(
    conn: sqlite3.Connection,
    lock: threading.Lock,
    *,
    mission_id: str,
    run_id: str,
    run_status: str,
    judge: Judge | None = None,
) -> LoopDecision:
    """Judge one terminal run exactly once and persist the resulting loop state."""
    loop = get_loop(conn, mission_id)
    if loop is None or loop["state"] != "active":
        return LoopDecision("stopped", "skipped", "mission is not an active goal loop")
    if run_status != "succeeded":
        _record_terminal_state(conn, lock, mission_id, run_id, "failed", "run did not succeed")
        return LoopDecision("stopped", "skipped", "failed runs are not auto-continued")

    existing = conn.execute(
        "SELECT verdict,reason FROM run_judgements WHERE run_id=?", (run_id,)
    ).fetchone()
    if existing:
        action = "done" if existing[0] == "done" else "stopped"
        return LoopDecision(action, existing[0], existing[1])

    response = _run_response(conn, run_id)
    runtime = _effective_runtime(conn, loop)
    verdict, reason, parse_failed, provider, model = (judge or _foundation_judge)(
        str(loop["objective"]), response, runtime
    )
    runs_used = int(loop["runs_used"]) + 1
    failures = int(loop["consecutive_parse_failures"]) + 1 if parse_failed else 0
    if verdict == "done":
        state, action = "done", "done"
    elif failures >= MAX_PARSE_FAILURES:
        state, action = "paused", "paused"
    elif runs_used >= int(loop["max_runs"]):
        state, action = "exhausted", "exhausted"
    else:
        state, action = "active", "continue"

    now = _now()
    with lock:
        with conn:
            # Re-check under the write lock: reconnects/resumes must not judge twice.
            if conn.execute("SELECT 1 FROM run_judgements WHERE run_id=?", (run_id,)).fetchone():
                return LoopDecision("stopped", "skipped", "run was already judged")
            conn.execute(
                "INSERT INTO run_judgements"
                "(id,mission_id,run_id,verdict,reason,parse_failed,model_provider,model_id,created_at) "
                "VALUES (?,?,?,?,?,?,?,?,?)",
                (str(uuid.uuid4()), mission_id, run_id, verdict, reason, int(parse_failed), provider, model, now),
            )
            conn.execute(
                "UPDATE mission_loops SET state=?,runs_used=?,consecutive_parse_failures=?,"
                "last_run_id=?,last_verdict=?,last_reason=?,updated_at=? WHERE mission_id=?",
                (state, runs_used, failures, run_id, verdict, reason, now, mission_id),
            )
            if action == "continue":
                conn.execute("UPDATE missions SET status='pending',updated_at=? WHERE id=?", (now, mission_id))

    emit(
        conn, lock, run_id=run_id, event_type="goal_judgement",
        data={"verdict": verdict, "reason": reason, "state": state,
              "runs_used": runs_used, "max_runs": int(loop["max_runs"]),
              "model_provider": provider, "model_id": model},
    )
    return LoopDecision(action, verdict, reason)


def _effective_runtime(conn: sqlite3.Connection, loop: dict[str, object]) -> dict[str, str]:
    config = config_service.load_config()
    resolved = config_service.resolve_provider(config)
    override = str(loop.get("judge_model") or config.functions.judge_model or "").strip()
    if override:
        provider, _, model = override.partition("/")
        if provider != resolved.get("provider"):
            if provider == "openai-codex":
                from atlas_runtime import codex_auth  # noqa: PLC0415

                credentials = codex_auth.resolve_codex_credentials()
                resolved["base_url"] = credentials.get("base_url") or ""
                resolved["api_key"] = credentials.get("api_key") or ""
                resolved["auth_mode"] = "oauth_import"
                model = codex_auth.effective_codex_model(model)
            else:
                from atlas_runtime import auth_service  # noqa: PLC0415

                resolved["api_key"] = auth_service.resolve_secret(provider) or ""
                provider_row = conn.execute(
                    "SELECT default_base_url FROM provider_registry WHERE provider_id=?",
                    (provider,),
                ).fetchone()
                resolved["base_url"] = (
                    str(provider_row[0]) if provider_row and provider_row[0] else ""
                )
                resolved["auth_mode"] = "api_key"
        resolved["provider"], resolved["model"] = provider, model
    elif loop.get("session_id"):
        row = conn.execute(
            "SELECT model_provider,model_id FROM surface_sessions WHERE id=?",
            (loop["session_id"],),
        ).fetchone()
        if row and row[0] and row[1]:
            selected_provider, selected_model = str(row[0]), str(row[1])
            if selected_provider != resolved.get("provider"):
                if selected_provider == "openai-codex":
                    from atlas_runtime import codex_auth  # noqa: PLC0415

                    credentials = codex_auth.resolve_codex_credentials()
                    resolved["base_url"] = credentials.get("base_url") or ""
                    resolved["api_key"] = credentials.get("api_key") or ""
                    resolved["auth_mode"] = "oauth_import"
                    selected_model = codex_auth.effective_codex_model(selected_model)
                else:
                    from atlas_runtime import auth_service  # noqa: PLC0415

                    resolved["api_key"] = auth_service.resolve_secret(selected_provider) or ""
                    provider_row = conn.execute(
                        "SELECT default_base_url FROM provider_registry WHERE provider_id=?",
                        (selected_provider,),
                    ).fetchone()
                    resolved["base_url"] = (
                        str(provider_row[0]) if provider_row and provider_row[0] else ""
                    )
                    resolved["auth_mode"] = "api_key"
            resolved["provider"], resolved["model"] = selected_provider, selected_model
    return {k: str(v) for k, v in resolved.items() if v is not None}


def _foundation_judge(
    objective: str, response: str, runtime: dict[str, str]
) -> tuple[Verdict, str, bool, str, str]:
    """Call Hermes's text auxiliary client while inheriting the live chat runtime."""
    if not response.strip():
        return "continue", "empty response (nothing to evaluate)", False, runtime.get("provider", ""), runtime.get("model", "")
    from atlas_runtime.subagent_service import _foundation_on_path  # noqa: PLC0415

    if not _foundation_on_path():
        return "continue", "judge unavailable", False, runtime.get("provider", ""), runtime.get("model", "")
    from agent.auxiliary_client import get_auxiliary_extra_body, resolve_provider_client  # type: ignore # noqa: PLC0415
    from hermes_cli.goals import (  # type: ignore # noqa: PLC0415
        JUDGE_SYSTEM_PROMPT,
        JUDGE_USER_PROMPT_TEMPLATE,
        _goal_judge_max_tokens,
        _parse_judge_response,
    )

    provider = runtime.get("provider", "")
    client, model = resolve_provider_client(
        provider or "auto",
        model=runtime.get("model") or None,
        explicit_base_url=runtime.get("base_url") or None,
        explicit_api_key=runtime.get("api_key") or None,
        main_runtime=runtime,
    )
    if client is None or not model:
        return "continue", "no judge client configured", False, provider, model or ""
    prompt = JUDGE_USER_PROMPT_TEMPLATE.format(
        goal=objective[:2000], response=response[:12000],
        current_time=datetime.datetime.now().astimezone().strftime("%Y-%m-%d %H:%M:%S %Z"),
    )
    try:
        result = client.chat.completions.create(
            model=model,
            messages=[{"role": "system", "content": JUDGE_SYSTEM_PROMPT}, {"role": "user", "content": prompt}],
            temperature=0, max_tokens=_goal_judge_max_tokens(), timeout=30,
            extra_body=get_auxiliary_extra_body() or None,
        )
        raw = result.choices[0].message.content or ""
    except Exception as exc:  # fail-open, bounded by max_runs
        return "continue", f"judge error: {type(exc).__name__}", False, provider, model
    done, reason, parse_failed = _parse_judge_response(raw)
    return ("done" if done else "continue"), reason, parse_failed, provider, model


def _run_response(conn: sqlite3.Connection, run_id: str) -> str:
    rows = conn.execute(
        "SELECT data FROM audit_events WHERE run_id=? AND event_type IN ('llm_call','model_call_end') "
        "ORDER BY timestamp DESC,rowid DESC", (run_id,)
    ).fetchall()
    for (raw,) in rows:
        try:
            data = json.loads(raw)
        except (TypeError, json.JSONDecodeError):
            continue
        text = data.get("text") if isinstance(data, dict) else None
        if isinstance(text, str) and text.strip():
            return text
    row = conn.execute("SELECT summary FROM runs WHERE id=?", (run_id,)).fetchone()
    return str(row[0] or "") if row else ""


def _record_terminal_state(
    conn: sqlite3.Connection, lock: threading.Lock, mission_id: str, run_id: str,
    state: str, reason: str,
) -> None:
    now = _now()
    with lock:
        with conn:
            conn.execute(
                "UPDATE mission_loops SET state=?,last_run_id=?,last_reason=?,updated_at=? WHERE mission_id=?",
                (state, run_id, reason, now, mission_id),
            )


def _set_state(conn: sqlite3.Connection, lock: threading.Lock, mission_id: str, state: str) -> None:
    with lock:
        with conn:
            changed = conn.execute(
                "UPDATE mission_loops SET state=?,updated_at=? WHERE mission_id=?",
                (state, _now(), mission_id),
            ).rowcount
            if not changed:
                raise ValueError(f"Mission loop {mission_id!r} not found")


def _now() -> str:
    return datetime.datetime.now(datetime.timezone.utc).isoformat()


__all__ = [
    "DEFAULT_MAX_RUNS", "LoopDecision", "configure_loop", "evaluate_after_run",
    "get_loop", "pause_loop", "resume_loop",
]
