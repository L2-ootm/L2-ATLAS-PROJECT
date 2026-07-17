"""AgentRuntime registry — resolve a runtime by its key (P4)."""
from __future__ import annotations

from atlas_runtime.agents.base import AgentRuntime
from atlas_runtime.agents.claude_code import ClaudeCodeAgent
from atlas_runtime.agents.codex import CodexAgent
from atlas_runtime.agents.native import NativeAtlasAgent

_REGISTRY: dict[str, type[AgentRuntime]] = {
    NativeAtlasAgent.name: NativeAtlasAgent,
    ClaudeCodeAgent.name: ClaudeCodeAgent,
    CodexAgent.name: CodexAgent,
}


def get_agent(name: str) -> AgentRuntime:
    """Instantiate the AgentRuntime registered under `name`.

    Raises:
        ValueError: if `name` is not a known runtime key.
    """
    try:
        cls = _REGISTRY[name]
    except KeyError:
        raise ValueError(
            f"Unknown agent runtime {name!r}. Known: {known_agents()}"
        ) from None
    return cls()


def known_agents() -> list[str]:
    """Sorted list of registered runtime keys."""
    return sorted(_REGISTRY)
