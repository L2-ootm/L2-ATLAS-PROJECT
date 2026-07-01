"""De-brand audit for the canonical Go terminal surface (TUI-11).

Grep-style smoke test, not a fixture-based unit test. This is the final
phase-wide enforcement point for TUI-11/criterion 5 (Wave 4): atlas_runtime/tui/
source and all --help output (including the hidden dev-foundation-tui
command's own help) must carry no Hermes/Ink identity outside a `# provenance:`
comment.

ONE REMAINING KNOWN PRE-EXISTING LEAK (documented, out of scope for this
phase): `atlas foundation` (cli/foundation.py: "Inspect and verify the
vendored ATLAS foundation (foundation/atlas-hermes).") legitimately references
"foundation/atlas-hermes" in its own help= string, because that is literally
the vendored directory it inspects. It is unrelated to the terminal-workbench
surface TUI-11 governs and is untouched by this phase. This test strips that
one known phrase before checking for identity leaks, so it stays meaningful
for catching any OTHER (new, unexpected) leak without false-failing on
pre-existing, intentional text.
"""
from __future__ import annotations

import pathlib
import re

from typer.testing import CliRunner

from atlas_runtime.cli.main import app

runner = CliRunner()

_FORBIDDEN_IDENTITY_TOKENS = ("hermes", "ink", "atlas-hermes")


# Pre-existing help= strings that legitimately reference the vendored Hermes
# tree today (see module docstring). Rich's --help renderer hard-wraps long
# strings across box-drawing table cells, so raw substrings never survive
# intact in captured output — match on whitespace-collapsed text instead.
_KNOWN_LEAK_PATTERNS = (
    re.compile(
        r"vendored\s+atlas\s+foundation\s+foundation\s+atlas-hermes",
        re.IGNORECASE,
    ),  # `foundation` command help text (out of scope for this phase)
)


def _collapse_whitespace(text: str) -> str:
    """Normalize for substring/pattern matching: keep only ASCII letters, digits,
    and hyphens, collapsing everything else (whitespace, Rich box-drawing border
    glyphs, punctuation) to a single space. This makes a help phrase wrapped
    across a table cell boundary (e.g. "...foundation │ (foundation/atlas-
    hermes)...") read as one contiguous phrase for pattern matching, since the
    box-drawing glyphs that separate wrapped cells are themselves collapsed."""
    return re.sub(r"[^A-Za-z0-9-]+", " ", text)


def _strip_known_pre_existing_leaks(text: str) -> str:
    """Remove the known pre-existing leak phrases (see module docstring) so the
    remaining output can be checked for any OTHER (new, unexpected) identity
    leak. Returns the text unchanged if none of the known leaks are present —
    which is exactly what should happen once `tui` is rewired in Wave 4."""
    collapsed = _collapse_whitespace(text)
    for pattern in _KNOWN_LEAK_PATTERNS:
        collapsed = pattern.sub("", collapsed)
    return collapsed


def test_help_output_contains_no_hermes_identity():
    """TUI-11: --help output (root + `tui --help` + `dev-foundation-tui --help`)
    leaks no Hermes/Ink identity EXCEPT the one remaining known pre-existing
    source (the unrelated `foundation` command's help= string, documented in
    the module docstring). That known phrase is stripped before asserting; any
    OTHER occurrence is a real, unexpected leak.

    LOAD-BEARING (Wave 4): the `tui` command was rewired to the native
    workbench, so its own help text no longer carries any legacy phrase.
    `dev-foundation-tui --help` is asserted clean too — the de-branded help
    text introduced in Wave 4 must hold here.
    """
    root_help = runner.invoke(app, ["--help"])
    tui_help = runner.invoke(app, ["tui", "--help"])
    dev_tui_help = runner.invoke(app, ["dev-foundation-tui", "--help"])
    combined = _strip_known_pre_existing_leaks(
        root_help.output + tui_help.output + dev_tui_help.output
    ).lower()
    for token in _FORBIDDEN_IDENTITY_TOKENS:
        assert token not in combined, f"forbidden identity token {token!r} leaked into --help output"


def test_retired_python_tui_package_is_absent():
    """The rejected Rich/prompt_toolkit generation cannot leak identity or behavior."""
    package_root = pathlib.Path(__file__).resolve().parent.parent / "atlas_runtime"
    tui_dir = package_root / "tui"
    assert not tui_dir.exists()
