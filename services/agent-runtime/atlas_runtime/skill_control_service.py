"""Audited control-plane mutations for the discovered skill catalog."""

from __future__ import annotations

import sqlite3
import threading
from typing import Literal

from atlas_core.schemas.control_plane import ControlPlaneError
from pydantic import BaseModel, ConfigDict

from atlas_runtime import audit_service, mission_service, skill_manifest


class SkillTierReceipt(BaseModel):
    """Durable receipt returned to operator surfaces after a tier change."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    receipt_id: str
    resource_type: Literal["skill"] = "skill"
    resource_id: str
    resource_name: str
    action: Literal["set_loading_tier"] = "set_loading_tier"
    before: str
    after: str
    actor: str
    reason: str
    timestamp: str
    status: Literal["committed"] = "committed"


def set_tier(
    conn: sqlite3.Connection,
    audit_lock: threading.Lock,
    *,
    skill_id: str,
    tier: str,
    expected_tier: str | None,
    reason: str,
    source_surface: str,
) -> SkillTierReceipt:
    """Validate, conflict-check, commit, and audit one skill tier mutation."""
    catalog = skill_manifest.scan_skills()
    skill = next((item for item in catalog if item["id"] == skill_id), None)
    if skill is None:
        raise ControlPlaneError(
            "skill_not_found",
            f"unknown skill {skill_id!r}",
            "reload the skill catalog and choose a discovered skill",
            field="id",
        )

    actor = source_surface.strip() or "cli"
    mutation_reason = reason.strip() or "operator changed the skill loading tier"
    if len(mutation_reason) > 500:
        raise ControlPlaneError(
            "skill_reason_too_long",
            "skill tier change reason exceeds 500 characters",
            "shorten the reason and retry",
            field="reason",
        )

    try:
        before, _overrides = skill_manifest.commit_skill_tier(
            skill_id,
            tier,
            expected_tier=expected_tier,
        )
    except skill_manifest.SkillTierConflictError as exc:
        raise ControlPlaneError(
            "skill_tier_conflict",
            (
                f"skill tier changed from expected {expected_tier!r} "
                f"to {exc.current_tier!r}"
            ),
            "reload the skill catalog and retry against the current tier",
            field="expected_tier",
        ) from exc
    except ValueError as exc:
        raise ControlPlaneError(
            "skill_tier_invalid",
            str(exc),
            "use full, name-only, or deactivated",
            field="tier",
        ) from exc

    try:
        run_id = mission_service.ensure_operator_run(conn, audit_lock)
        event = audit_service.emit(
            conn,
            audit_lock,
            run_id=run_id,
            event_type="config_change",
            data={
                "resource_type": "skill",
                "resource_id": skill_id,
                "resource_name": skill["name"],
                "changed_paths": [f"skills.{skill_id}.loading_tier"],
                "before": {"loading_tier": before},
                "after": {"loading_tier": tier},
                "source_surface": actor,
                "reason": mutation_reason,
            },
        )
    except Exception as exc:
        raise ControlPlaneError(
            "skill_tier_audit_failed",
            (
                f"skill tier {tier!r} was committed for {skill_id!r}, "
                "but its audit receipt failed"
            ),
            (
                "the tier is already committed; inspect the audit database "
                "and reconcile before retrying"
            ),
        ) from exc

    event_json = event.model_dump(mode="json")
    return SkillTierReceipt(
        receipt_id=event.id,
        resource_id=skill_id,
        resource_name=str(skill["name"]),
        before=before,
        after=tier,
        actor=actor,
        reason=mutation_reason,
        timestamp=str(event_json["timestamp"]),
    )
