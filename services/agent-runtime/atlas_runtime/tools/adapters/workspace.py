"""Workspace adapter — read/list/grep bounded by the workspace policy (Phase 10.0.4).

Read-class. Every path is gated through ``policy.check_workspace_boundary`` BEFORE
any filesystem access, so a CWD-escaping path (``../../etc/passwd``) is rejected
without I/O. The adapter performs no risk decision — that is the chokepoint's job.
"""
from __future__ import annotations

import json
import pathlib
from typing import Any

from atlas_core.schemas.tool import ToolResult

from atlas_runtime import policy

_TOOL = "workspace"


def _workspace_root(ctx: Any) -> str:
    if isinstance(ctx, dict):
        return ctx.get("workspace_root") or "."
    return getattr(ctx, "workspace_root", None) or "."


def run(args: dict, ctx: Any) -> ToolResult:
    args = args or {}
    op = args.get("op", "read")
    target = args.get("path", "")
    root = _workspace_root(ctx)

    # Single boundary gate (real signature is target_path first, root second).
    decision = policy.check_workspace_boundary(target_path=target, workspace_root=root)
    if not decision.allowed:
        return ToolResult(
            tool_name=_TOOL, ok=False, error=f"path outside workspace: {decision.reason}"
        )

    resolved = (pathlib.Path(root).resolve() / target).resolve()
    try:
        if op in ("read", "read_file"):
            text = resolved.read_text(encoding="utf-8", errors="replace")
            return ToolResult(tool_name=_TOOL, ok=True, output=text)
        if op in ("list", "list_dir"):
            names = sorted(p.name for p in resolved.iterdir())
            return ToolResult(tool_name=_TOOL, ok=True, output=json.dumps(names))
        if op == "grep":
            pattern = args.get("pattern", "")
            matches = [
                {"line": i, "text": line}
                for i, line in enumerate(
                    resolved.read_text(encoding="utf-8", errors="replace").splitlines(), 1
                )
                if pattern and pattern in line
            ]
            return ToolResult(tool_name=_TOOL, ok=True, output=json.dumps(matches))
        return ToolResult(tool_name=_TOOL, ok=False, error=f"unknown op {op!r}")
    except (OSError, ValueError) as exc:
        return ToolResult(tool_name=_TOOL, ok=False, error=str(exc))
