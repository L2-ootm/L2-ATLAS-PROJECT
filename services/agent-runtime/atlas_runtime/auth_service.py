"""ATLAS-owned auth store and secret-safe status projection."""
from __future__ import annotations

import datetime
import json
import os
import pathlib
import re
import shutil
from collections.abc import Mapping

from atlas_core.schemas.control_plane import AuthStatus
from atlas_core.schemas.core import SECRET_PATTERNS

from atlas_runtime import config_service
from atlas_runtime.secure_store import (
    SecureStoreError,
    durable_replace_text,
    file_lock,
    preserve_corrupt,
)

AUTH_STORE_VERSION = 1
_PROVIDER_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]*$")


class AuthServiceError(ValueError):
    """Expected auth boundary failure with stable remediation."""

    def __init__(self, code: str, message: str, remediation: str) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.remediation = remediation


def auth_store_path() -> pathlib.Path:
    return config_service.atlas_home() / "auth.json"


def auth_lock_path(path: pathlib.Path | None = None) -> pathlib.Path:
    store_path = pathlib.Path(path or auth_store_path())
    return store_path.with_name("auth.lock")


def _now() -> str:
    return datetime.datetime.now(datetime.timezone.utc).isoformat()


def _empty_store() -> dict[str, object]:
    return {"version": AUTH_STORE_VERSION, "providers": {}, "updated_at": _now()}


def _redact(text: str) -> str:
    for pattern in SECRET_PATTERNS:
        text = pattern.sub("[REDACTED]", text)
    return text


def _validate_provider(provider: str) -> str:
    provider = provider.strip()
    if not _PROVIDER_ID.fullmatch(provider):
        raise AuthServiceError(
            "auth_provider_invalid",
            "provider id must use letters, numbers, dots, dashes, or underscores",
            "choose the provider id shown by `atlas models list`",
        )
    return provider


def _translate_store_error(exc: SecureStoreError) -> AuthServiceError:
    return AuthServiceError(exc.code, exc.message, exc.remediation)


def _load_store_unlocked(path: pathlib.Path) -> dict[str, object]:
    if not path.is_file():
        return _empty_store()
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        try:
            preserve_corrupt(path)
        except SecureStoreError as preserve_exc:
            raise _translate_store_error(preserve_exc) from preserve_exc
        raise AuthServiceError(
            "auth_corrupt",
            f"{path.name} is malformed and was preserved as {path.name}.corrupt",
            "remove or repair the malformed auth store, then add credentials again",
        ) from exc
    if (
        not isinstance(raw, dict)
        or raw.get("version") != AUTH_STORE_VERSION
        or not isinstance(raw.get("providers"), dict)
    ):
        raise AuthServiceError(
            "auth_schema_unsupported",
            "auth store schema is not supported",
            "upgrade ATLAS or recreate the auth store with `atlas auth add`",
        )
    return raw


def _load_store(path: pathlib.Path) -> dict[str, object]:
    try:
        with file_lock(auth_lock_path(path)):
            return _load_store_unlocked(path)
    except SecureStoreError as exc:
        raise _translate_store_error(exc) from exc


def _record_status(provider: str, record: Mapping[str, object]) -> AuthStatus:
    return AuthStatus(
        provider=provider,
        auth_type=str(record.get("auth_type", "api_key")),
        status="auth_present",
        source="atlas_auth_store",
        health="available",
        updated_at=str(record.get("updated_at") or "") or None,
        redacted_hint=str(record.get("redacted_hint", "")),
    )


def _env_status(config: config_service.AtlasConfig) -> AuthStatus | None:
    reference = config.provider.api_key
    if not reference.startswith("env:"):
        return None
    variable = reference[len("env:") :]
    present = bool(os.environ.get(variable))
    return AuthStatus(
        provider=config.provider.name,
        auth_type="api_key",
        status="auth_present" if present else "missing_auth",
        source="env",
        health="available" if present else "needs_auth",
        redacted_hint=reference,
        remediation=(
            None
            if present
            else f"set {variable} in the environment before starting ATLAS"
        ),
    )


def set_api_key(
    provider: str,
    secret: str,
    *,
    base_url: str | None = None,
    path: pathlib.Path | None = None,
) -> AuthStatus:
    """Store one provider API key and return only masked metadata."""
    provider = _validate_provider(provider)
    if not secret:
        raise AuthServiceError(
            "auth_secret_missing",
            "API key must not be empty",
            "retry and enter the provider API key at the hidden prompt",
        )
    store_path = pathlib.Path(path or auth_store_path())
    try:
        with file_lock(auth_lock_path(store_path)):
            store = _load_store_unlocked(store_path)
            providers = dict(store["providers"])
            previous = providers.get(provider)
            created_at = (
                previous.get("created_at")
                if isinstance(previous, dict)
                else _now()
            )
            timestamp = _now()
            record = {
                "auth_type": "api_key",
                "api_key": secret,
                "base_url": base_url,
                "created_at": created_at,
                "updated_at": timestamp,
                "redacted_hint": f"…{secret[-4:]}" if len(secret) >= 4 else "…",
            }
            providers[provider] = record
            store = {
                "version": AUTH_STORE_VERSION,
                "providers": providers,
                "updated_at": timestamp,
            }
            durable_replace_text(
                store_path,
                json.dumps(store, indent=2, sort_keys=True) + "\n",
            )
    except SecureStoreError as exc:
        raise _translate_store_error(exc) from exc
    return _record_status(provider, record)


