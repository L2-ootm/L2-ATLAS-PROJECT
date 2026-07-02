"""ClaudeCodeAgent — Claude Agent SDK on the operator's LOCAL session (P4).

Drives `claude-agent-sdk` (which spawns the installed `claude` CLI) so the run
executes on the operator's LOCAL Claude Code subscription session — no API key
(de-risk spike confirmed, 2026-06-18). The SDK's streamed messages are mapped
onto the ATLAS AuditEvent bus for audit parity:

  AssistantMessage.TextBlock  -> llm_call   (assistant text)
  AssistantMessage.ToolUseBlock -> tool_call (name + input)
  ResultMessage               -> llm_call   (usage + cost + subtype)
  any exception               -> failure

The SDK is an OPTIONAL dependency, lazy-imported here, so native-only installs
stay lean. Collaborators (`query_fn`, `options_factory`) are injectable so unit
tests run without the SDK or a live session. Mapping is by class name +
attribute access (duck-typed) to keep the test path SDK-import-free.
"""
from __future__ import annotations

import asyncio
import logging
import sqlite3
import threading
from typing import Any, Callable, Optional

from atlas_runtime.agents.base import AgentRuntime, RunOutcome
from atlas_runtime.audit_service import emit

logger = logging.getLogger(__name__)

_SUMMARY_CAP = 2000


def _result_text(content: Any) -> str:
    """Flatten a ToolResultBlock content payload into a capped display string."""
    if content is None:
        return ""
    if isinstance(content, str):
        return content[:_SUMMARY_CAP]
    if isinstance(content, list):
        parts: list[str] = []
        for item in content:
            if isinstance(item, dict) and isinstance(item.get("text"), str):
                parts.append(item["text"])
            elif isinstance(item, str):
                parts.append(item)
        return "\n".join(parts)[:_SUMMARY_CAP]
    return str(content)[:_SUMMARY_CAP]


class ClaudeCodeAgent(AgentRuntime):
    name = "claude_code"

    def __init__(
        self,
        query_fn: Optional[Callable[..., Any]] = None,
        options_factory: Optional[Callable[[], Any]] = None,
    ) -> None:
        self._query_fn = query_fn
        self._options_factory = options_factory

    def _resolve(self) -> tuple[Callable[..., Any], Callable[[], Any]]:
        if self._query_fn is not None:
            return self._query_fn, (self._options_factory or (lambda: None))
        try:
            from claude_agent_sdk import ClaudeAgentOptions, query  # noqa: PLC0415
        except ImportError as exc:  # pragma: no cover - environment dependent
            raise RuntimeError(
                "claude-agent-sdk is not installed; install atlas-runtime[claude] "
                "to use the claude_code agent runtime"
            ) from exc
        return query, (self._options_factory or (lambda: ClaudeAgentOptions()))

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
        # cancel_token is accepted for ABC conformance. The SDK driver streams
        # asynchronously; a pre-set token short-circuits before the SDK call so a
        # cancelled run never starts a new session.
        if cancel_token is not None and cancel_token.is_set():
            self._safe_emit(
                conn, lock, run_id, event_type="run_cancelled",
                data={"runtime": "claude_code", "stop_reason": "cancelled"},
            )
            return RunOutcome(
                status="failed", summary="cancelled before SDK start", stop_reason="cancelled"
            )
        query_fn, options_factory = self._resolve()
        summary: list[str] = []
        state = {"status": "succeeded"}

        async def _drive() -> None:
            options = options_factory()
            async for msg in query_fn(prompt=prompt, options=options):
                self._map_message(conn, lock, run_id, msg, summary, state)

        try:
            asyncio.run(_drive())
        except Exception as exc:  # fail-safe: report as a failed run, never crash
            logger.warning("ClaudeCodeAgent execute failed: %s", exc)
            self._safe_emit(
                conn, lock, run_id, event_type="failure",
                data={"runtime": "claude_code", "error": str(exc)},
            )
            return RunOutcome(status="failed", summary=f"claude_code error: {exc}"[:_SUMMARY_CAP])

        return RunOutcome(status=state["status"], summary="".join(summary).strip()[:_SUMMARY_CAP])

    # -- internal ----------------------------------------------------------

    def _map_message(
        self,
        conn: sqlite3.Connection,
        lock: threading.Lock,
        run_id: str,
        msg: Any,
        summary: list[str],
        state: dict[str, str],
    ) -> None:
        kind = type(msg).__name__
        if kind == "AssistantMessage":
            for block in getattr(msg, "content", []) or []:
                bkind = type(block).__name__
                if bkind == "TextBlock":
                    text = getattr(block, "text", "") or ""
                    summary.append(text)
                    self._safe_emit(
                        conn, lock, run_id, event_type="llm_call",
                        data={"runtime": "claude_code", "text": text},
                    )
                elif bkind == "ToolUseBlock":
                    # tool_name/tool_call_id ride inside data too: the surface
                    # projection (payload_json) carries only the data string,
                    # so web/TUI tool cards need them there to name and pair
                    # calls.
                    self._safe_emit(
                        conn, lock, run_id, event_type="tool_call",
                        tool_name=getattr(block, "name", None),
                        tool_call_id=getattr(block, "id", None),
                        data={
                            "runtime": "claude_code",
                            "tool_name": getattr(block, "name", None),
                            "tool_call_id": getattr(block, "id", None),
                            "input": getattr(block, "input", None),
                        },
                    )
        elif kind == "UserMessage":
            # Tool results come back as ToolResultBlocks on user-role turns.
            # Emitting them closes the tool_call -> tool_result pair every
            # surface uses to flip a tool card from RUNNING to DONE.
            for block in getattr(msg, "content", []) or []:
                if type(block).__name__ != "ToolResultBlock":
                    continue
                call_id = getattr(block, "tool_use_id", None)
                self._safe_emit(
                    conn, lock, run_id, event_type="tool_completed",
                    tool_call_id=call_id,
                    data={
                        "runtime": "claude_code",
                        "tool_call_id": call_id,
                        "is_error": bool(getattr(block, "is_error", False)),
                        "summary": _result_text(getattr(block, "content", None)),
                    },
                )
        elif kind == "ResultMessage":
            is_error = bool(getattr(msg, "is_error", False))
            if is_error:
                state["status"] = "failed"
            self._safe_emit(
                conn, lock, run_id, event_type="llm_call",
                data={
                    "runtime": "claude_code",
                    "result": True,
                    "is_error": is_error,
                    "subtype": getattr(msg, "subtype", None),
                    "num_turns": getattr(msg, "num_turns", None),
                    "total_cost_usd": getattr(msg, "total_cost_usd", None),
                    "usage": getattr(msg, "usage", None),
                },
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
        except Exception as exc:  # fail-open audit
            logger.warning("ClaudeCodeAgent audit emit failed: %s", exc)
