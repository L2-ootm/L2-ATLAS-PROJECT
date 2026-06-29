"""Immutable catastrophic-action floor shared by every ATLAS surface.

Adapted from the guard ordering and adversarial cases in Hermes
``tools/approval.py``. ATLAS owns these symbols and the evaluator; no Hermes
approval state or storage is imported.
"""

from __future__ import annotations

import pathlib
import re
from dataclasses import dataclass
from typing import Iterable

HARDLINE_VERSION = "2026-06-29"


@dataclass(frozen=True)
class HardlineMatch:
    rule_id: str
    reason_code: str


_FORK_BOMB = re.compile(r"^\s*:\s*\(\s*\)\s*\{\s*:\s*\|\s*:\s*&\s*\}\s*;\s*:\s*$")
_POSIX_ROOT_DELETE = re.compile(
    r"(?:^|[;&|]\s*)(?:sudo\s+)?rm\s+(?:-[a-z]*r[a-z]*f[a-z]*|-[a-z]*f[a-z]*r[a-z]*)\s+/(?:\*+)?\s*$",
    re.IGNORECASE,
)
_WINDOWS_ROOT_DELETE = re.compile(
    r"(?:remove-item|del|rmdir|rd)\b[^\r\n]*(?:[a-z]:[\\/])\s*(?:[;&|]|$)",
    re.IGNORECASE,
)
_BLOCK_DEVICE = (
    re.compile(r"(?:^|[;&|]\s*)format(?:\.com)?\s+[a-z]:\s", re.IGNORECASE),
    re.compile(r"(?:^|[;&|]\s*)mkfs(?:\.[a-z0-9]+)?\s+/dev/", re.IGNORECASE),
    re.compile(
        r"(?:^|[;&|]\s*)dd\s+[^;\r\n]*\bof=/dev/(?:sd|hd|vd|nvme)", re.IGNORECASE
    ),
    re.compile(
        r"(?:^|[;&|]\s*)diskpart\b[^\r\n]*(?:clean|/s\s+\S*clean)", re.IGNORECASE
    ),
)
_SHUTDOWN = (
    re.compile(r"(?:^|[;&|]\s*)shutdown(?:\.exe)?(?:\s|$)", re.IGNORECASE),
    re.compile(r"(?:^|[;&|]\s*)reboot(?:\s|$)", re.IGNORECASE),
    re.compile(r"(?:^|[;&|]\s*)stop-computer(?:\s|$)", re.IGNORECASE),
    re.compile(r"(?:^|[;&|]\s*)restart-computer(?:\s|$)", re.IGNORECASE),
)


def _is_filesystem_root(value: str) -> bool:
    raw = value.strip()
    if raw in {"/", "/*"}:
        return True
    if re.fullmatch(r"[A-Za-z]:[\\/]*", raw):
        return True
    try:
        path = pathlib.Path(raw)
        return bool(path.is_absolute() and path == pathlib.Path(path.anchor))
    except (OSError, ValueError):
        return False


def match_hardline(
    *,
    command: str | None = None,
    target_paths: Iterable[str] = (),
) -> HardlineMatch | None:
    """Return the first immutable hardline match, or ``None``.

    Command guards are intentionally narrow and anchored to executable positions
    so documentation/echo strings do not become false positives.
    """
    text = (command or "").strip()
    if text:
        if _FORK_BOMB.fullmatch(text):
            return HardlineMatch("hardline:fork-bomb", "hardline_fork_bomb")
        if _POSIX_ROOT_DELETE.search(text) or _WINDOWS_ROOT_DELETE.search(text):
            return HardlineMatch(
                "hardline:filesystem-root",
                "hardline_filesystem_root",
            )
        if any(pattern.search(text) for pattern in _BLOCK_DEVICE):
            return HardlineMatch(
                "hardline:block-device",
                "hardline_block_device",
            )
        if any(pattern.search(text) for pattern in _SHUTDOWN):
            return HardlineMatch(
                "hardline:system-shutdown",
                "hardline_system_shutdown",
            )
    if any(_is_filesystem_root(path) for path in target_paths):
        return HardlineMatch(
            "hardline:filesystem-root",
            "hardline_filesystem_root",
        )
    return None


__all__ = ["HARDLINE_VERSION", "HardlineMatch", "match_hardline"]
