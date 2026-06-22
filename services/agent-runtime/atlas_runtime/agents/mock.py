"""MockAtlasAgent — deterministic, zero-credential harness stand-in.

Used by NativeAtlasAgent.execute() ONLY when no provider credentials are
configured at all (`api_key` is empty/None). A configured-but-wrong api_key
must never route here — see native.py's `if not api_key:` factory-selection
branch, which is the single gate preserving the Phase A4 honest-failure
contract (a real, misconfigured provider must fail honestly, not be silently
masked by a canned mock response).

Determinism is mandatory: no `datetime.now()`, no interpolation of
`user_message` into the response, no randomization. The same canned dict is
returned for every call so cockpit/CLI demos and tests are fully reproducible.
"""
from __future__ import annotations

from typing import Optional

_MOCK_RESPONSE = (
    "MOCK MODE — no live model configured. This is a deterministic canned "
    "response demonstrating the ATLAS run pipeline end-to-end without any "
    "provider credentials. Configure a provider via `atlas setup` to get "
    "real model output."
)


class MockAtlasAgent:
    """Deterministic stand-in harness satisfying the same call surface as the
    foundation AIAgent: `run_conversation(user_message, system_message=None) ->
    dict` shaped to match NativeAtlasAgent._map_result's expected keys."""

    name = "mock"

    def __init__(self, *, model: str = "", provider: Optional[str] = None) -> None:
        self._model = model
        self._provider = provider

    def run_conversation(self, user_message: str, system_message: Optional[str] = None) -> dict:
        return {
            "final_response": _MOCK_RESPONSE,
            "api_calls": 0,
            "completed": True,
            "failed": False,
            "error": None,
        }


def mock_factory(session_id: str, *, model: str = "", provider: Optional[str] = None) -> MockAtlasAgent:
    """Factory mirroring `_default_factory`'s keyword signature shape so
    `NativeAtlasAgent.execute()` can swap factories without changing the call
    site's calling convention. `max_iterations`/`base_url`/`api_key` are
    intentionally dropped — the mock needs neither."""
    return MockAtlasAgent(model=model, provider=provider)
