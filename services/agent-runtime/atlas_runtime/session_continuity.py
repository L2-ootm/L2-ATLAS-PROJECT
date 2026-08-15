"""One definition of what a run remembers of its conversation.

Session continuity used to live entirely inside `agents/native.py`. Nothing
announced that, so the two runtimes added later — `claude_code` and `codex` —
were written without it and executed every operator message as a cold start:
the same session, the same surface, no memory of the previous turn. From the
operator's chair that is indistinguishable from the agent forgetting, and it
switched on and off with the runtime the run happened to use.

This module owns the four decisions, so a fifth runtime inherits them instead
of re-deriving them:

* **which turns are in scope** — `load()`, including the run-window and the
  exclusion of the live run's own message, which is persisted before the turn
  is driven and would otherwise be replayed to the model as history;
* **what the operator actually said** — `operator_message()`, the mission
  intent rather than the compiled brief wrapped around it;
* **how history reaches a model that only accepts one string** — `transcript()`
  and `with_history()`, for the CLI-driven runtimes that have no message list;
* **that recording a turn can never fail a run** — `record()`.

Runtimes that do take a message list (`native`) use `load()` with
`memory_router.history_snippets_to_messages`; the transcript form exists for
the ones that do not.
"""
from __future__ import annotations

import json
import logging
import sqlite3
import threading
from typing import Any, Optional

from atlas_runtime.memory_router import (
    ConversationHistoryRetriever,
    MemorySnippet,
    RouterQuery,
)

logger = logging.getLogger(__name__)

# How far back replay may reach, in prior runs of this session. On a chat
# surface one operator message is one run, so a small window silently caps a
# conversation at that many exchanges however short they were. The real bound
# is the retriever's token budget (ATLAS_CONVERSATION_TOKEN_BUDGET); this only
# stops an ancient session from being scanned end to end.
HISTORY_RUN_WINDOW = 40

_TRANSCRIPT_HEADER = (
    "# Conversation so far\n\n"
    "Earlier turns of this same session, oldest first. The operator can refer "
    "back to any of it without repeating themselves."
)
_TRANSCRIPT_FOOTER = "# End of conversation so far"
_ROLE_LABELS = {"user": "Operator", "assistant": "You", "tool": "Tool result"}


def resolve_session(conn: sqlite3.Connection, run_id: str) -> Optional[str]:
    """The surface session this run belongs to, or None for a session-less run."""
    try:
        row = conn.execute(
            "SELECT session_id FROM runs WHERE id=?", (run_id,)
        ).fetchone()
    except Exception as exc:  # noqa: BLE001 — continuity never fails a run
        logger.debug("Failed to resolve surface session for run %s: %s", run_id, exc)
        return None
    if row and row[0]:
        return str(row[0])
    return None


def operator_message(conn: sqlite3.Connection, mission_id: str, prompt: str) -> str:
    """What the operator typed, not the brief compiled around it.

    Persisting the compiled prompt replays an entire machine-generated context
    brief as an operator turn, which buries the actual ask and invites the model
    to treat synthesized evidence as something a human said.
    """
    try:
        row = conn.execute(
            "SELECT intent FROM missions WHERE id=?", (mission_id,)
        ).fetchone()
    except Exception as exc:  # noqa: BLE001
        logger.debug("Failed to resolve operator prompt for mission %s: %s", mission_id, exc)
        return prompt
    if row and str(row[0] or "").strip():
        return str(row[0]).strip()
    return prompt


def load(
    conn: sqlite3.Connection,
    session_key: Optional[str],
    *,
    exclude_run_id: Optional[str] = None,
) -> list[MemorySnippet]:
    """Prior user/assistant turns of this session, oldest-first and bounded.

    Returns an empty list rather than raising: a run that cannot read its own
    history is degraded, not broken, and the operator is better served by an
    answer without context than by a failed run.
    """
    if not session_key:
        return []
    try:
        return ConversationHistoryRetriever().retrieve(
            conn,
            RouterQuery(
                session_id=session_key,
                max_runs=HISTORY_RUN_WINDOW,
                exclude_run_id=exclude_run_id,
            ),
        )
    except Exception as exc:  # noqa: BLE001 — degraded, not fatal
        logger.debug("Failed to load conversation history for %s: %s", session_key, exc)
        return []


def transcript(snippets: list[MemorySnippet]) -> str:
    """Render replayed turns for a runtime whose only input is one string.

    Labelled and fenced so the model can tell the recalled conversation from
    the message it is being asked to answer — an unlabelled transcript reads as
    instructions arriving now, and the model answers the wrong question.
    """
    if not snippets:
        return ""
    lines = [_TRANSCRIPT_HEADER, ""]
    for snippet in snippets:
        role = snippet.source.partition(":")[0].removeprefix("session_")
        lines.append(f"## {_ROLE_LABELS.get(role, role.title())}")
        lines.append(snippet.text)
        lines.append("")
    lines.append(_TRANSCRIPT_FOOTER)
    return "\n".join(lines)


def with_history(prompt: str, history_transcript: str) -> str:
    """Prefix a prompt with the rendered conversation, if there is any."""
    if not history_transcript:
        return prompt
    return f"{history_transcript}\n\n---\n\n{prompt}"


def record(
    conn: sqlite3.Connection,
    lock: threading.Lock,
    session_key: Optional[str],
    *,
    run_id: str,
    role: str,
    content: str,
    tool_call_id: Optional[str] = None,
    tool_name: Optional[str] = None,
    metadata: Optional[dict[str, Any]] = None,
) -> None:
    """Append one turn to durable conversation history (migration 0030).

    No-ops without a surface session: `session_messages.surface_session_id` is
    FK-bound, and a run outside any session has nothing to attach to. Fail-open:
    losing a history row must never take down a run that is otherwise
    succeeding — but a lock-exhaustion loss is logged at WARNING, because it is
    the one failure that silently costs the next turn its context.
    """
    if not session_key or not content:
        return
    try:
        from atlas_runtime import session_message_service  # noqa: PLC0415
    except Exception as exc:  # noqa: BLE001 — fail-open history
        logger.debug("session message persistence unavailable (%s): %s", role, exc)
        return
    try:
        session_message_service.append_message(
            conn, lock,
            surface_session_id=session_key,
            run_id=run_id,
            role=role,
            content=content,
            tool_call_id=tool_call_id,
            tool_name=tool_name,
            metadata=metadata,
        )
    except session_message_service.DatabaseBusyExhausted as exc:
        logger.warning(
            "session message persistence warning: %s",
            json.dumps(
                {
                    "event": "session_message_persistence_failed",
                    "reason": exc.reason,
                    "attempts": exc.attempts,
                    "role": role,
                    "run_id": run_id,
                    "surface_session_id": session_key,
                },
                separators=(",", ":"),
                sort_keys=True,
            ),
        )
    except Exception as exc:  # noqa: BLE001 — fail-open history
        logger.debug("session message persistence failed (%s): %s", role, exc)


__all__ = [
    "HISTORY_RUN_WINDOW",
    "load",
    "operator_message",
    "record",
    "resolve_session",
    "transcript",
    "with_history",
]
