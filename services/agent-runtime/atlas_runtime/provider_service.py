"""Provider-mesh status composition for the operator CLI/surfaces.

Read-only helpers that compose the existing control-plane pieces (config,
auth store, Codex import status, claude SDK presence) into two operator views:

  - active_status(): what the active provider resolves to right now, and whether
    a real run would call a provider or fall back to deterministic MOCK MODE.
  - modes_status(): the multi-mode "which ways can I wire?" board across all four
    auth modes (api_key / oauth_import / claude_code / freellmapi).

No secrets are ever returned — only presence, mode, effective values, and
remediation. The CLI layer stays a thin wrapper over these.
"""
from __future__ import annotations

import importlib.util
import shutil
from typing import Any, Optional

from atlas_runtime import auth_service, codex_auth, config_service

# Operator-facing copy for each auth mode (kept here so CLI/TUI/cockpit agree).
_MODE_LABELS = {
    "api_key": "Direct API key (OpenRouter/OpenAI/Anthropic/compatible)",
    "oauth_import": "Codex / ChatGPT OAuth import",
    "claude_code": "Claude Code (local subscription session)",
    "freellmapi": "FreeLLMAPI (free models - privacy cost)",
}


def active_status(config: Optional[config_service.AtlasConfig] = None) -> dict[str, Any]:
    """Effective provider resolution for the active config (secret-free)."""
    config = config or config_service.load_config()
    resolved = config_service.resolve_provider(config)
    api_key_present = bool(resolved.get("api_key"))
    auth_mode = resolved.get("auth_mode", "api_key")
    # A run hits a real provider when credentials resolve OR the mode is
    # credential-less (claude_code uses the local session; freellmapi may use a
    # keyless base_url). oauth_import resolves its credential at run time from
    # the foundation's owned store, so the api_key projection is always empty
    # for it — the owned store, not resolve_provider, is its truth.
    codex_ready = auth_mode == "oauth_import" and _codex_runtime_ready()
    real = api_key_present or codex_ready or auth_mode in ("claude_code", "freellmapi")
    provider = resolved.get("provider", "")
    model = resolved.get("model", "")
    if codex_ready:
        # Report what a Codex run will actually use — the foundation resolves
        # provider "openai-codex", and the backend rejects non-Codex slugs.
        provider = "openai-codex"
        model = codex_auth.effective_codex_model(model)
    return {
        "provider": provider,
        "model": model,
        "auth_mode": auth_mode,
        "auth_mode_label": _MODE_LABELS.get(auth_mode, auth_mode),
        "base_url": resolved.get("base_url", "") or None,
        "credentials_present": api_key_present or codex_ready,
        "mock_mode": not real,
        "remediation": None if real else _active_remediation(auth_mode),
        "reasoning_effort": resolved.get("reasoning_effort", "") or None,
        # Surfaced so every UI can show the cost of the mode that is wired
        # (the run boundary additionally emits the audited D-002 warning).
        "privacy_warning": (
            "free endpoints may log prompts — never send secrets"
            if auth_mode == "freellmapi" else None
        ),
    }


def _codex_runtime_ready() -> bool:
    """True when the foundation's owned Codex store can execute a run. A
    present refresh_token suffices — the foundation refreshes at run time."""
    owned = codex_auth.owned_status()
    return bool(owned.get("present") and owned.get("has_refresh_token"))


def _active_remediation(auth_mode: str) -> str:
    if auth_mode == "oauth_import":
        return "run `atlas auth import-codex` (and `codex` to refresh if invalidated)"
    if auth_mode == "freellmapi":
        return "set provider.base_url to a FreeLLMAPI endpoint"
    return "wire a key with `atlas auth add <provider>` or set provider.api_key=env:VAR"


def _api_key_mode() -> dict[str, Any]:
    resolved = config_service.resolve_provider()
    available = bool(resolved.get("api_key"))
    stored = [
        s.provider
        for s in auth_service.list_auth_status(include_external=False)
        if s.source == "atlas_auth_store"
    ]
    if not available and stored:
        available = True
    return {
        "available": available,
        "detail": (
            f"stored: {', '.join(stored)}" if stored
            else ("env reference set" if available else "no key configured")
        ),
        "remediation": None if available
        else "atlas auth add <provider>  (or set provider.api_key=env:VAR)",
    }


def _codex_mode() -> dict[str, Any]:
    imported = _codex_runtime_ready()
    st = codex_auth.cli_status()
    present = bool(st.get("present") and st.get("readable"))
    fresh = present and not st.get("access_token_expired", True)
    if imported:
        detail = "imported - foundation store owns refresh"
        if present and st.get("email"):
            detail += f" (codex login: {st.get('email')})"
        return {"available": True, "detail": detail, "remediation": None}
    if fresh:
        return {
            "available": True,
            "detail": f"codex login: {st.get('email')} (import pending)",
            "remediation": "run `atlas auth import-codex` to activate",
        }
    return {
        "available": False,
        "detail": (
            f"codex login: {st.get('email')} (token stale - refresh needed)"
            if present else "no ~/.codex login found"
        ),
        "remediation": "run `codex` to log in/refresh, then `atlas auth import-codex`",
    }


def claude_code_status() -> dict[str, Any]:
    """Claude-Code mode readiness: the SDK (atlas-runtime[claude]) + the local
    `claude` CLI must both be present in the *running* runtime. Self-contained
    (no config/DB), so health aggregators like `atlas doctor` can reuse it."""
    sdk = importlib.util.find_spec("claude_agent_sdk") is not None
    cli = shutil.which("claude") is not None
    available = sdk and cli
    missing = []
    if not sdk:
        missing.append("atlas-runtime[claude] SDK")
    if not cli:
        missing.append("claude CLI")
    return {
        "available": available,
        "detail": "SDK + claude CLI present" if available
        else f"missing: {', '.join(missing)}",
        "remediation": None if available
        else "install atlas-runtime[claude] into the runtime venv and the claude CLI",
    }


def _claude_code_mode() -> dict[str, Any]:
    return claude_code_status()


def _freellmapi_mode(config: config_service.AtlasConfig) -> dict[str, Any]:
    base_url = config.provider.base_url
    available = bool(base_url) and config.provider.auth_mode == "freellmapi"
    return {
        "available": available,
        "detail": f"base_url: {base_url}" if base_url else "no base_url configured",
        "remediation": None if available
        else "set provider.auth_mode=freellmapi and provider.base_url=<endpoint>",
    }


def modes_status(config: Optional[config_service.AtlasConfig] = None) -> list[dict[str, Any]]:
    """Per-mode availability board across the four wiring modes."""
    config = config or config_service.load_config()
    active = config.provider.auth_mode
    builders = {
        "api_key": _api_key_mode,
        "oauth_import": _codex_mode,
        "claude_code": _claude_code_mode,
        "freellmapi": lambda: _freellmapi_mode(config),
    }
    out: list[dict[str, Any]] = []
    for mode, build in builders.items():
        info = build()
        out.append({
            "mode": mode,
            "label": _MODE_LABELS[mode],
            "active": mode == active,
            **info,
        })
    return out


__all__ = ["active_status", "modes_status", "claude_code_status"]
