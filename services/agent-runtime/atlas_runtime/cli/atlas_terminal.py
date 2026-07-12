"""Resolve and launch the atlas-terminal (Bun/donor) TUI surface.

The launcher is intentionally tiny: deterministic checkout resolution, argv-only
subprocess dispatch, and inherited terminal handles. atlas-terminal remains a
client of the Rust gateway; no runtime logic lives here. The legacy Go TUI
launcher (go_tui.py) stays intact as the fallback until UAT retires it.
"""
from __future__ import annotations

import os
import pathlib
import shutil
import subprocess

DEFAULT_GATEWAY_URL = "http://127.0.0.1:8484"


class TerminalLaunchError(RuntimeError):
    """atlas-terminal cannot be resolved or started."""


def _repo_root() -> pathlib.Path | None:
    for parent in pathlib.Path(__file__).resolve().parents:
        if (parent / "services" / "atlas-terminal" / "package.json").is_file():
            return parent
    return None


def resolve_terminal_dir() -> pathlib.Path:
    """Resolve the atlas-terminal checkout directory."""
    override = os.environ.get("ATLAS_TERMINAL_DIR", "").strip()
    if override:
        candidate = pathlib.Path(override).expanduser()
        if (candidate / "package.json").is_file():
            return candidate

    repo = _repo_root()
    if repo is not None:
        return repo / "services" / "atlas-terminal"

    raise TerminalLaunchError(
        "atlas-terminal checkout not found. Run from a repo checkout or set "
        "ATLAS_TERMINAL_DIR to the atlas-terminal directory."
    )


def launch(gateway_url: str | None = None) -> int:
    """Launch atlas-terminal with inherited stdin/stdout/stderr and no shell.

    The gateway URL is forwarded as ATLAS_GATEWAY_URL (read by src/main.tsx);
    ATLAS_HOME and the rest of the environment pass through untouched.
    """
    terminal_dir = resolve_terminal_dir()
    if not (terminal_dir / "node_modules").is_dir():
        raise TerminalLaunchError(
            "atlas-terminal is not built. Run: cd services/atlas-terminal && bun install"
        )
    bun = shutil.which("bun")
    if not bun:
        raise TerminalLaunchError(
            "bun not found on PATH. Install Bun (https://bun.sh) or run "
            "scripts/install-atlas-cli.ps1."
        )
    env = os.environ.copy()
    env["ATLAS_GATEWAY_URL"] = (
        gateway_url
        or env.get("ATLAS_GATEWAY_URL", "").strip()
        or DEFAULT_GATEWAY_URL
    )
    try:
        # `bun run dev` = `bun run --conditions=browser src/main.tsx` — the
        # package script is the single source of truth for the entry flags.
        completed = subprocess.run(
            [bun, "run", "dev"],
            cwd=os.fspath(terminal_dir),
            env=env,
            check=False,
        )
    except OSError as exc:
        raise TerminalLaunchError(f"failed to start atlas-terminal: {exc}") from exc
    return int(completed.returncode)


__all__ = [
    "DEFAULT_GATEWAY_URL",
    "TerminalLaunchError",
    "launch",
    "resolve_terminal_dir",
]
