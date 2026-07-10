"""ATLAS-owned auth store and read-only external credential tests."""
from __future__ import annotations

import json
import hashlib
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


def test_external_detection_reports_install_and_auth_presence_without_reads(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    home = tmp_path / "external-home"
    codex_auth = home / ".codex" / "auth.json"
    codex_auth.parent.mkdir(parents=True)
    codex_auth.write_bytes(b'{"tokens":"never parse me"}')
    opened: list[Path] = []

    monkeypatch.setattr(auth_service, "_home_directory", lambda: home)
    monkeypatch.setattr(
        auth_service.shutil,
        "which",
        lambda command: f"C:/bin/{command}.exe" if command == "claude" else None,
    )
    original_open = Path.open

    def reject_external_open(path: Path, *args, **kwargs):
        if home in path.parents:
            opened.append(path)
            raise AssertionError("external credential payload was opened")
        return original_open(path, *args, **kwargs)

    monkeypatch.setattr(Path, "open", reject_external_open)
    statuses = {status.provider: status for status in auth_service.detect_external_auth()}

    assert statuses["codex"].status == "auth_present"
    assert statuses["claude"].status == "installed_no_auth"
    assert all(status.source == "external_read_only" for status in statuses.values())
    assert opened == []


def test_external_detection_preserves_bytes_hash_size_and_mtime(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    home = tmp_path / "external-home"
    path = home / ".claude" / ".credentials.json"
    path.parent.mkdir(parents=True)
    path.write_bytes(b"opaque external credential bytes")
    before = (
        path.read_bytes(),
        hashlib.sha256(path.read_bytes()).hexdigest(),
        path.stat().st_size,
        path.stat().st_mtime_ns,
    )
    monkeypatch.setattr(auth_service, "_home_directory", lambda: home)
    monkeypatch.setattr(auth_service.shutil, "which", lambda command: None)

    auth_service.detect_external_auth()

    after = (
        path.read_bytes(),
        hashlib.sha256(path.read_bytes()).hexdigest(),
        path.stat().st_size,
        path.stat().st_mtime_ns,
    )
    assert after == before


def test_external_detection_reports_unknown_error_safely(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    home = tmp_path / "external-home"
    monkeypatch.setattr(auth_service, "_home_directory", lambda: home)
    monkeypatch.setattr(auth_service.shutil, "which", lambda command: None)
    real_stat = Path.stat

    def denied(path: Path, *args, **kwargs):
        if ".codex" in path.parts:
            raise PermissionError("sensitive operating-system detail")
        return real_stat(path, *args, **kwargs)

    monkeypatch.setattr(Path, "stat", denied)
    statuses = {status.provider: status for status in auth_service.detect_external_auth()}

    assert statuses["codex"].status == "unknown_error"
    rendered = json.dumps(statuses["codex"].model_dump())
    assert "sensitive operating-system detail" not in rendered
    assert "credential file" in (statuses["codex"].remediation or "")


def test_doctor_oauth_import_reports_live_via_owned_store(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("ATLAS_HOME", str(tmp_path))
    from atlas_runtime import codex_auth

    monkeypatch.setattr(codex_auth, "runtime_ready", lambda: True)
    config = config_service.AtlasConfig.model_validate(
        {"provider": {"name": "openai-codex", "auth_mode": "oauth_import"}}
    )

    status = auth_service.doctor(provider="openai-codex", config=config)

    assert status.status == "auth_present"
    assert status.auth_type == "oauth_import"
    assert status.health == "available"
    assert status.source == "foundation_owned_store"


def test_doctor_oauth_import_not_imported_gives_import_remediation(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("ATLAS_HOME", str(tmp_path))
    from atlas_runtime import codex_auth

    monkeypatch.setattr(codex_auth, "runtime_ready", lambda: False)
    config = config_service.AtlasConfig.model_validate(
        {"provider": {"name": "openai-codex", "auth_mode": "oauth_import"}}
    )

    status = auth_service.doctor(provider="openai-codex", config=config)

    assert status.status == "missing_auth"
    assert status.auth_type == "oauth_import"
    assert "import-codex" in (status.remediation or "")