def remove_provider(
    provider: str,
    *,
    path: pathlib.Path | None = None,
) -> bool:
    """Remove a provider record; return whether one existed."""
    provider = _validate_provider(provider)
    store_path = pathlib.Path(path or auth_store_path())
    try:
        with file_lock(auth_lock_path(store_path)):
            store = _load_store_unlocked(store_path)
            providers = dict(store["providers"])
            if provider not in providers:
                return False
            del providers[provider]
            updated = {
                "version": AUTH_STORE_VERSION,
                "providers": providers,
                "updated_at": _now(),
            }
            durable_replace_text(
                store_path,
                json.dumps(updated, indent=2, sort_keys=True) + "\n",
            )
    except SecureStoreError as exc:
        raise _translate_store_error(exc) from exc
    return True


def resolve_secret(
    provider: str,
    *,
    path: pathlib.Path | None = None,
) -> str | None:
    """Resolve a private secret for runtime use; never call from status APIs."""
    provider = _validate_provider(provider)
    store = _load_store(pathlib.Path(path or auth_store_path()))
    record = store["providers"].get(provider)
    if not isinstance(record, dict):
        return None
    secret = record.get("api_key")
    return secret if isinstance(secret, str) and secret else None


def list_auth_status(
    *,
    config: config_service.AtlasConfig | None = None,
    include_external: bool = True,
    path: pathlib.Path | None = None,
) -> tuple[AuthStatus, ...]:
    """Return secret-free status for owned, env, and external auth sources."""
    store = _load_store(pathlib.Path(path or auth_store_path()))
    providers = store["providers"]
    statuses = [
        _record_status(provider, record)
        for provider, record in sorted(providers.items())
        if isinstance(provider, str) and isinstance(record, dict)
    ]
    config = config or config_service.load_config()
    env_status = _env_status(config)
    if env_status is not None and all(
        status.provider != env_status.provider for status in statuses
    ):
        statuses.append(env_status)
    if include_external:
        statuses.extend(detect_external_auth())
    return tuple(statuses)


def doctor(
    *,
    provider: str,
    config: config_service.AtlasConfig | None = None,
) -> AuthStatus:
    provider = _validate_provider(provider)
    for status in list_auth_status(config=config, include_external=False):
        if status.provider == provider:
            return status
    return AuthStatus(
        provider=provider,
        auth_type="api_key",
        status="missing_auth",
        source="atlas_auth_store",
        health="needs_auth",
        remediation=f"run `atlas auth add {provider}` and enter the key securely",
    )


def _home_directory() -> pathlib.Path:
    return pathlib.Path.home()


def _external_descriptors() -> tuple[tuple[str, str, pathlib.Path], ...]:
    home = _home_directory()
    codex_home = pathlib.Path(
        os.environ.get("CODEX_HOME", "").strip() or home / ".codex"
    )
    claude_home = pathlib.Path(
        os.environ.get("CLAUDE_CONFIG_DIR", "").strip() or home / ".claude"
    )
    return (
        ("codex", "codex", codex_home / "auth.json"),
        ("claude", "claude", claude_home / ".credentials.json"),
    )


def detect_external_auth() -> tuple[AuthStatus, ...]:
    """Detect external auth by binary/file presence without opening payloads."""
    statuses: list[AuthStatus] = []
    for provider, command, credential_path in _external_descriptors():
        installed = shutil.which(command) is not None
        try:
            credential_path.stat()
            credential_present = True
        except FileNotFoundError:
            credential_present = False
        except OSError:
            statuses.append(
                AuthStatus(
                    provider=provider,
                    auth_type="external_login",
                    status="unknown_error",
                    source="external_read_only",
                    health="unknown",
                    remediation=(
                        f"check access to the {provider} credential file and retry"
                    ),
                )
            )
            continue

        if credential_present:
            status = "auth_present"
            health = "available"
            remediation = None
        elif installed:
            status = "installed_no_auth"
            health = "needs_auth"
            remediation = f"authenticate with the {provider} CLI outside ATLAS"
        else:
            status = "not_installed"
            health = "not_installed"
            remediation = f"install the {provider} CLI if that provider is required"
        statuses.append(
            AuthStatus(
                provider=provider,
                auth_type="external_login",
                status=status,
                source="external_read_only",
                health=health,
                remediation=remediation,
            )
        )
    return tuple(statuses)


__all__ = [
    "AuthServiceError",
    "auth_lock_path",
    "auth_store_path",
    "detect_external_auth",
    "doctor",
    "list_auth_status",
    "remove_provider",
    "resolve_secret",
    "set_api_key",
]
