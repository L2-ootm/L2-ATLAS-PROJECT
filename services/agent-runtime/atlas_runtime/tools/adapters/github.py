"""GitHub adapter — read repo/issue/PR data via the operator's `gh` CLI (Phase 10.0.4).

Read-class. Delegates auth entirely to the user's existing `gh` login — ATLAS
handles no token (D-002). Argv VECTORS only, never shell=True (T-10.0.4-07). Any
failure (gh absent, non-zero exit, timeout) returns ToolResult(ok=False) rather
than raising, so registry load and the chokepoint never crash (T-10.0.4-08).

gh 2.92.0 --json field names verified for the three read subcommands (A1).
"""
from __future__ import annotations

import subprocess
from typing import Any

from atlas_core.schemas.tool import ToolResult

from atlas_runtime.tools.adapters.base import no_window_flags

_TOOL = "github"
_TIMEOUT = 30


def _argv(args: dict) -> list[str]:
    op = args.get("op", "repo_view")
    repo = args.get("repo", "")
    if op == "repo_view":
        return ["gh", "repo", "view", repo, "--json", "name,description,url,visibility"]
    if op == "issue_list":
        limit = str(args.get("limit", 20))
        return [
            "gh", "issue", "list", "--repo", repo,
            "--json", "number,title,state,author", "--limit", limit,
        ]
    if op == "pr_view":
        number = str(args.get("number", ""))
        return [
            "gh", "pr", "view", number, "--repo", repo,
            "--json", "number,title,state,body,author",
        ]
    raise ValueError(f"unknown github op {op!r}")


def run(args: dict, ctx: Any) -> ToolResult:
    args = args or {}
    try:
        argv = _argv(args)
    except ValueError as exc:
        return ToolResult(tool_name=_TOOL, ok=False, error=str(exc))
    try:
        proc = subprocess.run(
            argv, capture_output=True, text=True, timeout=_TIMEOUT,
            creationflags=no_window_flags(),
        )
    except FileNotFoundError:
        return ToolResult(tool_name=_TOOL, ok=False, error="gh CLI not found")
    except (OSError, subprocess.SubprocessError) as exc:
        return ToolResult(tool_name=_TOOL, ok=False, error=str(exc))
    if proc.returncode != 0:
        return ToolResult(
            tool_name=_TOOL, ok=False,
            error=(proc.stderr or "gh CLI failed").strip(), exit_code=proc.returncode,
        )
    return ToolResult(tool_name=_TOOL, ok=True, output=proc.stdout, exit_code=0)
