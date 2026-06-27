"""Native 4-option permission prompt (TUI-06): approve once / scoped allow /
reject / cancel — mapped exactly onto `permission_broker.claim`/`record_allow_rule`.

This module is the SOLE authority-mapping point between the TUI's 4 visible
options and the broker's 2 valid `claim` decision values (`approve`/`reject`)
plus the 3 `SessionAllowRuleKind` values. It never reimplements allow-rule
matching or normalization (PERM-07) — the "session" branch calls
`permission_broker.record_allow_rule` with an `arg_pattern` produced ONLY by
`permission_broker.allow_pattern_for_args`, the same helper the real
`invoke()` path uses for `args_normalized`.

Rendering (`render_approval_panel`) is pure (no I/O, no broker calls) and is
exercised indirectly by the dispatch tests in `tests/tui/test_permission_ui.py`.

Cancel is intentionally TUI-local: `permission_broker._VALID_CLAIM_DECISIONS`
has no "cancel" value, so a cancelled prompt makes ZERO broker calls and
leaves the approval pending in the broker's queue for a future decision
(T-10.6-12, accepted risk — no silent state loss, operator can revisit).

Every broker exception (`WrongSessionError`, `NotActiveSessionError`,
`StaleApprovalError`, `AlreadyDecided`, `ApprovalChannelMissingError`)
propagates out of `resolve_approval_choice` UNMODIFIED — no try/except wraps
the dispatch, so a headless/no-channel request fails closed rather than
appearing to silently succeed (T-10.6-13).
"""
from __future__ import annotations

import json
import sqlite3
import threading
from typing import TYPE_CHECKING, Optional

from rich import box
from rich.panel import Panel
from rich.text import Text

from atlas_runtime import permission_broker
from atlas_runtime import tool_service
from atlas_runtime.tui.theme import safe_style

if TYPE_CHECKING:
    from atlas_core.schemas.tool import ToolApproval

    from atlas_runtime.tui.capabilities import Capabilities

# Module-level lock for broker calls issued from the TUI (mirrors the
# `_LOCK = threading.Lock()` convention used by atlas_runtime/cli/*.py).
_LOCK = threading.Lock()

# Closed set of the 4 dialog options, in display order.
_OPTS = ("once", "session", "reject", "cancel")
_LABELS = {
    "once": "Approve once",
    "session": "Allow for this session",
    "reject": "Reject",
    "cancel": "Cancel",
}

# Maps the public `choice` values accepted by `resolve_approval_choice` (which
# mirror what the test suite / app.py key-binding loop pass) onto the internal
# `_OPTS` keys used for rendering/labels. Both forms are accepted so callers
# using either vocabulary dispatch identically.
_CHOICE_ALIASES = {
    "approve_once": "once",
    "allow_scoped": "session",
    "once": "once",
    "session": "session",
    "reject": "reject",
    "cancel": "cancel",
}


def render_approval_panel(
    approval: "ToolApproval", selected_idx: int, *, caps: "Capabilities"
) -> Panel:
    """Render the 4-option permission dialog as a pure (no I/O) `rich.panel.Panel`.

    `selected_idx` (0-3, indexing `_OPTS`) is visually highlighted via
    `safe_style("primary", caps)`; on ASCII-only terminals (legacy Windows
    conhost, no reverse-video support) the selection is also marked with
    `[x]`/`[ ]` ASCII brackets rather than relying on color/highlight alone.
    """
    ascii_only = caps.box_style == "ascii"
    body = Text()
    body.append(f"{approval.tool_name}", style="bold")
    body.append(f"  ({approval.risk_level})\n", style=safe_style("muted", caps))
    if approval.summary:
        body.append(f"{approval.summary}\n\n")
    else:
        body.append("\n")

    for idx, key in enumerate(_OPTS):
        label = _LABELS[key]
        selected = idx == selected_idx
        if ascii_only:
            marker = "[x]" if selected else "[ ]"
            line = f"{marker} {label}"
            style = safe_style("primary", caps) if selected else ""
        else:
            marker = ">" if selected else " "
            line = f"{marker} {label}"
            style = safe_style("primary", caps) if selected else ""
        if style:
            body.append(line, style=style)
        else:
            body.append(line)
        body.append("\n")

    return Panel(
        body,
        title="Permission Request",
        box=box.ASCII if ascii_only else box.ROUNDED,
    )


