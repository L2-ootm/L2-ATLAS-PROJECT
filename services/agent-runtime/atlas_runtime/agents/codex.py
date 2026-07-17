"""CodexAgent — OpenAI Codex CLI on the operator's LOCAL session.

Drives the installed `codex` CLI in headless mode (`codex exec --json`) so the
run executes on the operator's local Codex login (ChatGPT subscription or API
key — whatever their Codex CLI is configured with). ATLAS never handles the
credential. The CLI's experimental JSONL event stream is mapped onto the ATLAS
AuditEvent bus for audit parity with the other runtimes:

  item agent_message            -> llm_call   (assistant text)
  item command_execution /
       mcp_tool_call /
       file_change / web_search -> tool_call + tool_completed/tool_failed
  turn.completed                -> llm_call   (usage receipt)
  turn.failed / error           -> failure

The subprocess inherits the CLI worker's cwd, which the dispatch path already
chdirs to the mission's bound project root, so Codex works the operator's
selected workspace exactly like the other runtimes.

The CLI is an OPTIONAL external dependency, resolved at execute() time, so
installs without Codex stay lean. The event source (`runner_fn`) is injectable
so unit tests run without the CLI or a live session. Mapping is duck-typed and
tolerant of unknown event/item types: Codex's JSON stream is documented as
experimental, so unknown shapes are skipped, never fatal.
"""
from __future__ import annotations

import json
import logging
import os
import shutil
import sqlite3
import subprocess
import threading
from typing import Any, Callable, Iterable, Iterator, Optional

from atlas_runtime.agents.base import AgentRuntime, RunOutcome
from atlas_runtime.audit_service import emit

logger = logging.getLogger(__name__)

_SUMMARY_CAP = 2000
_OUTPUT_CAP = 2000

# Item types that represent an observable tool action (name -> display tool name).
_TOOL_ITEM_TYPES = {
    "command_execution": "shell",
    "mcp_tool_call": "mcp",
    "file_change": "apply_patch",
    "web_search": "web_search",
}


def _resolve_binary() -> str:
    """Locate the codex CLI. ATLAS_CODEX_BIN overrides PATH lookup."""
    override = os.environ.get("ATLAS_CODEX_BIN", "").strip()
    if override:
        return override
    found = shutil.which("codex")
    if not found:
        raise RuntimeError(
            "codex CLI not found on PATH; install it (npm install -g @openai/codex) "
            "and sign in (codex login) to use the codex agent runtime"
        )
    return found


