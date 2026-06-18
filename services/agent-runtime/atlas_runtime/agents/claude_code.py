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
    ) -> RunOutcome:
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
                    self._safe_emit(
                        conn, lock, run_id, event_type="tool_call",
                        tool_name=getattr(block, "name", None),
                        tool_call_id=getattr(block, "id", None),
                        data={"runtime": "claude_code", "input": getattr(block, "input", None)},
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
