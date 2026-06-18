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
from typing import Literal

VALID_AGENTS = ("native", "claude_code")


@dataclass(frozen=True)
class RunOutcome:
    """Terminal result of an AgentRuntime.execute() call."""

    status: Literal["succeeded", "failed"]
    summary: str = ""


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
    ) -> RunOutcome:
        """Execute the run, emitting AuditEvents, and return its outcome."""
        raise NotImplementedError
