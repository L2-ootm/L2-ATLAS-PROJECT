"""NativeAtlasAgent — the in-process ATLAS/Hermes-foundation runtime (P4).

Wires the vendored foundation harness (`AIAgent` in foundation/atlas-hermes/
run_agent.py) into a run: assemble → execute → map outcome. D-001 holds — this
*imports and uses* the foundation; it never edits it. The harness result dict
(`{final_response, messages, api_calls, completed, failed, error}`) is mapped
onto the ATLAS AuditEvent bus and a RunOutcome.

Safety substrate (LOOP-ENGINEERING-SYNTHESIS Layers 2 & 3):
  - Secret stop: the prompt is scanned with SECRET_PATTERNS before it reaches the
    agent; a match fails the run immediately (stop_reason="secret_in_prompt").
  - Max-runtime watchdog: the conversation runs on a daemon thread joined with a
    timeout (stop_reason="max_runtime_exceeded").
  - Claim taxonomy: the outcome carries evidence/inferences/uncertainties.

The foundation import is lazy + injectable (`agent_factory`) so native-only
installs and unit tests run without the foundation or any credentials. Real
output requires a provider configured via `atlas-agent setup`; with none, the
harness returns failed/error and this maps to an honest failed run (not theater).
"""
from __future__ import annotations

import logging
import sqlite3
import threading
import time
from pathlib import Path
from typing import Any, Callable, Optional

from atlas_core.schemas.core import SECRET_PATTERNS

from atlas_runtime.agents.base import AgentRuntime, RunOutcome
from atlas_runtime.audit_service import emit

logger = logging.getLogger(__name__)

_SUMMARY_CAP = 2000
_DEFAULT_MAX_RUNTIME_S = 1800.0  # 30 min
_DEFAULT_MAX_ITERATIONS = 40

# A harness factory: given a session_id, return an object exposing
# `run_conversation(user_message, system_message=None) -> dict`.
HarnessFactory = Callable[..., Any]


def _find_foundation() -> Optional[Path]:
    """Walk up from this file to locate foundation/atlas-hermes."""
    for parent in Path(__file__).resolve().parents:
        candidate = parent / "foundation" / "atlas-hermes"
        if candidate.is_dir():
            return candidate
    return None


def _default_factory(
    session_id: str,
    max_iterations: int,
    *,
    model: str = "",
    provider: Optional[str] = None,
    base_url: Optional[str] = None,
    api_key: Optional[str] = None,
) -> Any:
    """Construct a real foundation AIAgent (lazy import; path-injected).

    `model`/`provider`/`base_url`/`api_key` are resolved from ATLAS config +
    the active Focus by the caller (A4). Empty values are omitted so the
    foundation falls back to its own resolution rather than overriding with
    blanks — preserving the honest-failure path when nothing is configured.
    """
    foundation = _find_foundation()
    if foundation is not None:
        import sys

        path = str(foundation)
        # Intentional process-global, one-time mutation: sys.path is never
        # restored. Safe for the current single-process-per-run CLI model;
        # a future long-lived daemon sharing this code path with a
        # configurable foundation location would need to revisit this.
        if path not in sys.path:
            sys.path.insert(0, path)
    from run_agent import AIAgent  # noqa: PLC0415 — lazy, optional dependency

    kwargs: dict[str, Any] = dict(
        model=model,
        quiet_mode=True,
        skip_context_files=True,
        skip_memory=True,
        max_iterations=max_iterations,
        session_id=session_id,
    )
    if provider:
        kwargs["provider"] = provider
    if base_url:
        kwargs["base_url"] = base_url
    if api_key:
        kwargs["api_key"] = api_key
    return AIAgent(**kwargs)