def _default_runner(prompt: str, cancel_token: Optional[threading.Event]) -> Iterator[dict]:
    """Spawn `codex exec --json` and yield parsed JSONL events.

    Cancellation: checked between lines; a set token terminates the child and
    ends the stream (the caller records the cancelled outcome).
    """
    binary = _resolve_binary()
    cmd = [binary, "exec", "--json", "--skip-git-repo-check", prompt]
    proc = subprocess.Popen(  # noqa: S603 - operator-selected local CLI
        cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    try:
        assert proc.stdout is not None
        for line in proc.stdout:
            if cancel_token is not None and cancel_token.is_set():
                proc.terminate()
                return
            line = line.strip()
            if not line or not line.startswith("{"):
                continue
            try:
                event = json.loads(line)
            except json.JSONDecodeError:
                continue
            if isinstance(event, dict):
                yield event
        proc.wait(timeout=30)
        if proc.returncode not in (0, None):
            stderr_tail = ""
            if proc.stderr is not None:
                stderr_tail = (proc.stderr.read() or "")[-_OUTPUT_CAP:]
            raise RuntimeError(
                f"codex exec exited with code {proc.returncode}: {stderr_tail.strip()}"
            )
    finally:
        if proc.poll() is None:
            proc.terminate()


class CodexAgent(AgentRuntime):
    name = "codex"

    def __init__(
        self,
        runner_fn: Optional[Callable[[str, Optional[threading.Event]], Iterable[dict]]] = None,
    ) -> None:
        self._runner_fn = runner_fn

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
        if cancel_token is not None and cancel_token.is_set():
            self._safe_emit(
                conn, lock, run_id, event_type="run_cancelled",
                data={"runtime": "codex", "stop_reason": "cancelled"},
            )
            return RunOutcome(
                status="failed", summary="cancelled before codex start", stop_reason="cancelled"
            )
        runner = self._runner_fn or _default_runner
        summary: list[str] = []
        state = {"status": "succeeded"}
        try:
            for event in runner(prompt, cancel_token):
                self._map_event(conn, lock, run_id, event, summary, state)
                if cancel_token is not None and cancel_token.is_set():
                    self._safe_emit(
                        conn, lock, run_id, event_type="run_cancelled",
                        data={"runtime": "codex", "stop_reason": "cancelled"},
                    )
                    return RunOutcome(
                        status="failed",
                        summary="".join(summary).strip()[:_SUMMARY_CAP],
                        stop_reason="cancelled",
                    )
        except Exception as exc:  # fail-safe: report as a failed run, never crash
            logger.warning("CodexAgent execute failed: %s", exc)
            self._safe_emit(
                conn, lock, run_id, event_type="failure",
                data={"runtime": "codex", "error": str(exc)},
            )
            return RunOutcome(status="failed", summary=f"codex error: {exc}"[:_SUMMARY_CAP])
        return RunOutcome(status=state["status"], summary="\n".join(summary).strip()[:_SUMMARY_CAP])

    # -- internal ----------------------------------------------------------

    def _map_event(
        self,
        conn: sqlite3.Connection,
        lock: threading.Lock,
        run_id: str,
        event: dict,
        summary: list[str],
        state: dict[str, str],
    ) -> None:
        etype = str(event.get("type", ""))
        if etype in ("item.started", "item.completed", "item.updated"):
            item = event.get("item")
            if isinstance(item, dict):
                self._map_item(conn, lock, run_id, etype, item, summary)
        elif etype == "turn.completed":
            self._safe_emit(
                conn, lock, run_id, event_type="llm_call",
                data={
                    "runtime": "codex",
                    "result": True,
                    "is_error": False,
                    "usage": event.get("usage"),
                },
            )
        elif etype in ("turn.failed", "error"):
            state["status"] = "failed"
            error = event.get("error")
            message = None
            if isinstance(error, dict):
                message = error.get("message")
            message = message or event.get("message") or etype
            self._safe_emit(
                conn, lock, run_id, event_type="failure",
                data={"runtime": "codex", "error": str(message)[:_OUTPUT_CAP]},
            )

    def _map_item(
        self,
        conn: sqlite3.Connection,
        lock: threading.Lock,
        run_id: str,
        etype: str,
        item: dict,
        summary: list[str],
    ) -> None:
        item_type = str(item.get("item_type") or item.get("type") or "")
        item_id = item.get("id")
        if item_type == "agent_message":
            if etype != "item.completed":
                return  # streaming updates would duplicate the completed text
            text = str(item.get("text") or "")
            if text:
                summary.append(text)
                self._safe_emit(
                    conn, lock, run_id, event_type="llm_call",
                    data={"runtime": "codex", "text": text},
                )
        elif item_type == "reasoning":
            if etype != "item.completed":
                return
            text = str(item.get("text") or "")
            if text:
                self._safe_emit(
                    conn, lock, run_id, event_type="llm_call",
                    data={"runtime": "codex", "reasoning": True, "text": text[:_OUTPUT_CAP]},
                )
        elif item_type in _TOOL_ITEM_TYPES:
            tool_name = _TOOL_ITEM_TYPES[item_type]
            if item_type == "mcp_tool_call":
                server = item.get("server")
                tool = item.get("tool")
                if server or tool:
                    tool_name = f"{server or 'mcp'}.{tool or 'call'}"
            if etype == "item.started":
                self._safe_emit(
                    conn, lock, run_id, event_type="tool_call",
                    tool_name=tool_name,
                    tool_call_id=item_id,
                    data={
                        "runtime": "codex",
                        "tool_name": tool_name,
                        "tool_call_id": item_id,
                        "input": self._item_input(item_type, item),
                    },
                )
            elif etype == "item.completed":
                status = str(item.get("status") or "")
                exit_code = item.get("exit_code")
                failed = status == "failed" or (
                    isinstance(exit_code, int) and exit_code != 0
                )
                self._safe_emit(
                    conn, lock, run_id,
                    event_type="tool_failed" if failed else "tool_completed",
                    tool_call_id=item_id,
                    data={
                        "runtime": "codex",
                        "tool_call_id": item_id,
                        "is_error": failed,
                        "summary": self._item_output(item_type, item),
                    },
                )
        # unknown item types (todo_list, ...) are intentionally skipped

    @staticmethod
    def _item_input(item_type: str, item: dict) -> Any:
        if item_type == "command_execution":
            return {"command": item.get("command")}
        if item_type == "mcp_tool_call":
            return {"server": item.get("server"), "tool": item.get("tool")}
        if item_type == "file_change":
            return {"changes": item.get("changes")}
        if item_type == "web_search":
            return {"query": item.get("query")}
        return None

    @staticmethod
    def _item_output(item_type: str, item: dict) -> str:
        if item_type == "command_execution":
            out = str(item.get("aggregated_output") or "")
            code = item.get("exit_code")
            tail = f" (exit {code})" if isinstance(code, int) else ""
            return (out[:_OUTPUT_CAP] + tail).strip()
        if item_type == "file_change":
            changes = item.get("changes")
            if isinstance(changes, list):
                parts = []
                for change in changes:
                    if isinstance(change, dict):
                        parts.append(f"{change.get('kind', 'edit')} {change.get('path', '')}")
                return "; ".join(parts)[:_OUTPUT_CAP]
        return str(item.get("status") or "done")[:_OUTPUT_CAP]

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
            logger.warning("CodexAgent audit emit failed: %s", exc)
