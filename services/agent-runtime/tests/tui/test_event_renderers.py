"""Per-EventKind renderers: tool/result/diff/task/subagent/retry/retrieval/cancel (TUI-05).

RED until atlas_runtime.tui.transcript exists (Wave 1+).
"""
from __future__ import annotations

import typing

import pytest

from atlas_core.schemas.surface_session import EventKind, SurfaceEvent
from atlas_runtime.tui.transcript import render_event


def _event_for_kind(kind: str) -> SurfaceEvent:
    return SurfaceEvent(
        session_id="sess-1",
        seq=1,
        kind=kind,  # type: ignore[arg-type]
        run_id=None,
        occurred_at="2026-06-27T00:00:00+00:00",
        payload_json="{}",
    )


@pytest.mark.parametrize("kind", list(typing.get_args(EventKind)))
def test_every_event_kind_has_a_renderer(kind: str):
    """TUI-05: every normalized EventKind maps to a non-empty Rich renderable, no exception."""
    event = _event_for_kind(kind)
    renderable = render_event(event)
    assert renderable is not None
