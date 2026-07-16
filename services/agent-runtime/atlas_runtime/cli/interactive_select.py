"""Dependency-free space/enter checkbox prompt for the CLI (`atlas up`).

Stdlib only (`msvcrt` on Windows, `termios`/`tty` on POSIX) — no questionary/
InquirerPy dependency for a single prompt. Falls back to a numbered
comma-list `typer.prompt` when stdio isn't a real TTY (tests, CI, piped
input), matching the existing `_prompt_workspace_scope` TTY-gating pattern in
`cli/main.py`.

Key-reading is isolated in `_read_key()` so the selection state machine
(`multi_select`) can be unit-tested by monkeypatching it with a scripted key
sequence, without a real terminal.
"""
from __future__ import annotations

import os
import sys
from dataclasses import dataclass


class SelectionCancelled(Exception):
    """Raised when the operator quits (q/Esc/Ctrl-C) instead of confirming."""


@dataclass
class SelectItem:
    key: str
    label: str
    checked: bool = False
    locked: bool = False  # already satisfied (e.g. already running) — always included, not toggleable


def _read_key() -> str:
    """Blocking single-keypress read.

    Returns one of 'up'/'down'/'left'/'right'/'space'/'enter'/'backspace'/
    'quit' for recognized control keys, or the raw decoded character
    otherwise (so callers doing text entry, like a search box, can consume
    plain letters — including 'q' — as data). 'quit' is reserved for Ctrl-C
    and Esc only; a bare 'q' is deliberately NOT treated as quit here since
    that would swallow it in any text-entry caller. Callers with no text
    entry (like the checkbox picker) can just also treat a literal "q"/"Q"
    key as cancel themselves.
    """
    if os.name == "nt":
        import msvcrt

        ch = msvcrt.getch()
        if ch in (b"\x00", b"\xe0"):
            ch2 = msvcrt.getch()
            return {b"H": "up", b"P": "down", b"K": "left", b"M": "right"}.get(ch2, "")
        if ch == b"\r":
            return "enter"
        if ch == b" ":
            return "space"
        if ch in (b"\x08", b"\x7f"):
            return "backspace"
        if ch in (b"\x03", b"\x1b"):
            return "quit"
        try:
            return ch.decode("utf-8", "ignore")
        except Exception:
            return ""

    import select
    import termios
    import tty

    fd = sys.stdin.fileno()
    old = termios.tcgetattr(fd)
    try:
        tty.setraw(fd)
        ch = sys.stdin.read(1)
        if ch == "\x1b":
            # Distinguish a bare Esc from an arrow-key escape sequence (ESC [ A/B/C/D)
            # by a short non-blocking wait for the rest of the sequence.
            if select.select([fd], [], [], 0.01)[0]:
                rest = os.read(fd, 2).decode("utf-8", "ignore")
                if rest == "[A":
                    return "up"
                if rest == "[B":
                    return "down"
                if rest == "[C":
                    return "right"
                if rest == "[D":
                    return "left"
            return "quit"
        if ch in ("\r", "\n"):
            return "enter"
        if ch == " ":
            return "space"
        if ch in ("\x7f", "\x08"):
            return "backspace"
        if ch == "\x03":
            return "quit"
        return ch
    finally:
        termios.tcsetattr(fd, termios.TCSADRAIN, old)


def _render_lines(items: list[SelectItem], selected: set[str], cursor: int, title: str) -> list[str]:
    lines = []
    if title:
        lines.append(title)
    for i, it in enumerate(items):
        box = "[x]" if it.key in selected else "[ ]"
        pointer = ">" if i == cursor else " "
        suffix = " (already running)" if it.locked else ""
        lines.append(f"{pointer} {box} {it.label}{suffix}")
    lines.append("(up/down: move, space: toggle, enter: confirm, q: cancel)")
    return lines


def _draw(lines: list[str], redraw: bool) -> None:
    if redraw:
        sys.stdout.write(f"\x1b[{len(lines)}A")
    for line in lines:
        sys.stdout.write("\x1b[2K" + line + "\n")
    sys.stdout.flush()


def _fallback_prompt(items: list[SelectItem], title: str) -> list[str]:
    import typer

    selected = {it.key for it in items if it.checked or it.locked}
    unlocked = [it for it in items if not it.locked]
    if not unlocked:
        return sorted(selected)
    if title:
        typer.echo(title)
    for i, it in enumerate(unlocked, start=1):
        mark = "x" if it.key in selected else " "
        typer.echo(f"  {i}) [{mark}] {it.label}")
    raw = typer.prompt(
        "Start which (comma-separated numbers, 'all', or blank for none)", default="all"
    ).strip()
    if raw.lower() == "all":
        selected |= {it.key for it in unlocked}
    elif raw:
        for tok in raw.split(","):
            tok = tok.strip()
            if tok.isdigit() and 1 <= int(tok) <= len(unlocked):
                selected.add(unlocked[int(tok) - 1].key)
    return [it.key for it in items if it.key in selected]


def multi_select(
    items: list[SelectItem], title: str = "", read_key=_read_key
) -> list[str]:
    """Interactive space/enter checkbox prompt over `items`.

    Returns the selected keys (locked items are always included). Raises
    `SelectionCancelled` if the operator quits without confirming. Falls back
    to a non-interactive numbered prompt when stdio isn't a real TTY.
    """
    if not items:
        return []
    if not (sys.stdin.isatty() and sys.stdout.isatty()):
        return _fallback_prompt(items, title)

    cursor = next((i for i, it in enumerate(items) if not it.locked), 0)
    selected = {it.key for it in items if it.checked or it.locked}

    _draw(_render_lines(items, selected, cursor, title), redraw=False)
    while True:
        key = read_key()
        if key == "up":
            cursor = (cursor - 1) % len(items)
        elif key == "down":
            cursor = (cursor + 1) % len(items)
        elif key == "space":
            it = items[cursor]
            if not it.locked:
                if it.key in selected:
                    selected.discard(it.key)
                else:
                    selected.add(it.key)
        elif key == "enter":
            _draw(_render_lines(items, selected, cursor, title), redraw=True)
            return [it.key for it in items if it.key in selected]
        elif key in ("quit", "q", "Q"):
            _draw(_render_lines(items, selected, cursor, title), redraw=True)
            raise SelectionCancelled()
        _draw(_render_lines(items, selected, cursor, title), redraw=True)
