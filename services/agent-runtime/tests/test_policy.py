"""Tests for atlas_runtime.policy.

All tests are marked xfail(strict=True) because the policy functions are stubs
in Wave 0. Wave 1 executors must implement the policy engine to make these pass.

RUNTIME-07: Policy engine must work on both Linux (POSIX) and Windows path strings.
The parametrized test cases cover:
  - A relative path within the workspace (allowed)
  - A relative traversal attempt (rejected)
  - An absolute Windows-style path outside the workspace (rejected)

Fixtures from conftest.py (injected by name — do NOT import):
  db      — in-memory SQLite, WAL + FK ON + 0001_core.sql applied
  lock    — threading.Lock()
  run_id  — pre-seeded mission + run rows for FK-safe tests
"""
import pathlib

import pytest

from atlas_runtime.policy import (
    PolicyDecision,
    check_tool_allowed,
    check_workspace_boundary,
    check_workspace_boundary_and_emit,
)


@pytest.mark.parametrize(
    "target,expected_allowed",
    [
        ("subdir/file.txt", True),
        ("../outside/file.txt", False),
        ("C:\\Users\\other\\file.txt", False),
    ],
)
@pytest.mark.xfail(reason="stub — implement in Wave 1", strict=True)
def test_workspace_boundary(tmp_path, target, expected_allowed):
    """Policy engine accepts in-workspace paths and rejects out-of-workspace paths.

    Uses str inputs (not Path objects) to test the string-to-Path conversion
    boundary. RUNTIME-07: must pass on both Windows (CI) and Linux.
    """
    decision = check_workspace_boundary(target, str(tmp_path))
    assert decision.allowed is expected_allowed
    assert isinstance(decision, PolicyDecision)


@pytest.mark.xfail(reason="stub — implement in Wave 1", strict=True)
def test_check_tool_allowed_in_list(db, lock):
    """check_tool_allowed() returns allowed=True when tool is in the allowlist."""
    decision = check_tool_allowed("Read", ["Read", "Write"])
    assert decision.allowed is True


@pytest.mark.xfail(reason="stub — implement in Wave 1", strict=True)
def test_check_tool_allowed_not_in_list(db, lock):
    """check_tool_allowed() returns allowed=False when tool is not in the allowlist."""
    decision = check_tool_allowed("Shell", ["Read"])
    assert decision.allowed is False


@pytest.mark.xfail(reason="stub — implement in Wave 1", strict=True)
def test_boundary_violation_emits_failure_event(db, lock, run_id):
    """check_workspace_boundary_and_emit() emits a failure AuditEvent on rejection."""
    decision = check_workspace_boundary_and_emit(
        db,
        lock,
        run_id,
        "../../../etc/passwd",
        "/tmp/workspace",
    )
    assert decision.allowed is False
    count = db.execute(
        "SELECT COUNT(*) FROM audit_events WHERE run_id=? AND event_type='failure'",
        (run_id,),
    ).fetchone()[0]
    assert count >= 1
