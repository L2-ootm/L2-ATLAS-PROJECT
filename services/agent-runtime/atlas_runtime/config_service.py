"""Versioned, locked owner of ``~/.atlas/config.yaml``."""

from __future__ import annotations

import os
import pathlib
from collections.abc import Mapping

import yaml
from atlas_core.schemas.control_plane import (
    AtlasConfig,
    CockpitConfig,
    ContextConfig,
    ControlPlaneError,
    GatewayConfig,
    ModulesConfig,
    PermissionConfig,
    ProviderConfig,
    RuntimeConfig,
)
from pydantic import ValidationError

from atlas_runtime.secure_store import (
    SecureStoreError,
    durable_replace_text,
    file_lock,
    preserve_corrupt,
)

ATLAS_HOME_ENV = "ATLAS_HOME"
CONFIG_SCHEMA_VERSION = 1


def atlas_home() -> pathlib.Path:
    """Return the ATLAS-owned config/state directory."""
    env = os.environ.get(ATLAS_HOME_ENV, "").strip()
    return pathlib.Path(env) if env else pathlib.Path.home() / ".atlas"


def default_config_path() -> pathlib.Path:
    return atlas_home() / "config.yaml"


def config_lock_path(path: pathlib.Path | None = None) -> pathlib.Path:
    config_path = pathlib.Path(path or default_config_path())
    return config_path.with_name(f"{config_path.name}.lock")


def _translate_store_error(exc: SecureStoreError) -> ControlPlaneError:
    return ControlPlaneError(exc.code, exc.message, exc.remediation)


def _field_from_validation(exc: ValidationError) -> str | None:
    errors = exc.errors()
    if not errors:
        return None
    return ".".join(str(part) for part in errors[0].get("loc", ())) or None


def _validation_error(exc: ValidationError) -> ControlPlaneError:
    field = _field_from_validation(exc)
    messages = " ".join(str(error.get("msg", "")) for error in exc.errors())
    if "may only narrow" in messages:
        return ControlPlaneError(
            "permission_profile_widening",
            "permission profile would widen the master safety ceiling",
            "make the profile preset and allow rules equal to or stricter than the master policy",
            field=field or "permission.profiles",
        )
    label = f" for {field}" if field else ""
    return ControlPlaneError(
        "config_invalid",
        f"invalid configuration value{label}",
        "correct the named setting and retry",
        field=field,
    )


def _load_unlocked(path: pathlib.Path) -> AtlasConfig:
    if not path.is_file():
        return AtlasConfig()

    try:
        raw = yaml.safe_load(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, yaml.YAMLError) as exc:
        try:
            preserve_corrupt(path)
        except SecureStoreError as preserve_exc:
            raise _translate_store_error(preserve_exc) from preserve_exc
        raise ControlPlaneError(
            "config_corrupt",
            f"{path.name} is malformed and was preserved as {path.name}.corrupt",
            "repair or replace the preserved config, then retry",
        ) from exc

    if raw is None:
        raw = {}
    if not isinstance(raw, dict):
        try:
            preserve_corrupt(path)
        except SecureStoreError as preserve_exc:
            raise _translate_store_error(preserve_exc) from preserve_exc
        raise ControlPlaneError(
            "config_corrupt",
            f"{path.name} must contain a YAML object",
            "repair the preserved config so its top level is a mapping",
        )

    version = raw.get("schema_version", CONFIG_SCHEMA_VERSION)
    if version != CONFIG_SCHEMA_VERSION:
        raise ControlPlaneError(
            "config_schema_unsupported",
            f"config schema version {version!r} is not supported",
            "upgrade ATLAS or export the config with a compatible version",
        )

    migrated = dict(raw)
    migrated.setdefault("schema_version", CONFIG_SCHEMA_VERSION)
    migrated.setdefault("revision", 0)
    try:
        return AtlasConfig.model_validate(migrated)
    except ValidationError as exc:
        raise _validation_error(exc) from exc


def load_config(path: pathlib.Path | None = None) -> AtlasConfig:
    """Load config under the same advisory lock used by writers."""
    config_path = pathlib.Path(path or default_config_path())
    try:
        with file_lock(config_lock_path(config_path)):
            return _load_unlocked(config_path)
    except SecureStoreError as exc:
        raise _translate_store_error(exc) from exc


def _apply_dotted_change(
    data: dict[str, object],
    dotted_key: str,
    value: object,
) -> None:
    parts = dotted_key.split(".")
    if not dotted_key or any(not part for part in parts):
        raise ControlPlaneError(
            "config_invalid",
            "configuration path must be a non-empty dotted key",
            "use a path such as provider.model",
            field=dotted_key or None,
        )
    node: dict[str, object] = data
    for part in parts[:-1]:
        child = node.get(part)
        if not isinstance(child, dict):
            raise ControlPlaneError(
                "config_invalid",
                f"unknown configuration path {dotted_key}",
                "reload the masked config and choose a supported setting",
                field=dotted_key,
            )
        node = child
    leaf = parts[-1]
    if leaf not in node:
        raise ControlPlaneError(
            "config_invalid",
            f"unknown configuration path {dotted_key}",
            "reload the masked config and choose a supported setting",
            field=dotted_key,
        )
    node[leaf] = value


