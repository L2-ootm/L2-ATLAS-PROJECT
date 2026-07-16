"""Centralized logging for the ATLAS runtime (deep-audit F13).

One rotating file under `<ATLAS_HOME>/logs/atlas.log` shared by every entry
point (CLI, runtime daemon, gateway-dispatched subprocesses). Attaches to the
`atlas_runtime` package logger — never the root logger — so embedding hosts
keep their own logging untouched.

Knobs:
  ATLAS_LOG_LEVEL  DEBUG | INFO | WARNING | ERROR   (default INFO)
  ATLAS_LOG_DIR    directory override                (default <ATLAS_HOME>/logs)

Fail-open by design: an unwritable log directory must never break a command.
"""
from __future__ import annotations

import logging
import logging.handlers
import os
import pathlib

_MAX_BYTES = 5 * 1024 * 1024
_BACKUP_COUNT = 3
_FORMAT = "%(asctime)s %(levelname)s %(name)s: %(message)s"

_configured = False


def _default_log_dir() -> pathlib.Path:
    env_dir = os.environ.get("ATLAS_LOG_DIR", "").strip()
    if env_dir:
        return pathlib.Path(env_dir).expanduser()
    home = os.environ.get("ATLAS_HOME", "").strip()
    base = pathlib.Path(home) if home else pathlib.Path.home() / ".atlas"
    return base / "logs"


def log_file_path() -> pathlib.Path:
    """Resolve `<ATLAS_HOME>/logs/atlas.log` at call time (ATLAS_LOG_DIR/ATLAS_HOME-aware)."""
    return _default_log_dir() / "atlas.log"


def configure_logging(
    *,
    level: str | None = None,
    log_dir: pathlib.Path | None = None,
) -> logging.Handler | None:
    """Attach the rotating file handler once per process; return it (or None).

    Idempotent: repeated calls (CLI callback + daemon serve in one process)
    are no-ops after the first.
    """
    global _configured
    if _configured:
        return None
    _configured = True

    level_name = (level or os.environ.get("ATLAS_LOG_LEVEL", "INFO")).upper()
    resolved_level = getattr(logging, level_name, logging.INFO)

    try:
        directory = log_dir or _default_log_dir()
        directory.mkdir(parents=True, exist_ok=True)
        handler = logging.handlers.RotatingFileHandler(
            directory / "atlas.log",
            maxBytes=_MAX_BYTES,
            backupCount=_BACKUP_COUNT,
            encoding="utf-8",
        )
    except OSError:
        return None

    handler.setFormatter(logging.Formatter(_FORMAT))
    package_logger = logging.getLogger("atlas_runtime")
    package_logger.setLevel(resolved_level)
    package_logger.addHandler(handler)
    return handler


def reset_for_tests() -> None:
    """Detach handlers and re-arm configure_logging (test isolation only)."""
    global _configured
    _configured = False
    package_logger = logging.getLogger("atlas_runtime")
    for handler in list(package_logger.handlers):
        package_logger.removeHandler(handler)
        handler.close()