class NativeAtlasAgent(AgentRuntime):
    name = "native"

    def __init__(
        self,
        agent_factory: Optional[HarnessFactory] = None,
        *,
        max_runtime_s: float = _DEFAULT_MAX_RUNTIME_S,
        max_iterations: int = _DEFAULT_MAX_ITERATIONS,
        model: str = "",
        provider: Optional[str] = None,
    ) -> None:
        self._agent_factory = agent_factory
        self._max_runtime_s = max_runtime_s
        self._max_iterations = max_iterations
        # Explicit overrides take precedence over ATLAS-config resolution; left
        # empty, execute() resolves them from config + the active Focus (A4).
        self._model = model
        self._provider = provider

    def _resolve_provider(
        self, conn: sqlite3.Connection
    ) -> tuple[str, Optional[str], Optional[str], Optional[str]]:
        """Resolve (model, provider, base_url, api_key) for this run from ATLAS
        config, with the active Focus.framework overriding the model. Fail-open
        to the constructor values so a config/DB hiccup never blocks a run."""
        model, provider, base_url, api_key = self._model, self._provider, None, None
        try:
            from atlas_runtime import config_service, focus_service  # noqa: PLC0415

            focus = focus_service.get_current_focus(conn)
            framework = (focus.framework if focus else "") or ""
            resolved = config_service.resolve_provider(focus_framework=framework)
            model = self._model or resolved["model"]
            provider = self._provider or resolved["provider"]
            base_url = resolved["base_url"] or None
            api_key = resolved["api_key"] or None
            # auth_mode="oauth_import" (Codex/ChatGPT): delegate credential
            # resolution to the foundation, which imports from ~/.codex once and
            # then owns refresh in its own store (D-001; never touches ~/.codex
            # after import). Model stays operator/Focus-chosen.
            if resolved.get("auth_mode") == "oauth_import":
                from atlas_runtime import codex_auth  # noqa: PLC0415

                creds = codex_auth.resolve_codex_credentials()
                provider = self._provider or creds["provider"] or provider
                base_url = creds["base_url"] or base_url
                api_key = creds["api_key"] or api_key
        except Exception as exc:  # noqa: BLE001 — never block a run on config
            logger.debug("native provider resolution fell back to defaults: %s", exc)
        return model, provider, base_url, api_key

    def execute(
        self,
        conn: sqlite3.Connection,
        lock: threading.Lock,
        *,
        mission_id: str,
        run_id: str,
        prompt: str,
        cancel_token: Optional[threading.Event] = None,
    ) -> RunOutcome:
        # Persist the generated prompt/tool/context contract before foundation
        # execution. Failure is fail-safe for auditability: no untracked run.
        try:
            from atlas_runtime.agent_contract_service import (  # noqa: PLC0415
                persist_contract,
                prepare_run_contract,
            )

            persist_contract(
                conn,
                prepare_run_contract(
                    conn,
                    run_id=run_id,
                    mission_id=mission_id,
                    prompt=prompt,
                ),
            )
        except Exception as exc:  # noqa: BLE001
            logger.warning("NativeAtlasAgent contract preparation failed: %s", exc)
            return RunOutcome(
                status="failed",
                summary=f"contract preparation failed: {exc}"[:_SUMMARY_CAP],
                stop_reason="contract_preparation_failed",
            )

        # --- Layer 2: secret stop (pre-execution, hard gate) ---------------
        if _contains_secret(prompt):
            self._safe_emit(
                conn, lock, run_id, event_type="failure",
                data={"runtime": "native", "stop_reason": "secret_in_prompt"},
            )
            return RunOutcome(
                status="failed",
                summary="stopped: prompt appears to contain a secret/credential",
                stop_reason="secret_in_prompt",
                uncertainties=("prompt redaction required before this run can proceed",),
            )

        self._safe_emit(
            conn, lock, run_id, event_type="tool_call", tool_name="native_runtime",
            data={"runtime": "native", "mission_id": mission_id},
        )

        # --- resolve the harness factory -----------------------------------
        # The default factory selects provider/model from ATLAS config + the
        # active Focus (A4); an injected factory (tests) bypasses resolution.
        factory = self._agent_factory
        if factory is None:
            model, provider, base_url, api_key = self._resolve_provider(conn)
            if not api_key:
                # Zero-credential path: route to the deterministic mock so a
                # mission run still completes with a clearly-labeled MOCK MODE
                # response. A non-empty-but-wrong api_key (configured but
                # invalid) intentionally falls through to the else branch below
                # so the real provider's own honest failure surfaces — never
                # silently masked (Phase A4 honest-failure contract).
                from atlas_runtime.agents.mock import mock_factory  # noqa: PLC0415

                factory = lambda session_id: mock_factory(  # noqa: E731
                    session_id, model=model, provider=provider,
                )
                self._safe_emit(
                    conn, lock, run_id, event_type="tool_call", tool_name="mock",
                    data={"runtime": "native", "mock_mode": True},
                )
            else:
                factory = lambda session_id: _default_factory(  # noqa: E731
                    session_id,
                    self._max_iterations,
                    model=model,
                    provider=provider,
                    base_url=base_url,
                    api_key=api_key,
                )
        try:
            agent = factory(session_id=run_id)
        except Exception as exc:  # foundation missing / construction error
            logger.warning("NativeAtlasAgent harness unavailable: %s", exc)
            self._safe_emit(
                conn, lock, run_id, event_type="failure",
                data={"runtime": "native", "error": str(exc), "stop_reason": "harness_unavailable"},
            )
            return RunOutcome(
                status="failed",
                summary=f"native harness unavailable: {exc}"[:_SUMMARY_CAP],
                stop_reason="harness_unavailable",
            )

        # --- Layer 2: max-runtime watchdog (run on a daemon thread) --------
        result_holder: dict[str, Any] = {}
        error_holder: dict[str, BaseException] = {}

        def _drive() -> None:
            try:
                result_holder["result"] = agent.run_conversation(prompt)
            except BaseException as exc:  # noqa: BLE001 — surfaced below
                error_holder["error"] = exc

        worker = threading.Thread(target=_drive, name=f"native-run-{run_id[:8]}", daemon=True)
        worker.start()
        # Cancel-aware watchdog: poll-join in small intervals so a set cancel_token
        # is observed between turns. The single opaque run_conversation() call cannot
        # be interrupted mid-call (D-001: no foundation hook); cancellation takes effect
        # at this checkpoint, and the max-runtime deadline remains the hard backstop.
        _deadline = time.monotonic() + self._max_runtime_s
        _poll = min(0.1, self._max_runtime_s) if self._max_runtime_s > 0 else 0.1
        while worker.is_alive():
            if cancel_token is not None and cancel_token.is_set():
                self._safe_emit(
                    conn, lock, run_id, event_type="run_cancelled",
                    data={"runtime": "native", "stop_reason": "cancelled"},
                )
                return RunOutcome(
                    status="failed",
                    summary="cancelled: cooperative cancel observed at watchdog checkpoint",
                    stop_reason="cancelled",
                )
            remaining = _deadline - time.monotonic()
            if remaining <= 0:
                break
            worker.join(min(_poll, remaining))
        if worker.is_alive():
            self._safe_emit(
                conn, lock, run_id, event_type="failure",
                data={"runtime": "native", "stop_reason": "max_runtime_exceeded"},
            )
            return RunOutcome(
                status="failed",
                summary=f"stopped: exceeded max runtime ({self._max_runtime_s:.0f}s)",
                stop_reason="max_runtime_exceeded",
                uncertainties=("run was still executing when the watchdog fired",),
            )

        if "error" in error_holder:
            exc = error_holder["error"]
            logger.warning("NativeAtlasAgent run failed: %s", exc)
            self._safe_emit(
                conn, lock, run_id, event_type="failure",
                data={"runtime": "native", "error": str(exc)},
            )
            return RunOutcome(status="failed", summary=f"native error: {exc}"[:_SUMMARY_CAP])

        return self._map_result(conn, lock, run_id, result_holder.get("result", {}))

    # -- internal ----------------------------------------------------------

    def _map_result(
        self,
        conn: sqlite3.Connection,
        lock: threading.Lock,
        run_id: str,
        result: dict[str, Any],
    ) -> RunOutcome:
        """Map the harness result dict → audit event + RunOutcome with claims."""
        final_response = (result.get("final_response") or "").strip()
        api_calls = result.get("api_calls") or 0
        completed = bool(result.get("completed"))
        failed = bool(result.get("failed"))
        error = _clean_error(result.get("error"))

        self._safe_emit(
            conn, lock, run_id, event_type="llm_call",
            data={
                "runtime": "native",
                "result": True,
                "completed": completed,
                "failed": failed,
                "api_calls": api_calls,
                "text": final_response[:_SUMMARY_CAP],
            },
        )

        status = "succeeded" if (completed and not failed and not error) else "failed"
        # --- Layer 3: claim taxonomy ---------------------------------------
        evidence: list[str] = []
        inferences: list[str] = []
        uncertainties: list[str] = []
        if api_calls:
            evidence.append(f"agent made {api_calls} model call(s)")
        if status == "succeeded":
            evidence.append("harness reported the conversation completed")
            # Output not independently verified by ATLAS — the agent's own claim.
            inferences.append("final response reflects the agent's own account of its work")
        if error:
            uncertainties.append(f"harness error: {str(error)[:200]}")
        if not final_response:
            uncertainties.append("no final response text returned")

        summary = (final_response or (str(error) if error else "native run produced no output"))[:_SUMMARY_CAP]
        return RunOutcome(
            status=status,
            summary=summary,
            evidence=tuple(evidence),
            inferences=tuple(inferences),
            uncertainties=tuple(uncertainties),
        )

    @staticmethod
    def _safe_emit(
        conn: sqlite3.Connection,
        lock: threading.Lock,
        run_id: str,
        **kwargs: Any,
    ) -> None:
        try:
            emit(conn, lock, run_id=run_id, **kwargs)
        except Exception as exc:  # fail-open audit, never crash the run
            logger.warning("NativeAtlasAgent audit emit failed: %s", exc)


def _contains_secret(text: str) -> bool:
    return any(p.search(text or "") for p in SECRET_PATTERNS)


def _clean_error(error: Any) -> Optional[str]:
    """Collapse noisy provider error payloads (e.g. an HTML 4xx page) into a
    concise operator-facing message so summaries/observations stay readable."""
    if not error:
        return error
    text = str(error)
    low = text.lower()
    if "<html" in low or "<!doctype" in low:
        return "provider returned an HTML error page (likely auth/credentials — run `atlas-agent setup`)"
    return text[:_SUMMARY_CAP]
