"""ATLAS CLI — atlas skills list|set-tier subcommands.

Thin wrapper only (D-022): scanning/parsing logic lives in
atlas_runtime.skill_manifest. Backs the gateway's dispatch-only
GET /api/skills and PUT /api/skills/tier routes
(native/atlas-core-rs/crates/atlas-gateway/src/lib.rs).
"""

from __future__ import annotations

import json

import typer

skills_app = typer.Typer(name="skills", help="Discover and manage ATLAS skills.")


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
) -> None:
    """Set a skill's loading tier (persisted at <ATLAS_HOME>/skill_tiers.json)."""
    from atlas_runtime import skill_manifest

    try:
        skill_manifest.set_skill_tier(skill_id, tier)
    except ValueError as exc:
        typer.echo(f"Error: {exc}", err=True)
        raise typer.Exit(1)
    typer.echo("updated")
