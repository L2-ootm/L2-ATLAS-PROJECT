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


def _checkout_sources(tui_dir: pathlib.Path) -> list[pathlib.Path]:
    sources = [tui_dir / "go.mod", tui_dir / "go.sum"]
    sources.extend(tui_dir.rglob("*.go"))
    return [path for path in sources if path.is_file()]


def _checkout_binary_stale(tui_dir: pathlib.Path, binary: pathlib.Path) -> bool:
    if not binary.is_file():
        return True
    sources = _checkout_sources(tui_dir)
    return bool(sources) and max(path.stat().st_mtime for path in sources) > binary.stat().st_mtime


def _source_commit(repo: pathlib.Path) -> str:
    git = shutil.which("git")
    if not git or not (repo / ".git").exists():
        return "source"
    completed = subprocess.run(
        [git, "rev-parse", "--short", "HEAD"],
        cwd=repo,
        capture_output=True,
        text=True,
        check=False,
    )
    commit = completed.stdout.strip()
    return commit if completed.returncode == 0 and commit else "source"


def _build_checkout(tui_dir: pathlib.Path, binary: pathlib.Path) -> pathlib.Path:
    go = shutil.which("go")
    if not go:
        raise TUILaunchError(
            "atlas-tui source is newer than its binary and Go is unavailable. "
            "Install Go 1.26+ or run scripts/install-atlas-cli.ps1."
        )
    commit = _source_commit(tui_dir.parents[1])
    completed = subprocess.run(
        [
            go,
            "build",
            "-trimpath",
            "-ldflags",
            f"-s -w -X main.version=dev -X main.commit={commit}",
            "-o",
            os.fspath(binary),
            ".",
        ],
        cwd=tui_dir,
        capture_output=True,
        text=True,
        check=False,
    )
    if completed.returncode or not binary.is_file():
        detail = completed.stderr.strip() or f"exit {completed.returncode}"
        raise TUILaunchError(f"failed to rebuild stale atlas-tui: {detail}")
    return binary


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
        tui_dir = repo / "services" / "atlas-tui"
        checkout = tui_dir / binary_name()
        if (tui_dir / "go.mod").is_file():
            if _checkout_binary_stale(tui_dir, checkout):
                return _build_checkout(tui_dir, checkout)
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
