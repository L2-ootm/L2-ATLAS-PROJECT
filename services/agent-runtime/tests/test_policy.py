"""Tests for atlas_runtime.policy.

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
def test_workspace_boundary(tmp_path, target, expected_allowed):
    """Policy engine accepts in-workspace paths and rejects out-of-workspace paths.

    Uses str inputs (not Path objects) to test the string-to-Path conversion
    boundary. RUNTIME-07: must pass on both Windows (CI) and Linux.
    """
    decision = check_workspace_boundary(target, str(tmp_path))
    assert decision.allowed is expected_allowed
    assert isinstance(decision, PolicyDecision)


def test_check_tool_allowed_in_list(db, lock):
    """check_tool_allowed() returns allowed=True when tool is in the allowlist."""
    decision = check_tool_allowed("Read", ["Read", "Write"])
    assert decision.allowed is True


def test_check_tool_allowed_not_in_list(db, lock):
    """check_tool_allowed() returns allowed=False when tool is not in the allowlist."""
    decision = check_tool_allowed("Shell", ["Read"])
    assert decision.allowed is False


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


# --- Phase 10.0.4: tool risk-level decision (policy.decide) ---


def _manifest(risk_level):
    from atlas_core.schemas.tool import ToolManifest

    return ToolManifest(name="t", description="", risk_level=risk_level)


def test_decide_read_is_allowed_without_approval():
    from atlas_runtime.policy import decide

    d = decide(_manifest("read"))
    assert d.allowed is True
    assert d.requires_approval is False
    assert d.reason == "read_class_allowed"


def test_decide_write_requires_approval():
    from atlas_runtime.policy import decide

    d = decide(_manifest("write"))
    assert d.allowed is False
    assert d.requires_approval is True
    assert d.reason == "write_requires_approval"


def test_decide_shell_requires_approval():
    from atlas_runtime.policy import decide

    d = decide(_manifest("shell"))
    assert d.allowed is False
    assert d.requires_approval is True
    assert d.reason == "shell_requires_approval"


def test_policy_decision_back_compat_default():
    # Existing (allowed, reason) construction still works; requires_approval defaults False.
    d = PolicyDecision(allowed=True, reason="within_workspace")
    assert d.requires_approval is False
