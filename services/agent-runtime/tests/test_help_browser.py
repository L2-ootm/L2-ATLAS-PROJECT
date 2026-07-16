"""Tests for the interactive `atlas help` command (help_browser.py).

Follows the same pattern as test_interactive_select.py: the raw key reader is
injected so the tab/list/search state machine is testable without a real
terminal, and `sys.stdin`/`sys.stdout` `.isatty()` are monkeypatched to force
the interactive branch (pytest's captured stdio isn't a TTY by default).
`_show_detail` is stubbed in most tests since it shells out to a second
`CliRunner` invocation and blocks on an extra keypress to dismiss — one
dedicated test exercises it directly.
"""
from __future__ import annotations

import typer

from atlas_runtime.cli import help_browser
from atlas_runtime.cli.help_browser import CommandEntry, _draw, _search, build_catalog, render_static, run_browser
from atlas_runtime.cli.main import app

_ROOT = typer.main.get_command(app)


def _force_tty(monkeypatch) -> None:
    monkeypatch.setattr("sys.stdin.isatty", lambda: True)
    monkeypatch.setattr("sys.stdout.isatty", lambda: True)


def _scripted_keys(keys):
    it = iter(keys)
    return lambda: next(it)


def test_draw_first_frame_has_no_cursor_up(capsys) -> None:
    import re

    # prev_line_count=0 means "nothing drawn yet" — must not move the cursor.
    n = _draw(["a", "b", "c"], 0)
    out = capsys.readouterr().out
    assert n == 3
    assert re.search(r"\x1b\[\d+A", out) is None


def test_draw_uses_previous_frames_line_count_not_the_new_ones(capsys) -> None:
    # Regression for the observed bug: switching from a 7-line tab to a
    # shorter 2-line tab (or vice versa) must move the cursor up by the
    # PREVIOUS frame's height, not the new frame's — using the new frame's
    # (shorter) count would undershoot and leave stale lines from the taller
    # previous frame on screen, which is exactly the duplicated-tab-bar bug
    # reported in production.
    n1 = _draw(["l1", "l2", "l3", "l4", "l5", "l6", "l7"], 0)
    assert n1 == 7
    capsys.readouterr()  # discard first frame's output

    n2 = _draw(["only-one-line"], n1)
    out = capsys.readouterr().out
    # Must move up by the OLD frame height (7), not the new one (1).
    assert "\x1b[7A" in out
    assert "\x1b[1A" not in out.split("\x1b[7A")[0]
    assert n2 == 1


def test_draw_clears_leftover_lines_when_frame_shrinks(capsys) -> None:
    _draw(["l1", "l2", "l3", "l4", "l5"], 0)
    capsys.readouterr()
    n2 = _draw(["l1", "l2"], 5)
    out = capsys.readouterr().out
    # 5 -> 2 lines: 3 leftover lines must be blanked, then the cursor moved
    # back up by those same 3 lines so the *next* draw's math stays correct.
    assert out.count("\x1b[2K\n") >= 3
    assert out.rstrip().endswith("\x1b[3A")
    assert n2 == 2


def test_draw_growing_frame_uses_old_smaller_count(capsys) -> None:
    _draw(["l1", "l2"], 0)
    capsys.readouterr()
    n2 = _draw(["l1", "l2", "l3", "l4", "l5"], 2)
    out = capsys.readouterr().out
    assert "\x1b[2A" in out
    assert n2 == 5


def test_build_catalog_covers_every_visible_top_level_command() -> None:
    tab_order, tabs = build_catalog(_ROOT)
    catalogued = {entry.name for label in tab_order for entry in tabs[label]}
    expected = {
        name
        for name, cmd in _ROOT.commands.items()
        if not getattr(cmd, "hidden", False) and name != "help"
    }
    assert catalogued == expected


def test_build_catalog_excludes_help_and_hidden_dev_commands() -> None:
    _, tabs = build_catalog(_ROOT)
    all_names = {entry.name for entries in tabs.values() for entry in entries}
    assert "help" not in all_names
    assert "dev-go-tui" not in all_names
    assert "dev-foundation-tui" not in all_names


def test_build_catalog_uncategorized_command_lands_in_other_tab() -> None:
    class _FakeCmd:
        hidden = False

        def get_short_help_str(self, limit=200):
            return "a made-up command"

    class _FakeRoot:
        commands = {"totally-new-thing": _FakeCmd()}

    tab_order, tabs = build_catalog(_FakeRoot())
    assert "Other" in tab_order
    assert [e.name for e in tabs["Other"]] == ["totally-new-thing"]


