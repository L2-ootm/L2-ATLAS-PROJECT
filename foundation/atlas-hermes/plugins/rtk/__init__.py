"""RTK (Rust Token Killer) — terminal output compression plugin.

Pipes terminal output through `rtk pipe` to reduce token consumption by 60-90%.
Fail-safe: returns original output on any error.

Disable: set ATLAS_RTK_DISABLED=1 or config rtk.enabled=false
"""
from __future__ import annotations

import logging
import os
import shutil
import subprocess

logger = logging.getLogger(__name__)

_RTK_TIMEOUT = 5  # seconds
_config_cache: bool | None = None


def _rtk_available() -> bool:
    return shutil.which("rtk") is not None


def _disabled() -> bool:
    global _config_cache
    # 1. Env var takes precedence
    if os.getenv("ATLAS_RTK_DISABLED", "").strip().lower() in {"1", "true", "yes"}:
        return True
    # 2. Check config (cached)
    if _config_cache is not None:
        return not _config_cache
    try:
        import yaml
        config_path = os.environ.get("ATLAS_CONFIG_PATH", "")
        if not config_path:
            atlas_home = os.environ.get("ATLAS_HOME", os.path.expanduser("~/.hermes"))
            config_path = os.path.join(atlas_home, "config.yaml")
        if os.path.exists(config_path):
            with open(config_path) as f:
                cfg = yaml.safe_load(f) or {}
            rtk_cfg = cfg.get("rtk", {})
            _config_cache = rtk_cfg.get("enabled", True)
        else:
            _config_cache = True
    except Exception:
        _config_cache = True
    return not _config_cache


def _compress_output(output: str, command: str) -> str | None:
    """Pipe output through rtk pipe. Returns compressed output or None on failure."""
    if not output or not output.strip():
        return None
    if _disabled():
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
