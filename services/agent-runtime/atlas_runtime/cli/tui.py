"""atlas dev-foundation-tui — run the legacy vendored terminal client from source.

# provenance: thin wrapper over the vendored foundation Ink TUI (D-001: import
# and use the foundation, never edit it). Locates ``foundation/atlas-hermes``,
# imports its launcher entry point, and hands off. The interactive client keeps
# its own legacy config; only explicit ``--model`` / ``--provider`` overrides
# are forwarded. ATLAS-config-driven model selection lives in the native agent
# path (A4), not this checkout-only escape hatch, because the legacy client
# uses a different provider namespace.

Superseded by the native workbench (``atlas`` / ``atlas tui``); retained only
behind the hidden ``dev-foundation-tui`` command for checkout-only development.

The launcher resolution is factored into ``_resolve_launcher`` so tests can
patch it without the legacy vendored tree being importable.
"""
from __future__ import annotations

import importlib.util
import pathlib
import sys
from typing import Callable, Optional

import typer


def _foundation_dir() -> Optional[pathlib.Path]:
    # provenance: foundation/atlas-hermes is the actual vendored directory name on disk (D-001).
    """Walk up from this file to locate the vendored legacy source tree."""
    for parent in pathlib.Path(__file__).resolve().parents:
        candidate = parent / "foundation" / "atlas-hermes"
        if candidate.is_dir():
            return candidate
    return None


def _resolve_launcher() -> Callable[..., object]:
    """Import the legacy vendored TUI launcher. Raises RuntimeError on failure."""
    foundation = _foundation_dir()
    if foundation is None:
        raise RuntimeError(
            "legacy vendored TUI source tree not found (run from within the ATLAS repo checkout)."
        )
    # Normally editable-installed in the ATLAS venv; fall back to importing
    # straight from the vendored tree when it is not on the path.
    # provenance: hermes_cli is the import name of the vendored legacy package on disk (D-001).
    if importlib.util.find_spec("hermes_cli") is None and str(foundation) not in sys.path:
        sys.path.insert(0, str(foundation))
    from hermes_cli.main import _launch_tui  # noqa: PLC0415 — lazy, optional dep

    return _launch_tui


def legacy_foundation_tui(
    model: Optional[str] = typer.Option(
        None, "--model", help="Model override for this session."
    ),
    provider: Optional[str] = typer.Option(
        None, "--provider", help="Provider override for this session."
    ),
    dev: bool = typer.Option(
        False, "--dev", help="Run from source with hot reload (checkout only)."
    ),
) -> None:
    """Run the legacy vendored terminal client from source (checkout-only; superseded by the native workbench)."""
    try:
        launch = _resolve_launcher()
    except Exception as exc:  # noqa: BLE001 — surface a clean operator message
        typer.echo(f"terminal UI unavailable: {exc}", err=True)
        raise typer.Exit(1)
    launch(model=model, provider=provider, tui_dev=dev)
