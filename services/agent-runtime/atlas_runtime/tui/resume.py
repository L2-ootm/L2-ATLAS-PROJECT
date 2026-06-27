"""Fail-closed TUI resume orchestration wrapper (TUI-09).

`resume_or_fail_closed` is the single TUI-side import surface for resuming a
suspended surface session. It always replays the immutable run contract via
`agent_contract_service.replay_contract` BEFORE delegating to
`surface_session_service.resume_session`, which itself re-asserts the same
fail-closed ordering against the session's own stored versions before any
state transition. Calling `replay_contract` here first against the caller-
supplied expected versions guarantees a version-drift check is performed
against the run's contract even when the session row's own stored version
columns have not yet been reconciled (e.g. a session created without a
run_id at session-creation time, later bound to a run for resume).

No try/except lives in this module: `ContractCompatibilityError`, `ValueError`,
and `LookupError` propagate unmodified. Error-card rendering is the caller's
responsibility (Wave 3 app.py), kept out of this module so resume.py stays a
pure orchestration call with no Rich/console dependency.
"""
from __future__ import annotations

import sqlite3
import threading
import uuid
from typing import Optional

from atlas_runtime import agent_contract_service
from atlas_runtime import surface_session_service


def resume_or_fail_closed(
    conn: sqlite3.Connection,
    *,
    session_id: str,
    run_id: str,
    expected_prompt_version: Optional[str] = None,
    expected_catalog_version: Optional[str] = None,
    expected_context_policy_version: Optional[str] = None,
    lock: Optional[threading.Lock] = None,
    owner_token: Optional[str] = None,
    owner_pid: Optional[int] = None,
):
    """Resume a suspended surface session, failing closed on contract drift.

    Replays the run's immutable contract snapshot BEFORE any session state
    transition (`agent_contract_service.replay_contract`), then delegates to
    `surface_session_service.resume_session` to perform the actual
    suspended -> resuming -> active transition (which independently repeats
    the same replay-before-transition guarantee against the session's own
    stored versions). Raises `ContractCompatibilityError` on any
    prompt/tool-catalog/context-policy version mismatch, or `LookupError` if
    no contract snapshot exists for the run — in both cases no transition is
    attempted and the session's DB state is left unchanged. Workspace and
    session identity are preserved unchanged across a successful resume;
    only state/ownership/heartbeat change.
    """
    agent_contract_service.replay_contract(
        conn,
        run_id,
        expected_prompt_version=expected_prompt_version,
        expected_catalog_version=expected_catalog_version,
        expected_context_policy_version=expected_context_policy_version,
    )

    return surface_session_service.resume_session(
        conn,
        lock if lock is not None else threading.Lock(),
        session_id,
        owner_token=owner_token if owner_token is not None else str(uuid.uuid4()),
        owner_pid=owner_pid,
    )


__all__ = ["resume_or_fail_closed"]