def test_search_matches_name_or_summary_case_insensitively() -> None:
    tabs = {
        "A": [CommandEntry("mission", "Create, run, retry missions"), CommandEntry("db", "Database lifecycle")],
    }
    assert [e.name for e in _search(tabs, "MISSION")] == ["mission"]
    assert [e.name for e in _search(tabs, "database")] == ["db"]
    assert _search(tabs, "") == []
    assert _search(tabs, "nope-nothing-matches") == []


def test_search_deduplicates_across_tabs() -> None:
    shared = CommandEntry("provider", "Wire and inspect AI providers")
    tabs = {"A": [shared], "B": [shared]}
    assert [e.name for e in _search(tabs, "provider")] == ["provider"]


def test_render_static_lists_every_command(capsys) -> None:
    tab_order, tabs = build_catalog(_ROOT)
    render_static(tab_order, tabs)
    out = capsys.readouterr().out
    assert "Getting Started" in out
    assert "atlas mission" in out
    assert "atlas doctor" in out


def test_run_browser_non_tty_falls_back_to_static(capsys) -> None:
    # No isatty monkeypatch — pytest's captured stdio isn't a real TTY.
    run_browser(app, _ROOT)
    out = capsys.readouterr().out
    assert "Getting Started" in out
    assert "atlas mission" in out


def test_interactive_tab_navigation_with_number_key(monkeypatch) -> None:
    _force_tty(monkeypatch)
    seen = {}
    monkeypatch.setattr(help_browser, "_show_detail", lambda app, name: seen.setdefault("name", name))
    # "2" jumps to tab 2 (Missions & Runs), enter on the first entry ("mission").
    run_browser(app, _ROOT, read_key=_scripted_keys(["2", "enter", "q"]))
    assert seen["name"] == "mission"


def test_interactive_left_right_wraps_tabs(monkeypatch) -> None:
    _force_tty(monkeypatch)
    seen = {}
    monkeypatch.setattr(help_browser, "_show_detail", lambda app, name: seen.setdefault("name", name))
    # From tab 0, "left" wraps to the last tab ("Dev / Internal": foundation only).
    run_browser(app, _ROOT, read_key=_scripted_keys(["left", "enter", "q"]))
    assert seen["name"] == "foundation"


def test_interactive_down_moves_cursor_within_tab(monkeypatch) -> None:
    _force_tty(monkeypatch)
    seen = {}
    monkeypatch.setattr(help_browser, "_show_detail", lambda app, name: seen.setdefault("name", name))
    # Tab 0 (Getting Started) starts with "setup"; "down" moves to "doctor".
    run_browser(app, _ROOT, read_key=_scripted_keys(["down", "enter", "q"]))
    assert seen["name"] == "doctor"


def test_interactive_search_filters_and_selects(monkeypatch) -> None:
    _force_tty(monkeypatch)
    seen = {}
    monkeypatch.setattr(help_browser, "_show_detail", lambda app, name: seen.setdefault("name", name))
    # '/' enters search, typing "wiki" filters to the wiki command, enter drills
    # in; "quit" (Esc) then leaves search mode (still in the browser) before
    # "q" exits it — "q" while inside the search box would just be text.
    run_browser(app, _ROOT, read_key=_scripted_keys(["/", "w", "i", "k", "i", "enter", "quit", "q"]))
    assert seen["name"] == "wiki"


def test_interactive_search_backspace_and_quit_returns_to_browse(monkeypatch) -> None:
    _force_tty(monkeypatch)
    monkeypatch.setattr(help_browser, "_show_detail", lambda app, name: None)
    # Enter search, type "zz" (no matches), backspace once, quit search (back to
    # browse), then quit the whole browser — should not raise.
    run_browser(app, _ROOT, read_key=_scripted_keys(["/", "z", "z", "backspace", "quit", "q"]))


def test_show_detail_invokes_real_help(monkeypatch, capsys) -> None:
    monkeypatch.setattr(help_browser, "_read_key", lambda: "enter")
    help_browser._show_detail(app, "version")
    out = capsys.readouterr().out
    assert "atlas version --help" in out
    assert "Print the ATLAS runtime version" in out
