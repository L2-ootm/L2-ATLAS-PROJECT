"""atlas foundation subcommands — operator surface for the vendored
ATLAS/Hermes foundation (D-018, D-021 section 9).

Thin wrappers only: status inspection and smoke-test dispatch. No SQL.
"""
from __future__ import annotations

import importlib.util
import pathlib
import re
import subprocess
import sys

import typer

foundation_app = typer.Typer(
    name="foundation",
    help="Inspect and verify the vendored ATLAS foundation (foundation/atlas-hermes).",
)

PINNED_SHA = "e8b9369a9d2df36139a5055cae3ed3c15691e03e"


def _repo_root() -> pathlib.Path | None:
    """Walk up from this file looking for foundation/atlas-hermes."""
    for parent in pathlib.Path(__file__).resolve().parents:
        if (parent / "foundation" / "atlas-hermes").is_dir():
            return parent
    return None


@foundation_app.command("status")
def status() -> None:
    """Show foundation vendor status: SHA, install state, audit plugin, divergences."""
    root = _repo_root()
    if root is None:
        typer.echo(
            "foundation/atlas-hermes not found (run from within the ATLAS repo)",
            err=True,
        )
        raise typer.Exit(1)
    vendor = root / "foundation" / "atlas-hermes"
    typer.echo(f"vendor:               {vendor}")
    typer.echo(f"pinned upstream SHA:  {PINNED_SHA} (NousResearch/hermes-agent, MIT)")
    installed = importlib.util.find_spec("hermes_cli") is not None
    typer.echo(
        "installed:            "
        + ("yes" if installed else "no — pip install -e foundation/atlas-hermes")
    )
    plugin = vendor / "plugins" / "atlas_audit" / "plugin.yaml"
    typer.echo(f"audit plugin bundled: {'yes' if plugin.is_file() else 'NO'}")
    log = root / "foundation" / "DIVERGENCE_LOG.md"
    if log.is_file():
        count = len(re.findall(r"^## DIV-F-", log.read_text(encoding="utf-8"), re.MULTILINE))
        typer.echo(f"divergences logged:   {count}")


@foundation_app.command("smoke")
def smoke() -> None:
    """Run the foundation boot smoke test (scripts/foundation_boot_smoke.py)."""
    root = _repo_root()
    if root is None:
        typer.echo("foundation/atlas-hermes not found", err=True)
        raise typer.Exit(1)
    result = subprocess.run(
        [sys.executable, str(root / "scripts" / "foundation_boot_smoke.py")]
    )
    raise typer.Exit(result.returncode)
