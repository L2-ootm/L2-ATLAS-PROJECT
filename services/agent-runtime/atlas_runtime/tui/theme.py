"""Semantic style tokens for the ATLAS terminal workbench.

`brand/` (see `brand/atlas/`) contains only rasters (PNG marks/sheets) and loose
ASCII-art text files — no machine-readable color palette. The tokens below are
hand-picked Rich named-color equivalents chosen to approximate the bronze/
celestial ATLAS brand marks (warm bronze primary, cool celestial accent) until
a real palette file exists under `brand/`.

Every other `tui/*` module must call `safe_style()`, never read `TOKENS`
directly, so no-color enforcement lives in exactly one place.
"""
from __future__ import annotations

from atlas_runtime.tui.capabilities import Capabilities

TOKENS: dict[str, str] = {
    "primary": "bold rgb(205,127,50)",  # bronze — brand/atlas board-bronze-* marks
    "accent": "bold cyan",  # celestial — brand/atlas board-celestial-* marks
    "warning": "bold yellow",
    "danger": "bold red",
    "muted": "grey58",
    "success": "bold green",
}


def safe_style(name: str, caps: Capabilities) -> str:
    """Return the Rich style string for `name`, or "" when `caps.no_color` is True.

    The single enforcement point for no-color mode across the entire `tui/`
    package — callers never branch on `caps.no_color` themselves.
    """
    if caps.no_color:
        return ""
    return TOKENS[name]


__all__ = ["TOKENS", "safe_style"]
