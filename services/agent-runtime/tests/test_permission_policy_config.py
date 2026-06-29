"""Permission policy integration tests for the revisioned control plane."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from atlas_runtime import config_service, control_plane_service
from atlas_runtime.config_service import ControlPlaneError
from atlas_core.schemas.control_plane import PermissionConfig
from atlas_core.schemas.surface_session import EventKind, SurfaceEvent
from typing import get_args


def test_snapshot_exposes_complete_permission_master_settings() -> None:
    snapshot = control_plane_service.get_config_snapshot()
    settings = {setting.path: setting for setting in snapshot.settings}

    expected = {
        "permission.mode",
        "permission.preset",
        "permission.rules",
        "permission.profiles",
        "permission.workspace_only",
        "permission.atlas_maintenance_enabled",
        "permission.maintenance_roots",
        "permission.approval_ttl_seconds",
        "permission.decision_timeout_seconds",
        "permission.heartbeat_interval_seconds",
        "permission.fail_closed_on_disconnect",
    }
    assert expected <= settings.keys()
    assert all(settings[path].restart_required is False for path in expected)
    assert "permission.hardline_version" not in settings


def test_revisioned_patch_accepts_narrower_surface_profile(tmp_path: Path) -> None:
    path = tmp_path / "config.yaml"
    updated = config_service.patch_config(
        expected_revision=0,
        changes={
            "permission.preset": "full_autonomy",
            "permission.profiles": [
                {
                    "id": "webui-manual",
                    "preset": "manual",
                    "surfaces": ["webui"],
                    "workspace_only": True,
                }
            ],
        },
        path=path,
    )

    assert updated.revision == 1
    assert updated.permission.profiles[0].id == "webui-manual"
    assert updated.permission.profiles[0].workspace_only is True


def test_revisioned_patch_rejects_profile_widening_with_typed_conflict(
    tmp_path: Path,
) -> None:
    path = tmp_path / "config.yaml"

    with pytest.raises(ControlPlaneError) as caught:
        config_service.patch_config(
            expected_revision=0,
            changes={
                "permission.profiles": [
                    {
                        "id": "webui-autonomous",
                        "preset": "full_autonomy",
                        "surfaces": ["webui"],
                    }
                ]
            },
            path=path,
        )

    assert caught.value.code == "permission_profile_widening"
    assert caught.value.field == "permission.profiles"
    assert not path.exists()


def test_rejected_widening_is_audited_without_rule_payload(
    tmp_path: Path,
    db,
    lock,
) -> None:
    path = tmp_path / "config.yaml"

    with pytest.raises(ControlPlaneError):
        control_plane_service.patch(
            db,
            lock,
            expected_revision=0,
            changes={
                "permission.profiles": [
                    {
                        "id": "webui-autonomous",
                        "preset": "full_autonomy",
                        "surfaces": ["webui"],
                        "rules": [
                            {
                                "id": "must-not-leak",
                                "effect": "allow",
                                "selector": {"command_patterns": ["secret-command *"]},
                            }
                        ],
                    }
                ]
            },
            source_surface="webui",
            source_session_id="surface-policy-test",
            path=path,
        )

    row = db.execute(
        "SELECT session_id, data FROM audit_events "
        "WHERE event_type='failure' ORDER BY rowid DESC LIMIT 1"
    ).fetchone()
    assert row is not None
    assert row[0] == "surface-policy-test"
    payload = json.loads(row[1])
    assert payload["reason"] == "permission_profile_widening"
    assert payload["changed_paths"] == ["permission.profiles"]
    assert "secret-command" not in row[1]
    assert "must-not-leak" not in row[1]


def test_cross_language_fixtures_are_schema_valid_and_complete() -> None:
    fixture_dir = Path(__file__).parent / "fixtures"
    event_fixture = json.loads(
        (fixture_dir / "surface_event_parity.json").read_text(encoding="utf-8")
    )
    events = tuple(
        SurfaceEvent.model_validate(item) for item in event_fixture["events"]
    )

    assert [event.seq for event in events] == list(range(len(events)))
    assert {event.kind for event in events} == set(get_args(EventKind))
    assert (
        json.loads(events[-1].payload_json)["status"]
        == event_fixture["terminal_outcome"]
    )

    matrix = json.loads(
        (fixture_dir / "permission_policy_matrix.json").read_text(encoding="utf-8")
    )
    ids = set()
    for case in matrix["cases"]:
        ids.add(case["id"])
        PermissionConfig.model_validate(case["config"])
        assert case["expected"]["decision"] in {"allow", "ask", "deny"}
    assert len(ids) == len(matrix["cases"])
