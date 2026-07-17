"""Function-slot model routing: curator/auxiliary autoconfig on the mesh.

The Hermes foundation runs its side tasks — curator review, context
compression, title generation — on ``auxiliary.<task>.{provider,model}``
slots read from its own config store (``hermes_cli.config``). This module
keeps those slots in sync with the ATLAS provider mesh: when
``functions.autoconfig`` is on, managed slots bind to the lightest model
available on the active provider (Codex -> gpt-5.4-mini class), and the
``functions.curator_model`` / ``functions.auxiliary_model`` overrides always
win. Completion judgement has a separate explicit slot; when unset it inherits
the initiating session model at call time.

D-001 holds: the foundation is used as a library, never edited. ATLAS writes
only slots it stamped ``managed_by: atlas`` (or untouched auto slots) so an
operator's hand-authored Hermes routing is never clobbered. Everything here
is best-effort — a routing sync failure must never fail a run.
"""
from __future__ import annotations

import logging
from pathlib import Path
from typing import Any, Optional

from atlas_runtime import codex_auth, config_service

logger = logging.getLogger(__name__)

MANAGED_MARKER = "atlas"

# Foundation side tasks ATLAS manages. Vision/web_extract are deliberately
# excluded: they need capability-matched (multimodal) models, not light ones.
CURATOR_TASK = "curator"
AUXILIARY_TASKS = ("compression", "title_generation")
JUDGE_TASK = "goal_judge"

# Best-effort lightest chat-capable model per provider. Unknown providers
# return no binding and the foundation's own "auto" chain stays in charge.
_LIGHT_MODEL_BY_PROVIDER = {
    "openai-codex": "gpt-5.4-mini",
    "openai": "gpt-5.4-mini",
    "anthropic": "claude-haiku-4-5",
    "google": "gemini-2.5-flash",
    "openrouter": "google/gemini-2.5-flash",
}


def lightest_model_for(
    provider: str, auth_mode: str, configured_model: str
) -> Optional[tuple[str, str]]:
    """(provider, model) side tasks should use on the active mesh.

    None means "leave the foundation's own resolution alone": claude_code
    runs bypass the foundation harness entirely, and unknown api_key
    providers have no safe light-model guess.
    """
    if auth_mode == "claude_code":
        return None
    if auth_mode == "oauth_import":
        ids = codex_auth.codex_model_ids()
        light = next((m for m in ids if "mini" in m or "nano" in m), None)
        return ("openai-codex", light or _LIGHT_MODEL_BY_PROVIDER["openai-codex"])
    if auth_mode == "freellmapi":
        # The endpoint is already free; reuse the configured model on it.
        return ("custom", configured_model) if configured_model else None
    light = _LIGHT_MODEL_BY_PROVIDER.get((provider or "").strip().lower())
    return ((provider or "").strip(), light) if light else None


def _slot_from_override(override: str) -> Optional[dict[str, str]]:
    """Parse a "provider/model" override into a slot; None when unset."""
    override = (override or "").strip()
    if not override:
        return None
    provider, _, model = override.partition("/")
    if not provider or not model:
        return None
    return {"provider": provider, "model": model, "managed_by": MANAGED_MARKER}


