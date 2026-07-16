"""Interactive `atlas help` — a dependency-free, tabbed command browser.

Same doctrine as `interactive_select.py`: stdlib-only raw-terminal I/O
(reuses its `_read_key`), falls back to a static categorized listing when
stdio isn't a real TTY. The command catalog is built by introspecting the
live typer/click command tree (`typer.main.get_command(app)`) rather than a
hand-duplicated list, so it can't silently drift out of sync with the CLI —
only the *category* a command lands in is manually curated (`_CATEGORIES`);
anything not explicitly placed falls into a trailing "Other" tab instead of
being dropped, so a newly added command is always reachable even before
someone files it under a category.

Detail view reuses `typer.testing.CliRunner` to invoke the real `--help`
for a selected command — this is deliberate: constructing a bare
`click.Context` by hand renders some option defaults incorrectly (a
click/typer quirk outside the normal `main()` invocation path), while
`CliRunner.invoke` goes through the exact same code path a user's terminal
would, guaranteeing byte-identical output.
"""
from __future__ import annotations

import shutil
import sys
from dataclasses import dataclass

from atlas_runtime.cli.interactive_select import _read_key

# (tab label, top-level command names in that tab, in display order).
# Names not listed here still show up, grouped under a trailing "Other" tab.
_CATEGORIES: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("Getting Started", ("setup", "doctor", "version", "up", "down", "tui", "logs")),
    ("Missions & Runs", ("mission", "run", "golden", "runtime")),
    ("Command Center", ("focus", "goal", "task", "observe", "operation")),
    ("Services & Sidecars", ("gateway", "cashflow", "freellmapi", "discord", "module", "terminal")),
    ("Providers & Models", ("provider", "models", "auth", "config")),
    ("Data & Knowledge", ("db", "project", "graph", "wiki")),
    ("Integrations", ("channels", "tools", "surface")),
    ("Dev / Internal", ("foundation",)),
)
# Never shown as a browsable entry (this command IS the browser).
_EXCLUDE = frozenset({"help"})


@dataclass
class CommandEntry:
    name: str
    summary: str


def _visible_top_level(root_command) -> list[tuple[str, object]]:
    return [
        (name, cmd)
        for name, cmd in sorted(root_command.commands.items())
        if not getattr(cmd, "hidden", False) and name not in _EXCLUDE
    ]


def build_catalog(root_command) -> tuple[list[str], dict[str, list[CommandEntry]]]:
    """Returns (tab_order, {tab_label: [CommandEntry, ...]})."""
    entries = {
        name: CommandEntry(name=name, summary=cmd.get_short_help_str(limit=200))
        for name, cmd in _visible_top_level(root_command)
    }
    categorized: set[str] = set()
    tabs: dict[str, list[CommandEntry]] = {}
    for label, names in _CATEGORIES:
        tabs[label] = [entries[n] for n in names if n in entries]
        categorized.update(names)
    leftover = sorted(set(entries) - categorized)
    tab_order = [label for label, _ in _CATEGORIES]
    if leftover:
        tabs["Other"] = [entries[n] for n in leftover]
        tab_order.append("Other")
    return tab_order, tabs


def _get_help_text(app, command_name: str) -> str:
    from typer.testing import CliRunner

    result = CliRunner().invoke(app, [command_name, "--help"])
    return result.output


def _term_width() -> int:
    return max(shutil.get_terminal_size(fallback=(100, 24)).columns, 40)


def render_static(tab_order: list[str], tabs: dict[str, list[CommandEntry]]) -> None:
    """Non-interactive fallback: a categorized listing, printed once."""
    import typer

    for label in tab_order:
        typer.echo(f"\n{label}")
        typer.echo("-" * len(label))
        for entry in tabs[label]:
            typer.echo(f"  atlas {entry.name:<14} {entry.summary}")
    typer.echo("\nRun 'atlas <command> --help' for full details on any command.")


def _search(tabs: dict[str, list[CommandEntry]], query: str) -> list[CommandEntry]:
    if not query:
        return []
    q = query.lower()
    seen: dict[str, CommandEntry] = {}
    for entries in tabs.values():
        for entry in entries:
            if q in entry.name.lower() or q in entry.summary.lower():
                seen[entry.name] = entry
    return [seen[name] for name in sorted(seen)]


