"""ATLAS policy engine — workspace boundary and tool allowlist enforcement.

References:
  - D-006: Policy engine must work cross-platform (Linux bash + Windows PowerShell
    paths). Uses pathlib.Path.resolve() — never hardcodes OS path separators.
  - RUNTIME-07: Policy engine enforces cross-platform workspace/command safety.

PolicyDecision is a dataclass (not a Pydantic model) — it is an in-memory result,
not a persisted entity.

check_workspace_boundary_and_emit emits a failure AuditEvent on rejection per
success criterion 6 (CONTEXT.md).
"""
from __future__ import annotations

import pathlib
import sqlite3
import threading
from dataclasses import dataclass
from typing import Optional

from atlas_runtime.audit_service import emit


@dataclass
class PolicyDecision:
    """Result of a policy check.

    Attributes:
        allowed: True if the action is permitted; False if rejected.
        reason: Human-readable explanation for the decision.
    """

    allowed: bool
    reason: str


def check_workspace_boundary(
    target_path: str,
    workspace_root: str,
) -> PolicyDecision:
    """Return a PolicyDecision for whether target_path is within workspace_root.

    Uses pathlib.Path.resolve() for cross-platform normalization — handles both
    Windows (C:\\...) and POSIX (/home/...) path strings transparently.

    Resolves target relative to workspace_root to prevent CWD-escape attacks
    (Pitfall 3 in 05-RESEARCH.md).

    Raises:
        NotImplementedError: Stub — implement in Wave 1.
    """
    raise NotImplementedError("not implemented")


def check_workspace_boundary_and_emit(
    conn: sqlite3.Connection,
    lock: threading.Lock,
    run_id: str,
    target_path: str,
    workspace_root: str,
) -> PolicyDecision:
    """Check workspace boundary and emit a failure AuditEvent on rejection.

    Delegates boundary check to check_workspace_boundary(). If rejected, emits
    an AuditEvent with event_type="failure" and policy_result set to the reason.

    Raises:
        NotImplementedError: Stub — implement in Wave 1.
    """
    raise NotImplementedError("not implemented")


def check_tool_allowed(
    tool_name: str,
    allowed_tools: list[str],
) -> PolicyDecision:
    """Return a PolicyDecision for whether tool_name is in the allowed list (D-008).

    Unclassified tools (not in allowed_tools) are rejected — skills must be
    classified before ATLAS-grade use (D-008).

    Raises:
        NotImplementedError: Stub — implement in Wave 1.
    """
    raise NotImplementedError("not implemented")
