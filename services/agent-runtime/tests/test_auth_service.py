"""ATLAS-owned auth store and read-only external credential tests."""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from atlas_runtime import auth_service, config_service


def test_auth_store_roundtrip_keeps_public_status_masked(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("ATLAS_HOME", str(tmp_path))
    secret = "sk-atlas-secret-1234"

    status = auth_service.set_api_key("openrouter", secret)

    stored = json.loads((tmp_path / "auth.json").read_text(encoding="utf-8"))
    assert stored["version"] == 1
    assert stored["providers"]["openrouter"]["api_key"] == secret
    assert stored["providers"]["openrouter"]["redacted_hint"] == "…1234"
    assert status.redacted_hint == "…1234"
    assert secret not in json.dumps(status.model_dump())
    assert auth_service.resolve_secret("openrouter") == secret
    assert secret not in json.dumps(
        [item.model_dump() for item in auth_service.list_auth_status()]
    )


def test_malformed_auth_store_is_preserved_and_fails_closed(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("ATLAS_HOME", str(tmp_path))
    path = tmp_path / "auth.json"
    path.write_text("{bad json", encoding="utf-8")

    with pytest.raises(auth_service.AuthServiceError) as caught:
        auth_service.list_auth_status()

    assert caught.value.code == "auth_corrupt"
    assert path.with_name("auth.json.corrupt").read_bytes() == path.read_bytes()


def test_remove_provider_is_idempotent_and_never_returns_secret(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("ATLAS_HOME", str(tmp_path))
    secret = "secret-never-return-this"
    auth_service.set_api_key("example", secret)

    first = auth_service.remove_provider("example")
    second = auth_service.remove_provider("example")

    assert first is True
    assert second is False
    assert secret not in repr((first, second))
    assert auth_service.resolve_secret("example") is None


def test_env_reference_status_reports_presence_without_copying_value(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("ATLAS_HOME", str(tmp_path))
    monkeypatch.setenv("ATLAS_PROVIDER_KEY", "secret-from-env")
    config = config_service.AtlasConfig.model_validate(
        {"provider": {"name": "openrouter", "api_key": "env:ATLAS_PROVIDER_KEY"}}
    )

    statuses = auth_service.list_auth_status(config=config, include_external=False)

    assert len(statuses) == 1
    assert statuses[0].provider == "openrouter"
    assert statuses[0].status == "auth_present"
    assert statuses[0].source == "env"
    assert statuses[0].redacted_hint == "env:ATLAS_PROVIDER_KEY"
    assert not (tmp_path / "auth.json").exists()
    assert "secret-from-env" not in json.dumps(statuses[0].model_dump())


def test_doctor_reports_missing_auth_with_actionable_remediation(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("ATLAS_HOME", str(tmp_path))

    report = auth_service.doctor(provider="openrouter")

    assert report.status == "missing_auth"
    assert "atlas auth add openrouter" in (report.remediation or "")
