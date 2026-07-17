"""ATLAS modular agent runtimes (P4).

An AgentRuntime executes a Mission's run and emits AuditEvents through the
shared audit bus, so every runtime produces an identical audit shape
(audit parity). Three runtimes ship:

  - NativeAtlasAgent  ("native")      — in-process / Hermes-foundation path.
  - ClaudeCodeAgent   ("claude_code") — Claude Agent SDK driven by the
    operator's LOCAL Claude Code subscription session (no API key).
  - CodexAgent        ("codex")       — the operator's LOCAL OpenAI Codex CLI
    (`codex exec --json`), whatever login that CLI is configured with.

Select a runtime by key via `get_agent(name)`; `known_agents()` lists keys.
"""
from __future__ import annotations

from atlas_runtime.agents.base import AgentRuntime, RunOutcome
from atlas_runtime.agents.registry import get_agent, known_agents

__all__ = ["AgentRuntime", "RunOutcome", "get_agent", "known_agents"]
