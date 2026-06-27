"""Shared fixtures for tests/tui/* (Phase 10.6 ATLAS Terminal Workbench, Wave 0).

Depends on the top-level fixtures defined in services/agent-runtime/tests/conftest.py
via pytest's automatic parent-conftest fixture discovery (no explicit import needed):
``db``, ``surface_session``, ``make_active_session``, ``seed_pending_approval``,
``register_test_channel``. This module intentionally builds NO new DB harness —
every TUI test in this package reuses the in-memory, all-migrations-applied ``db``
fixture. Never drive the live ``atlas`` CLI against ``~/.atlas/atlas.db`` from here.
"""
from __future__ import annotations

import io
from typing import Callable, Optional

import pytest
from rich.console import Console


@pytest.fixture(name="forced_console")
def forced_console_fixture() -> Callable[..., Console]:
    """Return a factory building a deterministic ``rich.console.Console`` for tests.

    Shared by every rendering test in this package so width/no-color/legacy-windows
    (ASCII box) assertions are consistent across test_header.py, test_event_renderers.py,
    etc. Defaults to an ``io.StringIO()`` sink so nothing reaches the real terminal.
    """

    def _make_console(
        *,
        no_color: bool = False,
        width: Optional[int] = None,
        legacy_windows: bool = False,
        file: Optional[io.StringIO] = None,
    ) -> Console:
        return Console(
            no_color=no_color,
            width=width,
            legacy_windows=legacy_windows,
            file=file or io.StringIO(),
        )

    return _make_console
