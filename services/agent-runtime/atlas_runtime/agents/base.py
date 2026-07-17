"""AgentRuntime ABC + RunOutcome (P4).

Contract: an AgentRuntime executes one run of a mission and emits AuditEvents
via audit_service.emit() for every observable action (llm_call, tool_call,
failure, ...). It returns a RunOutcome describing the terminal status; the
caller (CLI/executor) is responsible for the run lifecycle transition
(complete_run / fail_run). Implementations MUST be fail-safe: an internal
error becomes RunOutcome(status="failed", ...) plus a 'failure' AuditEvent,
never an unhandled exception that corrupts run state.
"""
from __future__ import annotations

import sqlite3
import threading
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Literal, Optional

VALID_AGENTS = ("native", "claude_code", "codex")


@dataclass(frozen=True)
class RunOutcome:
    """Terminal result of an AgentRuntime.execute() call.

    `evidence`/`inferences`/`uncertainties` are the L2 claim taxonomy (Layer 3):
    what was verified vs deduced vs unverified, so the operator can trust the
    summary. `stop_reason` is set when a stop condition (Layer 2) ended the run
    (e.g. "secret_in_prompt", "max_runtime_exceeded"). All default empty so
    existing constructions stay valid. Tuples keep the dataclass frozen/hashable.
    """

    status: Literal["succeeded", "failed"]
    summary: str = ""
    evidence: tuple[str, ...] = ()
    inferences: tuple[str, ...] = ()
    uncertainties: tuple[str, ...] = ()
    stop_reason: Optional[str] = None


class AgentRuntime(ABC):
    """Base class for a pluggable agent runtime.

    Subclasses set the class attribute `name` (the registry key) and implement
    execute(). Subclasses must be constructible with no required arguments so
    the registry can instantiate them; inject collaborators via optional
    keyword args with safe defaults (see ClaudeCodeAgent).
    """

    name: str = ""

    @abstractmethod
    def execute(
        self,
        conn: sqlite3.Connection,
        lock: threading.Lock,
        *,
        mission_id: str,
        run_id: str,
        prompt: str,
        cancel_token: Optional[threading.Event] = None,
    ) -> RunOutcome:
        """Execute the run, emitting AuditEvents, and return its outcome.

        `cancel_token`, when provided and set, requests COOPERATIVE cancellation:
        the runtime stops at its next observable checkpoint and returns a terminal
        `cancelled` outcome (CPython cannot hard-kill a thread). None preserves the
        pre-cancellation behavior exactly.
        """
        raise NotImplementedError