def _validated_with_revision(
    data: dict[str, object],
    revision: int,
    *,
    field_hint: str | None = None,
) -> AtlasConfig:
    data["schema_version"] = CONFIG_SCHEMA_VERSION
    data["revision"] = revision
    try:
        return AtlasConfig.model_validate(data)
    except ValidationError as exc:
        error = _validation_error(exc)
        if field_hint is not None:
            error.field = field_hint
        raise error from exc


def _dump_config(config: AtlasConfig) -> str:
    return yaml.safe_dump(
        config.model_dump(),
        sort_keys=False,
        default_flow_style=False,
    )


def patch_config(
    *,
    expected_revision: int,
    changes: Mapping[str, object],
    path: pathlib.Path | None = None,
) -> AtlasConfig:
    """Apply dotted changes atomically with optimistic revision checking."""
    config_path = pathlib.Path(path or default_config_path())
    try:
        with file_lock(config_lock_path(config_path)):
            current = _load_unlocked(config_path)
            if current.revision != expected_revision:
                raise ControlPlaneError(
                    "config_revision_conflict",
                    (
                        f"config changed from revision {expected_revision} "
                        f"to {current.revision}"
                    ),
                    "reload the masked config and retry your patch",
                    current_revision=current.revision,
                )

            data = current.model_dump()
            last_field: str | None = None
            for dotted_key, value in changes.items():
                last_field = dotted_key
                _apply_dotted_change(data, dotted_key, value)
            updated = _validated_with_revision(
                data,
                current.revision + 1,
                field_hint=last_field,
            )
            durable_replace_text(config_path, _dump_config(updated))
            return updated
    except SecureStoreError as exc:
        raise _translate_store_error(exc) from exc


def replace_config(
    config: AtlasConfig,
    *,
    expected_revision: int | None = None,
    path: pathlib.Path | None = None,
) -> AtlasConfig:
    """Replace config content through the locked revision transaction."""
    config_path = pathlib.Path(path or default_config_path())
    try:
        with file_lock(config_lock_path(config_path)):
            current = _load_unlocked(config_path)
            if expected_revision is not None and current.revision != expected_revision:
                raise ControlPlaneError(
                    "config_revision_conflict",
                    (
                        f"config changed from revision {expected_revision} "
                        f"to {current.revision}"
                    ),
                    "reload the masked config and retry your replacement",
                    current_revision=current.revision,
                )
            data = config.model_dump()
            updated = _validated_with_revision(data, current.revision + 1)
            durable_replace_text(config_path, _dump_config(updated))
            return updated
    except SecureStoreError as exc:
        raise _translate_store_error(exc) from exc


def save_config(
    config: AtlasConfig,
    path: pathlib.Path | None = None,
) -> pathlib.Path:
    """Compatibility adapter for callers not yet migrated to revisioned replace."""
    config_path = pathlib.Path(path or default_config_path())
    replace_config(config, path=config_path)
    return config_path


def resolve_provider(
    config: AtlasConfig | None = None,
    *,
    focus_framework: str | None = None,
) -> dict[str, str]:
    """Resolve effective provider/model and dereference an optional env key."""
    config = config or load_config()
    provider = config.provider
    model = (focus_framework or "").strip() or provider.model
    api_key = ""
    if provider.api_key.startswith("env:"):
        api_key = os.environ.get(provider.api_key[len("env:") :], "")
    return {
        "provider": provider.name,
        "model": model,
        "auth_mode": provider.auth_mode,
        "base_url": provider.base_url or "",
        "api_key": api_key,
    }


def masked_dict(config: AtlasConfig) -> dict[str, object]:
    """Return the backward-compatible secret-safe config projection."""
    data = config.model_dump()
    data["mock_mode"] = not bool(resolve_provider(config).get("api_key"))
    return data


def get_value(config: AtlasConfig, dotted_key: str) -> object:
    node: object = config.model_dump()
    for part in dotted_key.split("."):
        if not isinstance(node, dict) or part not in node:
            raise KeyError(dotted_key)
        node = node[part]
    return node


def set_value(
    config: AtlasConfig,
    dotted_key: str,
    value: object,
) -> AtlasConfig:
    """Return a revalidated immutable config with one changed value."""
    data = config.model_dump()
    try:
        _apply_dotted_change(data, dotted_key, value)
        return _validated_with_revision(
            data,
            config.revision,
            field_hint=dotted_key,
        )
    except ControlPlaneError as exc:
        if exc.code == "config_invalid" and exc.message.startswith("unknown"):
            raise KeyError(dotted_key) from exc
        raise


__all__ = [
    "ATLAS_HOME_ENV",
    "AtlasConfig",
    "CockpitConfig",
    "ContextConfig",
    "ControlPlaneError",
    "GatewayConfig",
    "ModulesConfig",
    "PermissionConfig",
    "ProviderConfig",
    "RuntimeConfig",
    "atlas_home",
    "config_lock_path",
    "default_config_path",
    "get_value",
    "load_config",
    "masked_dict",
    "patch_config",
    "replace_config",
    "resolve_provider",
    "save_config",
    "set_value",
]