def resolve_bindings(
    config: Optional[config_service.AtlasConfig] = None,
) -> dict[str, dict[str, str]]:
    """task -> desired foundation aux slot for the active mesh; {} = nothing."""
    config = config or config_service.load_config()
    functions = config.functions
    resolved = config_service.resolve_provider(config)
    auth_mode = str(resolved.get("auth_mode") or "api_key")

    auto: Optional[dict[str, str]] = None
    if functions.autoconfig:
        light = lightest_model_for(
            str(resolved.get("provider") or ""),
            auth_mode,
            str(resolved.get("model") or ""),
        )
        if light is not None:
            auto = {"provider": light[0], "model": light[1], "managed_by": MANAGED_MARKER}
            if auth_mode == "freellmapi" and resolved.get("base_url"):
                auto["base_url"] = str(resolved["base_url"])

    curator = _slot_from_override(functions.curator_model) or auto
    auxiliary = _slot_from_override(functions.auxiliary_model) or auto
    # Judge inheritance is intentionally not auto-bound to the light model.
    # With no override, the caller supplies the live session runtime.
    judge = _slot_from_override(functions.judge_model)

    bindings: dict[str, dict[str, str]] = {}
    if curator:
        bindings[CURATOR_TASK] = dict(curator)
    if auxiliary:
        for task in AUXILIARY_TASKS:
            bindings[task] = dict(auxiliary)
    if judge:
        bindings[JUDGE_TASK] = dict(judge)
    return bindings


def _foundation_config_path() -> Optional[Path]:
    """The foundation's own config.yaml path, via its config module."""
    foundation = codex_auth._find_foundation()  # noqa: SLF001 — shared locator (D-001)
    if foundation is None:
        return None
    import sys  # noqa: PLC0415

    path = str(foundation)
    if path not in sys.path:
        sys.path.insert(0, path)
    from hermes_cli import config as hermes_config  # noqa: PLC0415

    return Path(hermes_config.get_config_path())


def _atlas_owned(slot: dict[str, Any]) -> bool:
    """True when ATLAS may write this slot: previously stamped, or unset/auto."""
    if slot.get("managed_by") == MANAGED_MARKER:
        return True
    provider = str(slot.get("provider") or "").strip().lower()
    model = str(slot.get("model") or "").strip()
    return provider in ("", "auto") and not model


def apply_autoconfig(
    config: Optional[config_service.AtlasConfig] = None,
    *,
    config_path: Optional[Path] = None,
) -> dict[str, Any]:
    """Sync managed foundation aux slots to the active mesh. Never raises."""
    report: dict[str, Any] = {"applied": False, "tasks": {}, "reason": ""}
    try:
        bindings = resolve_bindings(config)
        if not bindings:
            report["reason"] = "no bindings for the active mode"
            return report
        path = config_path or _foundation_config_path()
        if path is None:
            report["reason"] = "foundation config unavailable"
            return report
        import yaml  # noqa: PLC0415 — foundation dependency, present with it

        raw: dict[str, Any] = {}
        if path.exists():
            loaded = yaml.safe_load(path.read_text(encoding="utf-8"))
            if isinstance(loaded, dict):
                raw = loaded
        aux = raw.get("auxiliary")
        if not isinstance(aux, dict):
            aux = {}
            raw["auxiliary"] = aux

        changed = False
        for task, desired in bindings.items():
            existing = aux.get(task) if isinstance(aux.get(task), dict) else {}
            if existing and not _atlas_owned(existing):
                # Adopt a slot that already holds exactly the binding we would
                # write (same provider/model, just missing our stamp) so a
                # later provider switch can retarget it; anything else is a
                # deliberate operator choice and stays untouched (D-001).
                same_target = existing.get("provider") == desired.get(
                    "provider"
                ) and existing.get("model") == desired.get("model")
                if not same_target:
                    report["tasks"][task] = "operator-owned"
                    continue
            merged = {**existing, **desired}
            if merged != existing:
                aux[task] = merged
                changed = True
                report["tasks"][task] = "updated"
            else:
                report["tasks"][task] = "current"
        if changed:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(
                yaml.safe_dump(raw, default_flow_style=False, sort_keys=False),
                encoding="utf-8",
            )
        report["applied"] = True
    except Exception as exc:  # noqa: BLE001 — routing sync must never fail a run
        report["reason"] = str(exc)
        logger.debug("function-router autoconfig skipped: %s", exc)
    return report


__all__ = [
    "AUXILIARY_TASKS",
    "CURATOR_TASK",
    "JUDGE_TASK",
    "apply_autoconfig",
    "lightest_model_for",
    "resolve_bindings",
]
