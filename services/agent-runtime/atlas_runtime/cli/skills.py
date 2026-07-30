"""ATLAS CLI — atlas skills list|set-tier subcommands.

Thin wrapper only (D-022): scanning/parsing logic lives in
atlas_runtime.skill_manifest. Backs the gateway's dispatch-only
GET /api/skills and PUT /api/skills/tier routes
(native/atlas-core-rs/crates/atlas-gateway/src/lib.rs).
"""

from __future__ import annotations

import json
import sqlite3
import threading

import typer
from atlas_core.schemas.control_plane import ControlPlaneError

skills_app = typer.Typer(name="skills", help="Discover and manage ATLAS skills.")


def _get_connection() -> sqlite3.Connection:
    from atlas_runtime.cli import main

    return main._get_connection()


def _get_lock() -> threading.Lock:
    from atlas_runtime.cli import main

    return main._get_lock()


def _render_control_error(exc: ControlPlaneError) -> None:
    error: dict[str, object] = {
        "code": exc.code,
        "message": exc.message,
        "remediation": exc.remediation,
    }
    if exc.field is not None:
        error["field"] = exc.field
    typer.echo(json.dumps({"error": error}, ensure_ascii=False), err=True)


@skills_app.command("list")
def skills_list_cmd(
    json_output: bool = typer.Option(
        False, "--json", help="Emit {\"skills\": [...], \"total\": N} as JSON."
    ),
) -> None:
    """List all discovered skills (ATLAS-native + bundled framework skills)."""
    from atlas_runtime import skill_manifest

    try:
        skills = skill_manifest.scan_skills()
    except RuntimeError as exc:
        typer.echo(f"Error: {exc}", err=True)
        raise typer.Exit(1)

    if json_output:
        typer.echo(json.dumps({"skills": skills, "total": len(skills)}))
        return

    if not skills:
        typer.echo("no skills found")
        return

    header = f"{'ID':<48} {'NAME':<22} {'CATEGORY':<16} {'TIER':<12} PROVENANCE"
    typer.echo(header)
    typer.echo("-" * len(header))
    for s in skills:
        typer.echo(
            f"{s['id']:<48} {s['name']:<22} {s['category']:<16} "
            f"{s['loading_tier']:<12} {s['provenance']['tier']}"
        )
    typer.echo(f"\n{len(skills)} skill(s)")


@skills_app.command("set-tier")
def skills_set_tier_cmd(
    skill_id: str = typer.Option(
        ..., "--id", help="Skill id, as printed by 'atlas skills list' (its relative dir path)."
    ),
    tier: str = typer.Option(..., "--tier", help="full | name-only | deactivated"),
    expected_tier: str | None = typer.Option(
        None,
        "--expected-tier",
        help="Reject the write if the effective tier changed since it was read.",
    ),
    reason: str = typer.Option(
        "operator changed the skill loading tier",
        "--reason",
        help="Human-readable audit reason.",
    ),
    source_surface: str = typer.Option(
        "cli",
        "--source-surface",
        help="Originating operator surface (for the durable receipt).",
    ),
) -> None:
    """Set a skill tier through the guarded, audited control-plane path."""
    from atlas_runtime import skill_control_service

    try:
        receipt = skill_control_service.set_tier(
            _get_connection(),
            _get_lock(),
            skill_id=skill_id,
            tier=tier,
            expected_tier=expected_tier,
            reason=reason,
            source_surface=source_surface,
        )
    except ControlPlaneError as exc:
        _render_control_error(exc)
        raise typer.Exit(1)
    typer.echo(receipt.model_dump_json())
