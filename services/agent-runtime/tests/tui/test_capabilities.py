"""Terminal capability probing for cross-terminal rendering (TUI-10).

RED until atlas_runtime.tui.capabilities exists (Wave 1+).
"""
from __future__ import annotations

from atlas_runtime.tui.capabilities import probe_capabilities


def test_no_color_env_forces_no_color(monkeypatch):
    """TUI-10: NO_COLOR=1 must force no_color regardless of terminal type."""
    monkeypatch.setenv("NO_COLOR", "1")
    caps = probe_capabilities()
    assert caps.no_color is True


def test_legacy_windows_falls_back_to_ascii_box(monkeypatch):
    """TUI-10: legacy Windows console (no ANSI/Unicode) selects the ASCII box style."""
    monkeypatch.setattr(
        "atlas_runtime.tui.capabilities._is_legacy_windows_console", lambda: True
    )
    caps = probe_capabilities()
    assert caps.box_style == "ascii"


def test_narrow_width_under_80_cols_selected(monkeypatch):
    """TUI-10: terminal width under 80 columns selects the narrow layout."""
    monkeypatch.setattr(
        "atlas_runtime.tui.capabilities._detect_width", lambda: 60
    )
    caps = probe_capabilities()
    assert caps.width < 80
    assert caps.layout == "narrow"
