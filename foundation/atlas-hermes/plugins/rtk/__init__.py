"""RTK (Rust Token Killer) — terminal output compression plugin.

Pipes terminal output through `rtk pipe` to reduce token consumption by 60-90%.
Fail-safe: returns original output on any error.

Disable per-env: set ATLAS_RTK_DISABLED=1
"""
from __future__ import annotations

import logging
import os
import shutil
import subprocess

logger = logging.getLogger(__name__)

_RTK_TIMEOUT = 5  # seconds


def _rtk_available() -> bool:
    return shutil.which("rtk") is not None


def _compress_output(output: str, command: str) -> str | None:
    """Pipe output through rtk pipe. Returns compressed output or None on failure."""
    if not output or not output.strip():
        return None
    if os.getenv("ATLAS_RTK_DISABLED", "").strip().lower() in {"1", "true", "yes"}:
        return None
    if not _rtk_available():
        return None

    try:
        proc = subprocess.run(
            ["rtk", "pipe"],
            input=output,
            capture_output=True,
            text=True,
            timeout=_RTK_TIMEOUT,
        )
        if proc.returncode == 0 and proc.stdout:
            compressed = proc.stdout
            # Only use compressed version if it's actually smaller
            if len(compressed) < len(output):
                return compressed
    except (subprocess.TimeoutExpired, OSError) as exc:
        logger.debug("RTK pipe failed: %s", exc)
    return None


def register(ctx):
    """Register the transform_terminal_output hook."""

    def _on_transform_terminal_output(*, command: str, output: str, **_kwargs) -> str | None:
        return _compress_output(output, command)

    ctx.register_hook("transform_terminal_output", _on_transform_terminal_output)
