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
# Delta coalescing: the gateway relays audit rows on a ~200ms poll, so
# flushing every token as its own row would burn one SQLite write per token
# for no visible benefit — coalesce into ~150ms/48-char chunks instead.
_DELTA_FLUSH_INTERVAL_S = 0.15
_DELTA_FLUSH_CHARS = 48

# The foundation's mid-tool-call silent stream retry (chat_completion_helpers.py
# ~2144-2186, D-001 vendored — not editable here) intentionally re-streams a
# turn's preamble from scratch after a transient connection drop, firing this
# exact marker text through stream_delta_callback with NO end-of-turn signal
# in between (documented tradeoff: losing the in-flight tool call is worse
# than a duplicated preamble). Detecting it here lets ATLAS close the
# pre-drop segment as its own part instead of letting the regenerated text
# concatenate seamlessly onto it — the client already knows how to start a
# fresh part on an end_of_turn boundary (see chat.ts's streamingText.open
# handling), so this turns silent, garbled-looking duplication into two
# clearly separated segments with the reconnect notice between them.
_STREAM_RETRY_MARKER = "Connection dropped mid tool-call"

# A harness factory: given a session_id, return an object exposing
# `run_conversation(user_message, system_message=None) -> dict`.
HarnessFactory = Callable[..., Any]


def _diff_cumulative_chunk(previous_text: str, chunk_text: str) -> str:
    """Normalizes an incoming stream chunk against everything already seen
    for the current turn, returning just the new increment.

    ATLAS's `_DeltaBuffer` is the single choke point every streaming surface
    (atlas-terminal, web-ui-react) consumes through — it must not trust the
    upstream provider mesh (freellmapi and any provider behind it) to always
    honor the incremental-delta contract. Some upstreams (observed: Gemini
    via freellmapi, ULTRAREVIEW-streaming-duplication-R4) resend the full
    text accumulated so far in a single chunk instead of just the new
    fragment; forwarding that verbatim duplicates/overlaps the rendered
    text. This defends the boundary ATLAS actually owns, rather than relying
    on every sidecar/provider to normalize correctly upstream.
    """
    if not previous_text:
        return chunk_text
    if chunk_text == previous_text:
        return ""
    if chunk_text.startswith(previous_text):
        return chunk_text[len(previous_text):]
    if previous_text.startswith(chunk_text):
        return ""
    return chunk_text


def _repair_cumulative_final(final_text: str, streamed_turn_text: str) -> str:
    """Repairs a `final_response` corrupted by cumulative-chunk concatenation.

    The foundation builds the assistant message by appending every raw
    `delta.content` chunk (chat_completion_helpers.py ~1814, D-001 vendored —
    not editable here), so a provider that resends cumulative text produces a
    final string like ``p1 + p2 + ... + truth`` where each ``p_i`` is a stale
    prefix of the true text. `_DeltaBuffer` already normalized the same chunk
    stream, so its per-turn text is the ground truth for what the final turn
    actually said. Repair triggers only when the foundation text ends with the
    streamed truth AND the leftover head decomposes entirely into prefixes of
    it — the exact fingerprint of cumulative concatenation. Anything else
    (think-block stripping, appended footers, retry re-streams, non-streaming
    paths) fails that check and passes through untouched.
    """
    truth = streamed_turn_text.strip()
    if not truth or not final_text or final_text == truth:
        return final_text
    if len(final_text) <= len(truth) or not final_text.endswith(truth):
        return final_text
    head = final_text[: len(final_text) - len(truth)]
    i = 0
    while i < len(head):
        j = 0
        while i + j < len(head) and j < len(truth) and head[i + j] == truth[j]:
            j += 1
        if j == 0:
            return final_text
        i += j
    return truth


