"""Tool adapter protocol + shared helpers (Phase 10.0.4).

An adapter is a module exposing ``run(args: dict, ctx) -> ToolResult``. Adapters
assume they have ALREADY been authorized — they perform NO policy/risk checks
(the single chokepoint in ``tool_service.invoke`` owns policy). Mirrors the
``agents/base.py`` protocol shape.
"""
from __future__ import annotations

import os
import subprocess
from typing import Any, Protocol

from atlas_core.schemas.tool import ToolResult


def no_window_flags() -> int:
    """Windows: suppress the console flash for short-lived capture-and-wait
    subprocesses (e.g. the gh CLI). This is ONLY CREATE_NO_WINDOW — not the
    detached triad used for long-lived spawns (RESEARCH Pitfall 1)."""
    if os.name == "nt":
        return subprocess.CREATE_NO_WINDOW  # type: ignore[attr-defined]
    return 0


class ToolAdapter(Protocol):
    """Structural type for a tool adapter callable."""

    def run(self, args: dict, ctx: Any) -> ToolResult:  # pragma: no cover - protocol
        ...
