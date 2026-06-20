"""ATLAS config service — owns ``~/.atlas/config.yaml`` (ATLAS-level settings).

Distinct from the foundation messaging config (``~/.hermes/config.yaml``, which the
Python messaging gateway reads for channel adapters). This file holds ATLAS's own
provider / runtime / gateway / cockpit / module settings — the substrate the setup
wizard writes and the Rust gateway reads (masked) for the cockpit System page.

Trust posture: secret values are stored as ``env:VAR_NAME`` references, never inline
plaintext. The schema rejects raw-looking secrets so a key cannot leak into the file.
Path resolution lives behind ``default_config_path()`` (one function), consistent with
the 10.0 auth-store decision for future profiles.
"""
from __future__ import annotations

import os
import pathlib
import tempfile

import yaml
from pydantic import BaseModel, Field, field_validator

ATLAS_HOME_ENV = "ATLAS_HOME"


def atlas_home() -> pathlib.Path:
    """ATLAS-owned config/state dir (``ATLAS_HOME`` aware, default ``~/.atlas``)."""
    env = os.environ.get(ATLAS_HOME_ENV, "").strip()
    return pathlib.Path(env) if env else pathlib.Path.home() / ".atlas"


def default_config_path() -> pathlib.Path:
    return atlas_home() / "config.yaml"


def _is_secret_ref(value: str) -> bool:
    """A safe credential reference: empty or an ``env:VAR`` indirection."""
    return value == "" or value.startswith("env:")


class ProviderConfig(BaseModel):
    name: str = "openrouter"
    model: str = "anthropic/claude-sonnet-4"
    api_key: str = ""  # MUST be "" or "env:VAR_NAME" — never an inline secret
    base_url: str | None = None

    @field_validator("api_key")
    @classmethod
    def _no_inline_secret(cls, v: str) -> str:
        if not _is_secret_ref(v):
            raise ValueError(
                "provider.api_key must be empty or an 'env:VAR_NAME' reference, "
                "never an inline secret value"
            )
        return v


class RuntimeConfig(BaseModel):
    default_agent: str = "native"  # native | claude_code
    iteration_budget: int = 90
    compression: str = "auto"


class GatewayConfig(BaseModel):
    rust_port: int = 8484
    messaging_enabled: bool = False
    messaging_port: int = 8585


class CockpitConfig(BaseModel):
    port: int = 3000
    branding: str = "atlas"


class AtlasConfig(BaseModel):
    provider: ProviderConfig = Field(default_factory=ProviderConfig)
    runtime: RuntimeConfig = Field(default_factory=RuntimeConfig)
    gateway: GatewayConfig = Field(default_factory=GatewayConfig)
    cockpit: CockpitConfig = Field(default_factory=CockpitConfig)
    modules: dict[str, bool] = Field(default_factory=lambda: {"wiki": True, "graph": True, "cashflow": False})


def load_config(path: pathlib.Path | None = None) -> AtlasConfig:
    """Load config from ``path`` (default ``~/.atlas/config.yaml``). Missing/empty
    file yields defaults — always safe to call on a fresh install."""
    path = path or default_config_path()
    if not path.is_file():
        return AtlasConfig()
    data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    return AtlasConfig.model_validate(data)


def save_config(cfg: AtlasConfig, path: pathlib.Path | None = None) -> pathlib.Path:
    """Atomically write config to ``path`` (default ``~/.atlas/config.yaml``)."""
    path = path or default_config_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    body = yaml.safe_dump(cfg.model_dump(), sort_keys=False, default_flow_style=False)
    # Atomic write: temp in the same dir, then os.replace (atomic on Windows + POSIX).
    fd, tmp = tempfile.mkstemp(dir=str(path.parent), suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            fh.write(body)
        os.replace(tmp, str(path))
    finally:
        if os.path.exists(tmp):
            os.remove(tmp)
    return path


def masked_dict(cfg: AtlasConfig) -> dict:
    """Config as a plain dict safe for the gateway/cockpit. Secrets are already
    ``env:`` refs (no values), so this is a straight dump kept behind one function
    in case future fields need masking."""
    return cfg.model_dump()


def get_value(cfg: AtlasConfig, dotted_key: str):
    """Read a nested value by dotted path, e.g. ``provider.model``."""
    node = cfg.model_dump()
    for part in dotted_key.split("."):
        if not isinstance(node, dict) or part not in node:
            raise KeyError(dotted_key)
        node = node[part]
    return node


def set_value(cfg: AtlasConfig, dotted_key: str, value) -> AtlasConfig:
    """Return a new validated config with ``dotted_key`` set to ``value``.
    Re-validation enforces the no-inline-secret rule and type coercion."""
    data = cfg.model_dump()
    parts = dotted_key.split(".")
    node = data
    for part in parts[:-1]:
        if part not in node or not isinstance(node[part], dict):
            raise KeyError(dotted_key)
        node = node[part]
    leaf = parts[-1]
    if leaf not in node:
        raise KeyError(dotted_key)
    node[leaf] = value
    return AtlasConfig.model_validate(data)
