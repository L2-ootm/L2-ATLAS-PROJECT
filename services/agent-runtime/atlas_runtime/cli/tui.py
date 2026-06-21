"""atlas tui — launch the ATLAS terminal UI.

Thin wrapper over the vendored foundation Ink TUI (D-001: import and use the
foundation, never edit it). Locates ``foundation/atlas-hermes``, imports its
``_launch_tui`` entry point, and hands off. The interactive TUI keeps its own
foundation config (``~/.hermes/config.yaml``) and ATLAS skin; only explicit
``--model`` / ``--provider`` overrides are forwarded. ATLAS-config-driven model
selection lives in the native agent path (A4), not this interactive surface,
because the foundation uses a different provider namespace.

The launcher resolution is factored into ``_resolve_launcher`` so tests can
patch it without the foundation being importable.
"""
from __future__ import annotations

import importlib.util
import pathlib
import sys
from typing import Callable, Optional

import typer


def _foundation_dir() -> Optional[pathlib.Path]:
    """Walk up from this file to locate foundation/atlas-hermes."""
    for parent in pathlib.Path(__file__).resolve().parents:
        candidate = parent / "foundation" / "atlas-hermes"
        if candidate.is_dir():
            return candidate
    return None


def _resolve_launcher() -> Callable[..., object]:
    """Import the foundation TUI launcher. Raises RuntimeError on failure."""
    foundation = _foundation_dir()
    if foundation is None:
        raise RuntimeError(
            "foundation/atlas-hermes not found (run from within the ATLAS repo)."
        )
    # Normally editable-installed in the ATLAS venv; fall back to importing
    # straight from the vendored tree when it is not on the path.
    if importlib.util.find_spec("hermes_cli") is None and str(foundation) not in sys.path:
        sys.path.insert(0, str(foundation))
    from hermes_cli.main import _launch_tui  # noqa: PLC0415 — lazy, optional dep

    return _launch_tui


def tui(
    model: Optional[str] = typer.Option(
        None, "--model", help="Model override for this TUI session."
    ),
    provider: Optional[str] = typer.Option(
        None, "--provider", help="Provider override for this TUI session."
    ),
    dev: bool = typer.Option(
        False, "--dev", help="Run the TUI from source with hot reload (checkout only)."
    ),
) -> None:
    """Launch the ATLAS terminal UI (the foundation Ink TUI, ATLAS-skinned)."""
    try:
        launch = _resolve_launcher()
    except Exception as exc:  # noqa: BLE001 — surface a clean operator message
        typer.echo(f"terminal UI unavailable: {exc}", err=True)
        raise typer.Exit(1)
    launch(model=model, provider=provider, tui_dev=dev)
