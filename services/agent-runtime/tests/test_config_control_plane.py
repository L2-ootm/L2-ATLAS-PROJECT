"""Revisioned, fail-closed configuration transaction tests."""
from __future__ import annotations

import json
from pathlib import Path

import pytest
import yaml

from atlas_runtime import config_service
from atlas_runtime.config_service import AtlasConfig, ControlPlaneError


def test_missing_and_unversioned_config_migrate_in_memory_without_write(
    tmp_path: Path,
) -> None:
    missing = tmp_path / "missing.yaml"
    assert config_service.load_config(missing) == AtlasConfig()
    assert not missing.exists()

    path = tmp_path / "config.yaml"
    original = "provider:\n  model: custom/model\n"
    path.write_text(original, encoding="utf-8")
    loaded = config_service.load_config(path)

    assert loaded.schema_version == 1
    assert loaded.revision == 0
    assert loaded.provider.model == "custom/model"
    assert path.read_text(encoding="utf-8") == original


def test_every_config_read_uses_the_shared_lock(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    path = tmp_path / "config.yaml"
    entered: list[Path] = []
    real_lock = config_service.file_lock

    def recording_lock(lock_path: Path, timeout_seconds: float = 15.0):
        entered.append(lock_path)
        return real_lock(lock_path, timeout_seconds)

    monkeypatch.setattr(config_service, "file_lock", recording_lock)
    config_service.load_config(path)

    assert entered == [config_service.config_lock_path(path)]


def test_malformed_yaml_is_preserved_and_fails_closed(tmp_path: Path) -> None:
    path = tmp_path / "config.yaml"
    malformed = "provider: [not valid"
    path.write_text(malformed, encoding="utf-8")

    with pytest.raises(ControlPlaneError) as caught:
        config_service.load_config(path)

    assert caught.value.code == "config_corrupt"
    assert path.read_text(encoding="utf-8") == malformed
    assert path.with_name("config.yaml.corrupt").read_text(encoding="utf-8") == malformed


def test_future_schema_version_fails_with_remediation(tmp_path: Path) -> None:
    path = tmp_path / "config.yaml"
    path.write_text("schema_version: 99\nrevision: 4\n", encoding="utf-8")

    with pytest.raises(ControlPlaneError) as caught:
        config_service.load_config(path)

    assert caught.value.code == "config_schema_unsupported"
    assert "upgrade" in caught.value.remediation.lower()


def test_patch_increments_revision_once_and_preserves_other_sections(
    tmp_path: Path,
) -> None:
    path = tmp_path / "config.yaml"

    patched = config_service.patch_config(
        expected_revision=0,
        changes={
            "provider.model": "custom/model",
            "permission.mode": "deny",
        },
        path=path,
    )

    assert patched.revision == 1
    assert patched.provider.model == "custom/model"
    assert patched.permission.mode == "deny"
    assert patched.context.token_budget == 8000
    assert patched.modules["graph"] is True
    assert yaml.safe_load(path.read_text(encoding="utf-8"))["revision"] == 1


def test_stale_patch_conflicts_without_changing_file_bytes(tmp_path: Path) -> None:
    path = tmp_path / "config.yaml"
    winner = config_service.patch_config(
        expected_revision=0,
        changes={"runtime.iteration_budget": 42},
        path=path,
    )
    before = path.read_bytes()

    with pytest.raises(ControlPlaneError) as caught:
        config_service.patch_config(
            expected_revision=0,
            changes={"runtime.iteration_budget": 7},
            path=path,
        )

    assert winner.revision == 1
    assert caught.value.code == "config_revision_conflict"
    assert caught.value.current_revision == 1
    assert path.read_bytes() == before


@pytest.mark.parametrize(
    ("changes", "field"),
    [
        ({"provider.nope": "x"}, "provider.nope"),
        ({"runtime.iteration_budget": 0}, "runtime.iteration_budget"),
        ({"provider.api_key": "sk-secret"}, "provider.api_key"),
    ],
)
def test_patch_rejects_unknown_or_invalid_values_with_typed_field(
    tmp_path: Path,
    changes: dict[str, object],
    field: str,
) -> None:
    with pytest.raises(ControlPlaneError) as caught:
        config_service.patch_config(
            expected_revision=0,
            changes=changes,
            path=tmp_path / "config.yaml",
        )

    assert caught.value.code == "config_invalid"
    assert caught.value.field == field
    assert not (tmp_path / "config.yaml").exists()


def test_snapshot_preserves_top_level_compatibility_and_setting_metadata(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from atlas_runtime import control_plane_service

    monkeypatch.setenv("SNAPSHOT_PROVIDER_KEY", "resolved-secret-never-return")
    config = AtlasConfig.model_validate(
        {
            "provider": {
                "api_key": "env:SNAPSHOT_PROVIDER_KEY",
                "model": "configured/model",
            }
        }
    )

    snapshot = control_plane_service.get_config_snapshot(config)
    settings = {setting.path: setting for setting in snapshot.settings}

    assert snapshot.provider.model == "configured/model"
    assert snapshot.runtime.default_agent == "native"
    assert snapshot.gateway.rust_port == 8484
    assert snapshot.cockpit.port == 3000
    assert snapshot.context.token_budget == 8000
    assert snapshot.permission.mode == "ask"
    assert snapshot.modules["wiki"] is True
    assert snapshot.mock_mode is False
    assert settings["provider.api_key"].configured_json == '"env:SNAPSHOT_PROVIDER_KEY"'
    assert settings["provider.api_key"].effective_json == "true"
    assert settings["provider.api_key"].source == "env"
    assert settings["gateway.rust_port"].restart_required is True
    assert settings["cockpit.port"].restart_required is True
    assert settings["context.token_budget"].restart_required is False
    assert "resolved-secret-never-return" not in json.dumps(snapshot.model_dump())


def test_snapshot_reports_focus_model_override_as_effective_source() -> None:
    from atlas_runtime import control_plane_service

    snapshot = control_plane_service.get_config_snapshot(
        AtlasConfig(),
        focus_framework="focus/override-model",
    )
    model = next(
        setting
        for setting in snapshot.settings
        if setting.path == "provider.model"
    )

    assert model.configured_json == '"anthropic/claude-sonnet-4"'
    assert model.effective_json == '"focus/override-model"'
    assert model.source == "focus"
