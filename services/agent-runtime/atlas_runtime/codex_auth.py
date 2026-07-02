"""Codex (ChatGPT OAuth) credential adapter — delegates to the foundation.

auth_mode="oauth_import" lets an operator run ATLAS on their existing Codex /
ChatGPT subscription login. Per D-001 the vendored Hermes foundation already
owns the entire Codex OAuth lifecycle and we DO NOT reimplement it:

  - foundation `_import_codex_cli_tokens()` bootstraps ONE-TIME from
    ~/.codex/auth.json (read-only; rejects expired tokens),
  - foundation `_save_codex_tokens()` persists them into Hermes's OWN store
    (~/.hermes/auth.json) — deliberately separate from ~/.codex so a refresh
    here never rotates/invalidates the Codex CLI's live session,
  - foundation `resolve_codex_runtime_credentials()` resolves + refreshes the
    runtime access_token against that owned store.

This module is a thin, lazily-imported boundary onto those functions plus a
secret-free status read of ~/.codex for the settings surface. The spike
(docs/plans/2026-06-28-codex-oauth-spike-findings.md) confirmed the backend
contract; the open refresh-ownership question is resolved by reusing Hermes's
import-and-own model.
"""
from __future__ import annotations

import base64
import json
import logging
import os
import pathlib
import sys
import time
from typing import Any, Optional

logger = logging.getLogger(__name__)

# Foundation loader is injectable so unit tests run without the foundation.
_FOUNDATION_AUTH_FACTORY = None  # set by tests via set_foundation_loader()


def set_foundation_loader(factory) -> None:
    """Test seam: inject a callable returning a foundation-auth-like module."""
    global _FOUNDATION_AUTH_FACTORY
    _FOUNDATION_AUTH_FACTORY = factory


def _find_foundation() -> Optional[pathlib.Path]:
    for parent in pathlib.Path(__file__).resolve().parents:
        candidate = parent / "foundation" / "atlas-hermes"
        if candidate.is_dir():
            return candidate
    return None


def _foundation_auth() -> Any:
    """Lazily import the foundation hermes_cli.auth module (path-injected)."""
    if _FOUNDATION_AUTH_FACTORY is not None:
        return _FOUNDATION_AUTH_FACTORY()
    foundation = _find_foundation()
    if foundation is not None:
        path = str(foundation)
        if path not in sys.path:
            sys.path.insert(0, path)
    from hermes_cli import auth as foundation_auth  # noqa: PLC0415

    return foundation_auth


def codex_home() -> pathlib.Path:
    raw = os.environ.get("CODEX_HOME", "").strip()
    return pathlib.Path(raw) if raw else pathlib.Path.home() / ".codex"


def _jwt_claims(jwt: str) -> dict[str, Any]:
    try:
        payload = jwt.split(".")[1]
        payload += "=" * (-len(payload) % 4)
        return json.loads(base64.urlsafe_b64decode(payload))
    except Exception:  # noqa: BLE001 — best-effort, status only
        return {}


def cli_status() -> dict[str, Any]:
    """Secret-free status of the operator's Codex CLI login (~/.codex/auth.json).

    Never returns token bytes — only presence, mode, email, and expiry. Safe for
    the settings surface and `atlas auth` display.
    """
    path = codex_home() / "auth.json"
    if not path.is_file():
        return {"present": False, "reason": "no_codex_login"}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:  # noqa: BLE001
        return {"present": True, "readable": False, "reason": str(exc)[:120]}
    tokens = payload.get("tokens") or {}
    access = tokens.get("access_token") or ""
    claims = _jwt_claims(access) if access else {}
    exp = int(claims.get("exp", 0) or 0)
    now = int(time.time())
    id_claims = _jwt_claims(tokens.get("id_token") or "") if tokens.get("id_token") else {}
    return {
        "present": True,
        "readable": True,
        "auth_mode": payload.get("auth_mode"),
        "email": id_claims.get("email"),
        "has_access_token": bool(access),
        "has_refresh_token": bool(tokens.get("refresh_token")),
        "access_token_expired": bool(exp and exp <= now),
        "expires_in_seconds": (exp - now) if exp else None,
    }


def owned_status() -> dict[str, Any]:
    """Secret-free presence check of the foundation's OWNED Codex store.

    After `atlas auth import-codex`, runtime credential resolution reads the
    foundation store (never ~/.codex again — D-001). So *this*, not
    cli_status(), answers "can an oauth_import run execute right now". A
    present refresh_token is sufficient: the foundation refreshes an expired
    access token at run time.
    """
    try:
        fa = _foundation_auth()
        data = fa._read_codex_tokens()  # noqa: SLF001 — foundation API (D-001)
    except Exception as exc:  # noqa: BLE001 — missing store == not imported
        return {"present": False, "reason": str(exc)[:120]}
    tokens = data.get("tokens") or {}
    access = str(tokens.get("access_token") or "")
    claims = _jwt_claims(access) if access else {}
    exp = int(claims.get("exp", 0) or 0)
    now = int(time.time())
    return {
        "present": True,
        "has_refresh_token": bool(tokens.get("refresh_token")),
        "access_token_expired": bool(exp and exp <= now),
        "expires_in_seconds": (exp - now) if exp else None,
    }


def codex_model_ids() -> list[str]:
    """Codex-backend-capable model slugs, operator default first.

    Offline resolution (config.toml default > cache > curated fallback); never
    performs a network call here. Returns [] when the foundation is absent so
    callers can no-op instead of failing a run on model discovery.
    """
    try:
        foundation = _find_foundation()
        if foundation is not None:
            path = str(foundation)
            if path not in sys.path:
                sys.path.insert(0, path)
        from hermes_cli import codex_models  # noqa: PLC0415

        return list(codex_models.get_codex_model_ids())
    except Exception as exc:  # noqa: BLE001 — discovery is best-effort
        logger.debug("codex model discovery unavailable: %s", exc)
        return []


def import_from_codex_cli() -> dict[str, Any]:
    """Bootstrap Codex tokens from ~/.codex into the foundation's owned store.

    Delegates to the foundation (read-only on ~/.codex; writes only ~/.hermes).
    Returns a secret-free result. After a successful import the runtime can
    resolve+refresh independently of the Codex CLI.
    """
    fa = _foundation_auth()
    tokens = fa._import_codex_cli_tokens()  # noqa: SLF001 — foundation API (D-001)
    if not tokens:
        return {"imported": False, "reason": "no_valid_codex_tokens"}
    fa._save_codex_tokens(tokens)  # noqa: SLF001
    return {"imported": True}


def resolve_codex_credentials(*, force_refresh: bool = False) -> dict[str, str]:
    """Resolve runtime Codex credentials via the foundation (incl. refresh).

    Returns {provider, base_url, api_key}. `api_key` is the live access_token
    for runtime use only — never log it, never surface it through status APIs.
    """
    fa = _foundation_auth()
    resolved = fa.resolve_codex_runtime_credentials(force_refresh=force_refresh)
    return {
        "provider": str(resolved.get("provider") or "openai-codex"),
        "base_url": str(resolved.get("base_url") or ""),
        "api_key": str(resolved.get("api_key") or ""),
    }


__all__ = [
    "cli_status",
    "codex_home",
    "codex_model_ids",
    "import_from_codex_cli",
    "owned_status",
    "resolve_codex_credentials",
    "set_foundation_loader",
]
