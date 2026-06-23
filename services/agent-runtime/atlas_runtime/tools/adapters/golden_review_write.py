"""golden_review_write adapter — write a Self-Review note (write-class, Phase 10.0.5-03).

Write-class (risk_level: write in the manifest), so this `run()` is ONLY ever
invoked from `tool_service.approve` after an explicit operator approval — by the
time this code executes, authorization has already happened at the chokepoint.
This adapter performs NO policy/risk decision of its own (mirrors the adapter
protocol contract in tools/adapters/base.py).

It still re-validates the target path through `policy.check_workspace_boundary`
defensively (T-1005-08, tampering mitigation): the path was only checked once at
propose-time (`self_review.run_self_review`) and is stored verbatim in the
`tool_approvals.args` row until approve() — re-checking here at execute-time
guards against a malformed/tampered args payload, not against the original
authorization decision (already settled).
"""
from __future__ import annotations

import pathlib
from typing import Any

from atlas_core.schemas.tool import ToolResult

from atlas_runtime import policy

_TOOL = "golden_review_write"


def _workspace_root(ctx: Any) -> str:
    if isinstance(ctx, dict):
        return ctx.get("workspace_root") or "."
    return getattr(ctx, "workspace_root", None) or "."


def run(args: dict, ctx: Any) -> ToolResult:
    args = args or {}
    target = args.get("path", "")
    content = args.get("content", "")
    root = _workspace_root(ctx)

    decision = policy.check_workspace_boundary(target_path=target, workspace_root=root)
    if not decision.allowed:
        return ToolResult(
            tool_name=_TOOL, ok=False, error=f"path outside workspace: {decision.reason}"
        )

    resolved = (pathlib.Path(root).resolve() / target).resolve()
    try:
        resolved.parent.mkdir(parents=True, exist_ok=True)
        resolved.write_text(content, encoding="utf-8")
        return ToolResult(tool_name=_TOOL, ok=True, output=str(resolved))
    except OSError as exc:
        return ToolResult(tool_name=_TOOL, ok=False, error=str(exc))