def _render_browse(
    tab_order: list[str], tab_idx: int, entries: list[CommandEntry], cursor: int,
    mode: str, query: str, width: int,
) -> list[str]:
    lines = []
    tab_bar = "  ".join(
        f"[{i + 1}:{label}]" if i == tab_idx else f" {i + 1}:{label} "
        for i, label in enumerate(tab_order)
    )
    lines.append(tab_bar[: width - 1])
    if mode == "search":
        lines.append(f"/{query}")
    else:
        lines.append("")
    lines.append("")
    if not entries:
        lines.append("  (no matches)" if mode == "search" else "  (no commands in this tab)")
    for i, entry in enumerate(entries):
        pointer = ">" if i == cursor else " "
        line = f"{pointer} atlas {entry.name:<14} {entry.summary}"
        lines.append(line[: width - 1])
    lines.append("")
    if mode == "search":
        lines.append("(type to filter, up/down: move, enter: details, esc: back to tabs)")
    else:
        lines.append("(1-9/left/right: tabs, up/down: move, enter: details, /: search, q: quit)")
    return lines


def _draw(lines: list[str], prev_line_count: int) -> int:
    """Redraw in place given how many lines the *previous* frame took up
    (not the new one — tabs have different entry counts, so frame height
    varies between draws; using the new frame's length to move the cursor up
    desyncs it from the previous frame and leaves stale lines on screen).
    Returns the new frame's line count for the next call. Pass 0 to print a
    fresh frame below whatever is already on screen (no cursor-up at all) —
    used right after printing something untracked, like a detail view.
    """
    if prev_line_count:
        sys.stdout.write(f"\x1b[{prev_line_count}A")
    for line in lines:
        sys.stdout.write("\x1b[2K" + line + "\n")
    extra = prev_line_count - len(lines)
    if extra > 0:
        # The new frame is shorter — clear the leftover trailing lines from
        # the longer previous frame, then move back up past them so the next
        # draw's cursor-up math (based on the new, shorter count) stays correct.
        for _ in range(extra):
            sys.stdout.write("\x1b[2K\n")
        sys.stdout.write(f"\x1b[{extra}A")
    sys.stdout.flush()
    return len(lines)


def _show_detail(app, command_name: str) -> None:
    import typer

    text = _get_help_text(app, command_name)
    typer.echo(f"\n--- atlas {command_name} --help {'-' * 10}")
    typer.echo(text)
    typer.echo("(press any key to go back)")
    _read_key()


def run_browser(app, root_command, read_key=_read_key) -> None:
    """Interactive tabbed command browser. Falls back to a static listing
    when stdio isn't a real TTY."""
    tab_order, tabs = build_catalog(root_command)
    if not (sys.stdin.isatty() and sys.stdout.isatty()):
        render_static(tab_order, tabs)
        return

    tab_idx = 0
    cursor = 0
    mode = "browse"
    query = ""
    search_results: list[CommandEntry] = []
    prev_lines = 0

    while True:
        entries = search_results if mode == "search" else tabs[tab_order[tab_idx]]
        if entries and cursor >= len(entries):
            cursor = len(entries) - 1
        elif not entries:
            cursor = 0
        prev_lines = _draw(
            _render_browse(tab_order, tab_idx, entries, cursor, mode, query, _term_width()), prev_lines
        )
        key = read_key()

        if mode == "search":
            if key == "quit":
                mode, query, search_results, cursor = "browse", "", [], 0
                prev_lines = 0
            elif key == "backspace":
                query = query[:-1]
                search_results = _search(tabs, query)
                cursor = 0
            elif key == "up" and entries:
                cursor = (cursor - 1) % len(entries)
            elif key == "down" and entries:
                cursor = (cursor + 1) % len(entries)
            elif key == "enter":
                if entries:
                    _show_detail(app, entries[cursor].name)
                prev_lines = 0
            elif len(key) == 1 and key.isprintable():
                query += key
                search_results = _search(tabs, query)
                cursor = 0
            continue

        # browse mode
        if key in ("quit", "q", "Q"):
            return
        if key == "/":
            mode, query, search_results, cursor = "search", "", [], 0
        elif key == "left":
            tab_idx = (tab_idx - 1) % len(tab_order)
            cursor = 0
        elif key == "right":
            tab_idx = (tab_idx + 1) % len(tab_order)
            cursor = 0
        elif key.isdigit() and key != "0" and int(key) <= len(tab_order):
            tab_idx = int(key) - 1
            cursor = 0
        elif key == "up" and entries:
            cursor = (cursor - 1) % len(entries)
        elif key == "down" and entries:
            cursor = (cursor + 1) % len(entries)
        elif key == "enter":
            if entries:
                _show_detail(app, entries[cursor].name)
            prev_lines = 0
