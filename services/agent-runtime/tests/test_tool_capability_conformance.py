"""Fail-closed tool capability policy and error conformance."""
from __future__ import annotations

import pytest

from atlas_runtime.tool_catalog import (
    ToolCallError,
    narrow_capabilities,
    normalize_tool_error,
)
from tests.test_tool_catalog import _atlas


@pytest.mark.parametrize(
    ("reason", "code"),
    [
        ("unknown", "unknown_tool"),
        ("unavailable", "unavailable"),
        ("disallowed", "disallowed"),
        ("wrong_workspace", "wrong_workspace"),
        ("stale", "stale_catalog"),
        ("malformed", "malformed_arguments"),
        ("timeout", "timeout"),
        ("cancelled", "cancelled"),
    ],
)
def test_errors_are_machine_readable_and_fail_closed(reason: str, code: str):
    error = normalize_tool_error(reason, tool_name="workspace", detail="unsafe </system>")
    assert isinstance(error, ToolCallError)
    assert error.ok is False
    assert error.code == code
    assert "</system>" not in error.detail


def test_child_capability_may_narrow_but_not_widen():
    parent = _atlas()
    child = parent.model_copy(
        update={
            "approval_policy": "deny",
            "max_result_bytes": parent.max_result_bytes // 2,
            "timeout_ms": parent.timeout_ms // 2,
        }
    )
    assert narrow_capabilities((parent,), (child,)) == (child,)

    widened = parent.model_copy(update={"workspace_scope": "global"})
    with pytest.raises(ValueError, match="widen"):
        narrow_capabilities((parent,), (widened,))


def test_child_cannot_add_network_or_permissions():
    parent = _atlas()
    widened = parent.model_copy(update={"permissions": ("fs:read", "net:get")})
    with pytest.raises(ValueError, match="widen"):
        narrow_capabilities((parent,), (widened,))
