"""Terminal capability probing for cross-terminal rendering (TUI-10).

Thin named-field wrapper around `rich.console.Console`'s own detection plus a
couple of process-level checks (`NO_COLOR` env, legacy Windows conhost). Other
`tui/*` modules read `Capabilities` fields instead of re-deriving terminal
detection logic themselves (Rich already owns no-color/box/width detection —
this module does not reimplement it, it only names the decisions).
"""
from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Mapping, Optional

from rich.console import Console

_NARROW_WIDTH_THRESHOLD = 80


@dataclass(frozen=True)
class Capabilities:
    """Immutable snapshot of what the current terminal can safely render."""

    no_color: bool
    box_style: str  # "ascii" | "unicode"
    width: int
    layout: str  # "narrow" | "normal"
    color_system: Optional[str]


def _is_legacy_windows_console() -> bool:
    """True on legacy (non-VT100) Windows conhost where Unicode box chars are unreliable.

    Patched directly in tests; default delegates to a throwaway Console's own
    detection rather than reimplementing the platform check.
    """
    return Console().legacy_windows


def _detect_width() -> int:
    """Current terminal width in columns; default delegates to a real Console().width.

    Patched directly in tests (narrow-terminal simulation) so callers don't need
    to thread a `console` override through every probe call.
    """
    return Console().width


def probe_capabilities(
    console: Optional[Console] = None, *, env: Optional[Mapping[str, str]] = None
) -> Capabilities:
    """Probe the active terminal and return a frozen `Capabilities` snapshot.

    `console`/`env` are injectable for tests; defaults are the real process
    `Console()` and `os.environ`. `_is_legacy_windows_console`/`_detect_width`
    are separate module-level hooks (rather than inline `console` lookups) so
    tests can force legacy-Windows or narrow-width behavior independently of a
    full Console instance.
    """
    env = env if env is not None else os.environ
    console_given = console is not None
    console = console if console is not None else Console()

    no_color = bool(env.get("NO_COLOR")) or console.no_color

    # Module-level hooks (`_is_legacy_windows_console`, `_detect_width`) are consulted
    # first so tests can force a decision without constructing a full Console override;
    # an explicitly-passed console's own properties are honored as a fallback/override.
    legacy_windows = _is_legacy_windows_console() or (console_given and console.legacy_windows)
    ascii_only = (
        legacy_windows
        or console.safe_box
        or env.get("ATLAS_TUI_ASCII") == "1"
    )
    box_style = "ascii" if ascii_only else "unicode"

    width = console.width if console_given else _detect_width()
    layout = "narrow" if width < _NARROW_WIDTH_THRESHOLD else "normal"

    return Capabilities(
        no_color=no_color,
        box_style=box_style,
        width=width,
        layout=layout,
        color_system=console.color_system,
    )


__all__ = ["Capabilities", "probe_capabilities"]