class _DeltaBuffer:
    """Coalesces a foundation `stream_delta_callback(chunk | None)` stream into
    flush-sized `llm_delta` audit events.

    The foundation invokes the callback once per token (or provider-side
    chunk) while streaming, and once with `None` to signal the end of one
    assistant turn (e.g. before tool execution, or at the final response).
    Emitting an audit row per token would be one SQLite write per token; this
    buffers text and flushes on a time/size threshold, plus always on the
    `None` end-of-turn signal so no trailing text is dropped.
    """

    def __init__(
        self,
        on_flush: Callable[[str, bool], None],
        *,
        interval_s: float = _DELTA_FLUSH_INTERVAL_S,
        max_chars: int = _DELTA_FLUSH_CHARS,
    ) -> None:
        self._on_flush = on_flush
        self._interval_s = interval_s
        self._max_chars = max_chars
        self._buffer: list[str] = []
        self._last_flush = time.monotonic()
        self._turn_open = False
        # Normalized text accumulated for the currently-open turn — what
        # incoming chunks are diffed against (see _diff_cumulative_chunk).
        self._turn_text = ""
        # Normalized text of the most recently CLOSED turn. For the final
        # assistant turn this is the ground truth used to repair a
        # cumulative-corrupted foundation final_response (_repair_cumulative_final).
        self.last_turn_text = ""

    def push(self, chunk: Optional[str]) -> None:
        if chunk is None:
            if self._turn_open:
                self._flush(final=True)
                self._turn_open = False
                self.last_turn_text = self._turn_text
            self._turn_text = ""
            return
        if self._turn_open and _STREAM_RETRY_MARKER in chunk:
            # Mid-turn silent retry: close the pre-drop segment as its own
            # part before the reconnect marker + regenerated text start a
            # new one (see _STREAM_RETRY_MARKER comment above).
            self._flush(final=True)
            self._turn_open = False
            self.last_turn_text = self._turn_text
            self._turn_text = ""
        normalized = _diff_cumulative_chunk(self._turn_text, chunk)
        self._turn_text += normalized
        self._turn_open = True
        if not normalized:
            return
        self._buffer.append(normalized)
        now = time.monotonic()
        buffered_len = sum(len(c) for c in self._buffer)
        if now - self._last_flush >= self._interval_s or buffered_len >= self._max_chars:
            self._flush(final=False)
            self._last_flush = now

    def _flush(self, *, final: bool) -> None:
        text = "".join(self._buffer)
        self._buffer.clear()
        if not text and not final:
            return
        self._on_flush(text, final)


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
    reasoning_effort: str = "",
    stream_delta_callback: Optional[Callable[[Optional[str]], None]] = None,
) -> Any:
    """Construct a real foundation AIAgent (lazy import; path-injected).

    `model`/`provider`/`base_url`/`api_key` are resolved from ATLAS config +
    the active Focus by the caller (A4). Empty values are omitted so the
    foundation falls back to its own resolution rather than overriding with
    blanks — preserving the honest-failure path when nothing is configured.

    `stream_delta_callback` is the foundation's native streaming hook
    (`AIAgent(stream_delta_callback=...)`): registering it makes
    `_has_stream_consumers()` true, which the foundation's own dispatch uses
    to prefer the streaming API path over the batch one.
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
    if reasoning_effort:
        # The foundation clamps effort per provider; empty means default.
        kwargs["reasoning_config"] = {"effort": reasoning_effort}
    if stream_delta_callback is not None:
        kwargs["stream_delta_callback"] = stream_delta_callback
    return AIAgent(**kwargs)


def _resolve_reasoning_effort() -> str:
    """The operator-configured reasoning effort, or "" (provider default)."""
    try:
        from atlas_runtime import config_service  # noqa: PLC0415

        return config_service.load_config().provider.reasoning_effort
    except Exception:  # noqa: BLE001 — never block a run on config
        return ""


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
    ) -> tuple[str, Optional[str], Optional[str], Optional[str], str]:
        """Resolve (model, provider, base_url, api_key, auth_mode) for this run
        from ATLAS config, with the active Focus.framework overriding the model.
        auth_mode is threaded out so execute() can treat credential-less modes
        (freellmapi) as real runs. Fail-open to the constructor values so a
        config/DB hiccup never blocks a run."""
        model, provider, base_url, api_key = self._model, self._provider, None, None
        auth_mode = "api_key"
        try:
            from atlas_runtime import config_service, focus_service  # noqa: PLC0415

            focus = focus_service.get_current_focus(conn)
            framework = (focus.framework if focus else "") or ""
            if framework and not _is_model_override(conn, framework):
                # Focus.framework doubles as a model override (A4), but
                # operators also store methodology labels ("GSD") there. A
                # non-model value must never reach a provider as a model id.
                framework = ""
            resolved = config_service.resolve_provider(focus_framework=framework)
            model = self._model or resolved["model"]
            provider = self._provider or resolved["provider"]
            base_url = resolved["base_url"] or None
            api_key = resolved["api_key"] or None
            auth_mode = resolved.get("auth_mode") or "api_key"
            # auth_mode="oauth_import" (Codex/ChatGPT): delegate credential
            # resolution to the foundation, which imports from ~/.codex once and
            # then owns refresh in its own store (D-001; never touches ~/.codex
            # after import). Model stays operator/Focus-chosen.
            if auth_mode == "oauth_import":
                from atlas_runtime import codex_auth  # noqa: PLC0415

                creds = codex_auth.resolve_codex_credentials()
                provider = self._provider or creds["provider"] or provider
                base_url = creds["base_url"] or base_url
                api_key = creds["api_key"] or api_key
                # The Codex backend rejects non-Codex model slugs outright
                # ("The '<model>' model is not supported ..."); project the
                # configured model onto what Codex will actually accept.
                model = codex_auth.effective_codex_model(model)
        except Exception as exc:  # noqa: BLE001 — never block a run on config
            logger.debug("native provider resolution fell back to defaults: %s", exc)
        return model, provider, base_url, api_key, auth_mode

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
                RunContractSnapshot,
                persist_contract,
                prepare_run_contract,
            )

            contract_snapshot: RunContractSnapshot = persist_contract(
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
        # Real-provider path assigns this; stays None for mock/injected
        # factories where there is no stream_delta_callback to flush.
        delta_buffer: Optional[_DeltaBuffer] = None
        factory = self._agent_factory
        if factory is None:
            model, provider, base_url, api_key, auth_mode = self._resolve_provider(conn)
            # freellmapi resolves a KEYLESS base_url — free OpenAI-compatible
            # endpoints need a base_url, not a key — so it is a real run even
            # with an empty api_key. Every other mode requires a resolved
            # credential; an empty key falls back to the deterministic mock.
            free_keyless = auth_mode == "freellmapi" and bool(base_url)
            if free_keyless:
                # Privacy posture (§2.3): free models may log prompts. Surface a
                # one-time, audited warning at the run boundary (D-002 audit-first)
                # so the operator sees the cost of the mode they wired.
                self._safe_emit(
                    conn, lock, run_id, event_type="tool_call", tool_name="freellmapi",
                    data={
                        "runtime": "native",
                        "privacy_warning": (
                            "free models may log prompts — do not send secrets"
                        ),
                    },
                )
            if not api_key and not free_keyless:
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
                # Keep foundation side-task slots (curator/auxiliary) bound to
                # the lightest model on the active mesh (best-effort, audited
                # config write inside the foundation's own store).
                from atlas_runtime import function_router, subagent_service  # noqa: PLC0415

                function_router.apply_autoconfig()
                # Foundation delegation observer (F2): register the atlas_audit
                # hooks with the foundation plugin manager and map this run's
                # harness session, so delegate_tool subagent spawns emit
                # subagent_run AuditEvents. Best-effort; never blocks the run.
                subagent_service.ensure_foundation_bridge(conn, run_id=run_id)
                reasoning_effort = _resolve_reasoning_effort()

                def _emit_delta(text: str, final: bool) -> None:
                    data: dict[str, Any] = {"runtime": "native", "delta": text}
                    if final:
                        data["end_of_turn"] = True
                    self._safe_emit(conn, lock, run_id, event_type="llm_delta", data=data)

                delta_buffer = _DeltaBuffer(_emit_delta)
                factory = lambda session_id: _default_factory(  # noqa: E731
                    session_id,
                    self._max_iterations,
                    model=model,
                    provider=provider,
                    base_url=base_url,
                    api_key=api_key,
                    reasoning_effort=reasoning_effort,
                    stream_delta_callback=delta_buffer.push,
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

        system_message = _contract_system_message(contract_snapshot)

        def _drive() -> None:
            try:
                result_holder["result"] = agent.run_conversation(
                    prompt, system_message=system_message
                )
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

        # The foundation only signals stream_delta_callback(None) at tool
        # boundaries (never after a final, no-tool-call response) — flush any
        # trailing buffered text here so short/simple turns still get a
        # closing llm_delta(end_of_turn=True) instead of the remainder being
        # silently dropped when this function returns.
        if delta_buffer is not None:
            delta_buffer.push(None)

        return self._map_result(
            conn, lock, run_id, result_holder.get("result", {}),
            streamed_final=delta_buffer.last_turn_text if delta_buffer is not None else "",
        )

    # -- internal ----------------------------------------------------------

    def _map_result(
        self,
        conn: sqlite3.Connection,
        lock: threading.Lock,
        run_id: str,
        result: dict[str, Any],
        *,
        streamed_final: str = "",
    ) -> RunOutcome:
        """Map the harness result dict → audit event + RunOutcome with claims."""
        final_response = (result.get("final_response") or "").strip()
        repaired = _repair_cumulative_final(final_response, streamed_final)
        if repaired != final_response:
            logger.warning(
                "cumulative-chunk corruption repaired in final_response "
                "(run %s: %d chars -> %d)", run_id[:8], len(final_response), len(repaired),
            )
            final_response = repaired
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


def _is_model_override(conn: sqlite3.Connection, value: str) -> bool:
    """True when a Focus.framework value actually names a model.

    Accepts provider-scoped ids ("anthropic/claude-opus-4") and ids present in
    the model registry. Everything else — methodology labels like "GSD" — must
    not override the configured model.
    """
    value = value.strip()
    if "/" in value:
        return True
    try:
        from atlas_runtime import model_registry  # noqa: PLC0415

        rows = model_registry.list_models(conn, active_only=False)
        return any(
            str(row.get("model_id", "")).lower() == value.lower() for row in rows
        )
    except Exception:  # noqa: BLE001 — registry unavailable → not a model
        return False


def _contract_system_message(snapshot: Any) -> str:
    """Render the immutable run contract as the harness system message.

    The foundation harness accepts a separate `system_message`; use it for the
    generated bootstrap plus the full secret-redacted operator context so the
    run acts on Current Focus/Goals instead of only the raw mission prompt.
    """
    return (
        "# ATLAS Run Contract\n\n"
        "## Session Bootstrap\n"
        f"{snapshot.bootstrap_message}\n\n"
        "## Operator Context\n"
        f"{snapshot.context_markdown.rstrip()}\n\n"
        "## Dynamic Context Envelope\n"
        f"{snapshot.context_message}"
    )


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