def resolve_approval_choice(
    conn: sqlite3.Connection,
    *,
    approval_id: str,
    surface_session_id: str,
    choice: str,
    headless: bool = False,
) -> Optional["ToolApproval"]:
    """Dispatch a resolved dialog `choice` onto `permission_broker` for `approval_id`.

    `choice` accepts either the dialog's internal vocabulary (`once`/`session`/
    `reject`/`cancel`) or the caller-facing aliases (`approve_once`/
    `allow_scoped`/`reject`/`cancel`) used by the test suite and app.py's
    key-binding loop; both resolve to the same dispatch.

    - "cancel" -> returns `None` immediately. Calls NEITHER `claim` NOR
      `record_allow_rule` (the broker's `_VALID_CLAIM_DECISIONS` has no cancel
      value, so cancel MUST stay TUI-local; the approval remains pending).
    - "once" / "approve_once" -> `claim(decision="approve", record_rule=None)`.
      Never calls `record_allow_rule`.
    - "session" / "allow_scoped" -> `claim(decision="approve", record_rule=None)`
      first (the approve+execute is the authoritative action), THEN
      `record_allow_rule(rule_kind="allow_session", arg_pattern=
      allow_pattern_for_args(...))` using the broker's own normalization
      helper — never a hand-rolled pattern (PERM-07). If `record_allow_rule`
      itself raises, the exception propagates: the approve already executed
      via `claim` and there is no broker rollback primitive (accepted risk).
    - "reject" -> `claim(decision="reject", record_rule=None)`. Never calls
      `record_allow_rule`.

    Every exception raised by `claim`/`record_allow_rule` (including
    `ApprovalChannelMissingError` for a headless surface with no registered
    approval channel) propagates UNMODIFIED — this function never catches and
    silently treats a failure as still-pending.

    The nonce passed to `claim` is read off the persisted approval row itself
    (the broker's own replay guard, SEC-02) — the TUI never invents or caches
    a nonce of its own.
    """
    resolved = _CHOICE_ALIASES.get(choice)
    if resolved is None:
        raise ValueError(f"unknown approval choice: {choice!r}")

    if resolved == "cancel":
        return None

    approval = tool_service._load(conn, approval_id)
    nonce = approval.nonce

    if headless and not permission_broker.has_open_channel(conn, surface_session_id):
        raise permission_broker.ApprovalChannelMissingError(
            f"surface session {surface_session_id!r} has no open approval channel"
        )

    if resolved == "reject":
        return permission_broker.claim(
            conn,
            _LOCK,
            approval_id=approval_id,
            surface_session_id=surface_session_id,
            decision="reject",
            nonce=nonce,
            record_rule=None,
        )

    # "once" and "session" both start with the same approve claim; "session"
    # additionally records a scoped allow-rule afterward.
    terminal = permission_broker.claim(
        conn,
        _LOCK,
        approval_id=approval_id,
        surface_session_id=surface_session_id,
        decision="approve",
        nonce=nonce,
        record_rule=None,
    )

    if resolved == "session":
        permission_broker.record_allow_rule(
            conn,
            _LOCK,
            surface_session_id=surface_session_id,
            workspace_root=approval.workspace_root,
            surface_kind=approval.surface_kind,
            tool_name=approval.tool_name,
            arg_pattern=permission_broker.allow_pattern_for_args(
                json.loads(approval.args or "{}")
            ),
            rule_kind="allow_session",
        )

    return terminal


__all__ = ["render_approval_panel", "resolve_approval_choice", "_OPTS", "_LABELS"]
