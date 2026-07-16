"""Tests for the dependency-free checkbox prompt used by `atlas up`.

The raw-terminal key reader (`_read_key`) is injected via `multi_select`'s
`read_key` parameter so the selection state machine is testable without a
real TTY; `sys.stdin`/`sys.stdout` `.isatty()` are monkeypatched to force the
interactive branch (pytest's captured stdio is not a TTY by default, so the
un-patched code path already exercises the non-interactive fallback).
"""
from __future__ import annotations

import io

import pytest

from atlas_runtime.cli.interactive_select import (
    SelectionCancelled,
    SelectItem,
    _fallback_prompt,
    multi_select,
)


def _force_tty(monkeypatch) -> None:
    monkeypatch.setattr("sys.stdin.isatty", lambda: True)
    monkeypatch.setattr("sys.stdout.isatty", lambda: True)


def _scripted_keys(keys):
    it = iter(keys)
    return lambda: next(it)


def test_interactive_toggle_and_confirm(monkeypatch) -> None:
    _force_tty(monkeypatch)
    items = [SelectItem("a", "Service A"), SelectItem("b", "Service B")]
    # down, space (select B), enter
    result = multi_select(items, read_key=_scripted_keys(["down", "space", "enter"]))
    assert result == ["b"]


def test_interactive_default_checked_included(monkeypatch) -> None:
    _force_tty(monkeypatch)
    items = [SelectItem("a", "Service A", checked=True), SelectItem("b", "Service B")]
    result = multi_select(items, read_key=_scripted_keys(["enter"]))
    assert result == ["a"]


def test_interactive_locked_item_not_toggleable(monkeypatch) -> None:
    _force_tty(monkeypatch)
    items = [SelectItem("a", "Service A", locked=True), SelectItem("b", "Service B")]
    # cursor starts on the first unlocked item (b); space toggles it, then
    # move up and try (harmlessly) to toggle the locked item too.
    result = multi_select(items, read_key=_scripted_keys(["space", "up", "space", "enter"]))
    assert result == ["a", "b"]


def test_interactive_untoggle_default_checked(monkeypatch) -> None:
    _force_tty(monkeypatch)
    items = [SelectItem("a", "Service A", checked=True)]
    result = multi_select(items, read_key=_scripted_keys(["space", "enter"]))
    assert result == []


def test_interactive_cancel_raises(monkeypatch) -> None:
    _force_tty(monkeypatch)
    items = [SelectItem("a", "Service A")]
    with pytest.raises(SelectionCancelled):
        multi_select(items, read_key=_scripted_keys(["quit"]))


def test_interactive_wraps_navigation(monkeypatch) -> None:
    _force_tty(monkeypatch)
    items = [SelectItem("a", "A"), SelectItem("b", "B")]
    # From cursor 0, "up" should wrap to the last item (b), then toggle it.
    result = multi_select(items, read_key=_scripted_keys(["up", "space", "enter"]))
    assert result == ["b"]


def test_fallback_all(monkeypatch) -> None:
    items = [SelectItem("a", "A"), SelectItem("b", "B", locked=True)]
    monkeypatch.setattr("typer.prompt", lambda *a, **k: "all")
    assert set(_fallback_prompt(items, "")) == {"a", "b"}


def test_fallback_specific_numbers(monkeypatch) -> None:
    items = [SelectItem("a", "A"), SelectItem("b", "B"), SelectItem("c", "C")]
    monkeypatch.setattr("typer.prompt", lambda *a, **k: "2")
    assert _fallback_prompt(items, "") == ["b"]


def test_fallback_blank_keeps_only_checked_and_locked(monkeypatch) -> None:
    items = [SelectItem("a", "A", checked=True), SelectItem("b", "B"), SelectItem("c", "C", locked=True)]
    monkeypatch.setattr("typer.prompt", lambda *a, **k: "")
    assert set(_fallback_prompt(items, "")) == {"a", "c"}


def test_fallback_all_locked_skips_prompt(monkeypatch) -> None:
    items = [SelectItem("a", "A", locked=True)]
    called = []
    monkeypatch.setattr("typer.prompt", lambda *a, **k: called.append(1) or "all")
    assert _fallback_prompt(items, "") == ["a"]
    assert not called


def test_multi_select_uses_fallback_when_not_tty() -> None:
    # No monkeypatch of isatty here — under pytest, captured stdio is not a
    # real TTY, so this exercises the auto-fallback branch directly.
    items = [SelectItem("a", "A", checked=True)]
    import typer as _typer

    orig_prompt = _typer.prompt
    _typer.prompt = lambda *a, **k: "all"
    try:
        assert multi_select(items) == ["a"]
    finally:
        _typer.prompt = orig_prompt
