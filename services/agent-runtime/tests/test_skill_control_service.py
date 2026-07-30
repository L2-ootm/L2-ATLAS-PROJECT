from __future__ import annotations

import json
from pathlib import Path

import pytest
from atlas_core.schemas.control_plane import ControlPlaneError

from atlas_runtime import skill_control_service


def test_set_tier_emits_durable_before_after_receipt(
    db, lock, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("ATLAS_HOME", str(tmp_path))

    receipt = skill_control_service.set_tier(
        db,
        lock,
        skill_id="skills/atlas/gsd",
        tier="name-only",
        expected_tier="full",
        reason="reduce prompt footprint",
        source_surface="cockpit.skills",
    )

    assert receipt.before == "full"
    assert receipt.after == "name-only"
    assert receipt.actor == "cockpit.skills"
    assert receipt.reason == "reduce prompt footprint"
    row = db.execute(
        "SELECT id, event_type, data FROM audit_events WHERE id=?",
        (receipt.receipt_id,),
    ).fetchone()
    assert row[:2] == (receipt.receipt_id, "config_change")
    payload = json.loads(row[2])
    assert payload["resource_type"] == "skill"
    assert payload["before"] == {"loading_tier": "full"}
    assert payload["after"] == {"loading_tier": "name-only"}


def test_set_tier_rejects_unknown_skill_without_creating_override(
    db, lock, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("ATLAS_HOME", str(tmp_path))

    with pytest.raises(ControlPlaneError) as caught:
        skill_control_service.set_tier(
            db,
            lock,
            skill_id="skills/atlas/not-real",
            tier="deactivated",
            expected_tier="full",
            reason="test",
            source_surface="cockpit.skills",
        )

    assert caught.value.code == "skill_not_found"
    assert not (tmp_path / "skill_tiers.json").exists()


def test_set_tier_reports_committed_state_when_audit_fails(
    db, lock, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("ATLAS_HOME", str(tmp_path))

    def fail_audit(*args, **kwargs):
        raise RuntimeError("audit unavailable")

    monkeypatch.setattr(skill_control_service.audit_service, "emit", fail_audit)
    with pytest.raises(ControlPlaneError) as caught:
        skill_control_service.set_tier(
            db,
            lock,
            skill_id="skills/atlas/gsd",
            tier="deactivated",
            expected_tier="full",
            reason="test failure truth",
            source_surface="cockpit.skills",
        )

    assert caught.value.code == "skill_tier_audit_failed"
    assert "already committed" in caught.value.remediation
    stored = json.loads((tmp_path / "skill_tiers.json").read_text(encoding="utf-8"))
    assert stored["skills/atlas/gsd"] == "deactivated"
