"""Compact identity/status header rendering (TUI-03).

`render_status_header` only reads display fields already present on the
caller-supplied `snapshot` mapping (model id/provider, permission mode,
context budget, focus title, session state) and prints them via the given
`rich.console.Console`. It never resolves or touches any raw-secret field
(e.g. `resolved_api_key`) even when one happens to be present on the snapshot
mapping — masking is enforced by simply never reading that key, per T-10.6-01.
"""
from __future__ import annotations

from typing import Mapping

from rich.console import Console
from rich.text import Text

# Explicit allowlist of snapshot fields this header is permitted to render.
# Any other key on the snapshot mapping (including secret-shaped fields such
# as `resolved_api_key`) is never read by this module.
_ALLOWED_FIELDS = (
    "model_id",
    "model_provider",
    "permission_mode",
    "context_budget_used",
    "context_budget_total",
    "focus_title",
    "state",
)


def render_status_header(console: Console, snapshot: Mapping[str, object]) -> None:
    """Render the compact ATLAS status header to `console`.

    Composes a single-line `rich.text.Text` from the allowlisted snapshot
    fields only: brand identity, model id/provider, permission mode, a
    context-budget figure (used/total), focus title (or an explicit
    "no active focus" marker), and session state.
    """
    model_id = snapshot.get("model_id", "unknown-model")
    model_provider = snapshot.get("model_provider", "unknown-provider")
    permission_mode = snapshot.get("permission_mode", "unknown")
    budget_used = snapshot.get("context_budget_used")
    budget_total = snapshot.get("context_budget_total")
    focus_title = snapshot.get("focus_title") or "no active focus"
    state = snapshot.get("state", "unknown")

    if budget_used is not None and budget_total is not None:
        context_str = f"{budget_used}/{budget_total}"
    elif budget_used is not None:
        context_str = str(budget_used)
    else:
        context_str = "n/a"

    text = Text()
    text.append("ATLAS", style="bold")
    text.append(" | ")
    text.append(f"{model_id} ({model_provider})")
    text.append(" | ")
    text.append(f"mode={permission_mode}")
    text.append(" | ")
    text.append(f"context={context_str}")
    text.append(" | ")
    text.append(f"focus={focus_title}")
    text.append(" | ")
    text.append(f"state={state}")

    console.print(text)


__all__ = ["render_status_header"]
