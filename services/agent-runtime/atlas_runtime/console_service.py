"""Console chat bridge for the ATLAS cockpit.

This is intentionally separate from mission runs: a console chat turn may be
exploratory and folder-bound without becoming a mission lifecycle event. Mission
runs remain the audited execution contract.
"""
from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Any, Callable, Literal

AgentName = Literal["native", "claude_code"]

VALID_CONSOLE_AGENTS: tuple[AgentName, ...] = ("native", "claude_code")


def _resolve_cwd(cwd: str | None) -> Path | None:
    if cwd is None or not cwd.strip():
        return None
    path = Path(cwd).expanduser()
    if not path.exists():
        raise ValueError(f"folder does not exist: {cwd}")
    if not path.is_dir():
        raise ValueError(f"path is not a folder: {cwd}")
    return path.resolve()


def _native_response(prompt: str, cwd: Path | None) -> dict[str, Any]:
    where = str(cwd) if cwd else "default working directory"
    text = (
        f"Native console mode received the request in {where}. "
        "Switch to Claude Code mode to execute agentic folder-aware work."
    )
    return {
        "status": "succeeded",
        "agent": "native",
        "cwd": str(cwd) if cwd else None,
        "text": text,
        "events": [
            {
                "type": "text",
                "text": text,
            },
            {
                "type": "receipt",
                "prompt": prompt,
            },
        ],
    }


def run_chat(
    *,
    prompt: str,
    agent: str = "native",
    cwd: str | None = None,
    query_fn: Callable[..., Any] | None = None,
    options_factory: Callable[[Path | None], Any] | None = None,
) -> dict[str, Any]:
    """Run one console chat turn and return a JSON-serializable result."""
    clean_prompt = prompt.strip()
    if not clean_prompt:
        raise ValueError("prompt must be non-empty")
    if agent not in VALID_CONSOLE_AGENTS:
        raise ValueError("agent must be 'native' or 'claude_code'")
    resolved = _resolve_cwd(cwd)
    if agent == "native":
        return _native_response(clean_prompt, resolved)
    return _run_claude_code_chat(
        prompt=clean_prompt,
        cwd=resolved,
        query_fn=query_fn,
        options_factory=options_factory,
    )


def _run_claude_code_chat(
    *,
    prompt: str,
    cwd: Path | None,
    query_fn: Callable[..., Any] | None,
    options_factory: Callable[[Path | None], Any] | None,
) -> dict[str, Any]:
    try:
        if query_fn is None:
            from claude_agent_sdk import ClaudeAgentOptions, query  # noqa: PLC0415

            query_fn = query

            def _options_factory(path: Path | None) -> Any:
                return ClaudeAgentOptions(
                    cwd=path,
                    permission_mode="dontAsk",
                    allowed_tools=["Read", "Grep", "Glob", "LS", "Ls"],
                    max_turns=12,
                    system_prompt={
                        "type": "preset",
                        "preset": "claude_code",
                        "append": (
                            "You are running inside the ATLAS console. Keep replies concise. "
                            "State what you inspected, what you changed, and what remains. "
                            "Do not modify files unless the operator explicitly requests it."
                        ),
                    },
                    setting_sources=["user", "project", "local"],
                    env={
                        "API_TIMEOUT_MS": "120000",
                        "CLAUDE_CODE_MAX_RETRIES": "1",
                    },
                )

            options_factory = _options_factory
        elif options_factory is None:
            options_factory = lambda _path: None

        events: list[dict[str, Any]] = []
        text_parts: list[str] = []
        state = {"status": "succeeded"}

        async def _drive() -> None:
            options = options_factory(cwd)
            async for msg in query_fn(prompt=prompt, options=options):
                _map_sdk_message(msg, events, text_parts, state)

        asyncio.run(_drive())
        text = "".join(text_parts).strip()
        if not text:
            text = "Claude Code completed without assistant text."
        return {
            "status": state["status"],
            "agent": "claude_code",
            "cwd": str(cwd) if cwd else None,
            "text": text,
            "events": events,
        }
    except ImportError:
        return {
            "status": "failed",
            "agent": "claude_code",
            "cwd": str(cwd) if cwd else None,
            "text": "claude-agent-sdk is not installed. Install atlas-runtime[claude] to enable Claude Code console mode.",
            "events": [{"type": "failure", "error": "claude-agent-sdk is not installed"}],
        }
    except Exception as exc:
        return {
            "status": "failed",
            "agent": "claude_code",
            "cwd": str(cwd) if cwd else None,
            "text": f"claude_code error: {exc}",
            "events": [{"type": "failure", "error": str(exc)}],
        }


def _map_sdk_message(
    msg: Any,
    events: list[dict[str, Any]],
    text_parts: list[str],
    state: dict[str, str],
) -> None:
    kind = type(msg).__name__
    if kind == "AssistantMessage":
        for block in getattr(msg, "content", []) or []:
            bkind = type(block).__name__
            if bkind == "TextBlock":
                text = getattr(block, "text", "") or ""
                if text:
                    text_parts.append(text)
                    events.append({"type": "text", "text": text})
            elif bkind == "ToolUseBlock":
                events.append(
                    {
                        "type": "tool_call",
                        "tool_name": getattr(block, "name", None),
                        "tool_call_id": getattr(block, "id", None),
                        "input": getattr(block, "input", None),
                    }
                )
            elif bkind == "ToolResultBlock":
                events.append(
                    {
                        "type": "tool_result",
                        "tool_call_id": getattr(block, "tool_use_id", None),
                        "content": getattr(block, "content", None),
                    }
                )
    elif kind == "UserMessage":
        # The SDK returns tool results as ToolResultBlocks inside a UserMessage
        # that follows the assistant's ToolUseBlock — not in the AssistantMessage.
        content = getattr(msg, "content", None)
        if isinstance(content, list):
            for block in content:
                if type(block).__name__ == "ToolResultBlock":
                    events.append(
                        {
                            "type": "tool_result",
                            "tool_call_id": getattr(block, "tool_use_id", None),
                            "content": getattr(block, "content", None),
                        }
                    )
    elif kind == "ResultMessage":
        is_error = bool(getattr(msg, "is_error", False))
        if is_error:
            state["status"] = "failed"
        result = getattr(msg, "result", None)
        if result and not text_parts:
            text_parts.append(str(result))
        events.append(
            {
                "type": "result",
                "is_error": is_error,
                "subtype": getattr(msg, "subtype", None),
                "num_turns": getattr(msg, "num_turns", None),
                "total_cost_usd": getattr(msg, "total_cost_usd", None),
                "usage": getattr(msg, "usage", None),
            }
        )
    elif kind == "SystemMessage":
        events.append(
            {
                "type": "system",
                "subtype": getattr(msg, "subtype", None),
                "session_id": getattr(msg, "session_id", None),
            }
        )
