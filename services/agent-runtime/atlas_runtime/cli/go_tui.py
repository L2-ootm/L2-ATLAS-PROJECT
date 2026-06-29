"""Resolve and launch the Go/BubbleTea ATLAS workbench.

The launcher is intentionally tiny: deterministic binary resolution, argv-only
subprocess dispatch, and inherited terminal handles. The Go sidecar remains a
client of the Rust gateway; no runtime logic lives here.
"""
from __future__ import annotations

import os
import pathlib
import shutil
import subprocess

DEFAULT_GATEWAY_URL = "http://127.0.0.1:8484"


class TUILaunchError(RuntimeError):
    """The Go TUI cannot be resolved or started."""


def binary_name() -> str:
    return "atlas-tui.exe" if os.name == "nt" else "atlas-tui"


def atlas_home() -> pathlib.Path:
    configured = os.environ.get("ATLAS_HOME", "").strip()
    return pathlib.Path(configured).expanduser() if configured else pathlib.Path.home() / ".atlas"


def _repo_root() -> pathlib.Path | None:
    for parent in pathlib.Path(__file__).resolve().parents:
        if (parent / "services" / "atlas-tui" / "go.mod").is_file():
            return parent
    return None


def _usable(path: pathlib.Path | None) -> bool:
    return path is not None and path.is_file()


def resolve_binary() -> pathlib.Path:
    """Resolve atlas-tui in the documented precedence order."""
    override = os.environ.get("ATLAS_TUI_BIN", "").strip()
    if override:
        candidate = pathlib.Path(override).expanduser()
        if _usable(candidate):
            return candidate

    owned = atlas_home() / "bin" / binary_name()
    if _usable(owned):
        return owned

    repo = _repo_root()
    if repo is not None:
        checkout = repo / "services" / "atlas-tui" / binary_name()
        if _usable(checkout):
            return checkout

    found = shutil.which("atlas-tui")
    if found:
        return pathlib.Path(found)

    raise TUILaunchError(
        "atlas-tui binary not found. Run `scripts/install-atlas-cli.ps1` on "
        "Windows or `scripts/setup.sh` on POSIX, or set ATLAS_TUI_BIN."
    )


def launch(gateway_url: str | None = None) -> int:
    """Launch the sidecar with inherited stdin/stdout/stderr and no shell."""
    binary = resolve_binary()
    gateway = (
        gateway_url
        or os.environ.get("ATLAS_GATEWAY_URL", "").strip()
        or DEFAULT_GATEWAY_URL
    )
    try:
        completed = subprocess.run(
            [os.fspath(binary), "--gateway", gateway],
            check=False,
        )
    except OSError as exc:
        raise TUILaunchError(f"failed to start atlas-tui: {exc}") from exc
    return int(completed.returncode)


__all__ = [
    "DEFAULT_GATEWAY_URL",
    "TUILaunchError",
    "atlas_home",
    "binary_name",
    "launch",
    "resolve_binary",
]
