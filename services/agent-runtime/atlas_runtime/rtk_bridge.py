"""RTK bridge — Python-native integration for command output compression.

Provides `rewrite_command()` and `compress_output()` for direct use by
tool_service.py and terminal_tool.py. Fail-safe: returns original
values on any error.

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


def available() -> bool:
    """Return True if the rtk CLI is on PATH."""
    return shutil.which("rtk") is not None


def _disabled() -> bool:
    # 1. Env var takes precedence (immediate override)
    if os.getenv("ATLAS_RTK_DISABLED", "").strip().lower() in {"1", "true", "yes"}:
        return True

    # 2. Check config file (cached after first read)
    global _config_cache
    if _config_cache is not None:
        return not _config_cache

    try:
        import yaml
        config_path = os.environ.get("ATLAS_CONFIG_PATH", "")
        if not config_path:
            atlas_home = os.environ.get("ATLAS_HOME", os.path.expanduser("~/.atlas"))
            config_path = os.path.join(atlas_home, "config.yaml")
        if os.path.exists(config_path):
            with open(config_path) as f:
                cfg = yaml.safe_load(f) or {}
            rtk_cfg = cfg.get("rtk", {})
            _config_cache = rtk_cfg.get("enabled", True)  # default: enabled
        else:
            _config_cache = True  # no config = enabled
    except Exception:
        _config_cache = True  # error = enabled (fail-open)

    return not _config_cache


def rewrite_command(command: str) -> str:
    """Rewrite a shell command to its RTK equivalent.

    Returns the original command if RTK is unavailable, disabled, or
    the command has no RTK equivalent (exit code 1).
    """
    if not command or _disabled() or not available():
        return command
    try:
        proc = subprocess.run(
            ["rtk", "rewrite", *command.split()],
            capture_output=True,
            text=True,
            timeout=_RTK_TIMEOUT,
        )
        # rtk rewrite exits 0 on success, 1 if no equivalent.
        # On Windows, exit codes may differ; check stdout instead.
        stdout = proc.stdout.strip()
        if stdout and not stdout.startswith("error"):
            return stdout
    except (subprocess.TimeoutExpired, OSError) as exc:
        logger.debug("RTK rewrite failed: %s", exc)
    return command


def compress_output(output: str, *, filter_name: str = "") -> str:
    """Pipe output through rtk pipe for compression.

    Returns the original output if RTK is unavailable, disabled, or
    the compressed version is not actually smaller.
    """
    if not output or not output.strip() or _disabled() or not available():
        return output
    try:
        cmd = ["rtk", "pipe"]
        if filter_name:
            cmd.extend(["--filter", filter_name])
        proc = subprocess.run(
            cmd,
            input=output,
            capture_output=True,
            text=True,
            timeout=_RTK_TIMEOUT,
        )
        if proc.returncode == 0 and proc.stdout:
            compressed = proc.stdout
            if len(compressed) < len(output):
                return compressed
    except (subprocess.TimeoutExpired, OSError) as exc:
        logger.debug("RTK pipe failed: %s", exc)
    return output


__all__ = ["available", "rewrite_command", "compress_output"]
