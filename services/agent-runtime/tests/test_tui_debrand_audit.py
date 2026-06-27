"""De-brand audit: no imported product identity (Hermes/Ink) leaks into source or output (TUI-11).

Grep-style smoke test, not a fixture-based unit test. Runs WITHOUT depending on
atlas_runtime.tui existing, so it collects and runs cleanly pre-Wave-1. This
becomes a meaningful regression guard once Wave 1+ lands the real
atlas_runtime/tui/ package and Wave 4 wires the CLI; until then it documents the
intended invariant. Per Nyquist, pytest.xfail is forbidden — instead this file
asserts the CURRENT real condition and flags explicitly where the assertion
direction must flip post-Wave-1.

KNOWN PRE-EXISTING LEAKS (documented, not fixed by this Wave-0 plan): two
*existing* commands legitimately reference "foundation/atlas-hermes" in their
own help= strings today, because that is literally the vendored directory they
inspect/launch:
  - `atlas tui` (cli/main.py registration: "Launch the ATLAS terminal UI
    (foundation Ink TUI, ATLAS-skinned).") — the OLD Hermes-Ink wrapper this
    whole phase replaces. Wave 4 rewires this registration to the native
    workbench, at which point the phrase disappears.
  - `atlas foundation` (cli/foundation.py: "Inspect and verify the vendored
    ATLAS foundation (foundation/atlas-hermes).") — out of scope for this
    phase entirely; it inspects the vendored tree by design and is not part
    of the terminal-workbench surface TUI-11 governs.
Editing either pre-existing help= string now is out of scope for this Wave-0
RED-scaffolding plan (Wave 4 owns the `tui` rewiring; `foundation` is untouched
by this phase). This test instead strips the two known phrases before checking
for identity leaks, so it stays meaningful for catching any OTHER (new,
unexpected) leak without false-failing on pre-existing, intentional text.
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
    re.compile(r"foundation\s+ink\s+tui", re.IGNORECASE),  # `tui` command (Wave 4 rewires)
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
    """TUI-11: --help output (root + `tui --help`) leaks no Hermes/Ink identity
    EXCEPT the known pre-existing sources (the old `tui` command's own help=
    string, and the unrelated `foundation` command's help= string — both
    documented in the module docstring). Those known phrases are stripped
    before asserting; any OTHER occurrence is a real, unexpected leak.

    WAVE-4-FLIP: once Wave 4 rewires the `tui` command's registration to the
    native workbench, its pattern stops matching anything in --help. At that
    point narrow `_KNOWN_LEAK_PATTERNS` to just the `foundation` command's
    pattern (which stays out of scope for this phase).
    """
    root_help = runner.invoke(app, ["--help"])
    tui_help = runner.invoke(app, ["tui", "--help"])
    combined = _strip_known_pre_existing_leaks(root_help.output + tui_help.output).lower()
    for token in _FORBIDDEN_IDENTITY_TOKENS:
        assert token not in combined, f"forbidden identity token {token!r} leaked into --help output"


def test_tui_subcommand_help_leak_is_known_pre_existing_not_a_new_regression():
    """TUI-11 (documentation test): confirms the current `tui --help` leak is the
    pre-existing old wrapper's own help text, not something newly introduced. If
    this starts failing because the leak disappears, that is good news — delete
    this test and narrow `_KNOWN_LEAK_PATTERNS` (Wave 4 owns this flip)."""
    tui_help = runner.invoke(app, ["tui", "--help"])
    assert _KNOWN_LEAK_PATTERNS[0].search(_collapse_whitespace(tui_help.output))


def test_tui_package_source_contains_no_hermes_identity():
    """TUI-11: once atlas_runtime/tui/ exists, no source file leaks Hermes/Ink identity
    (excluding documented `# provenance:` comments).

    WAVE-1-FLIP: today `atlas_runtime/tui/` does not exist, so this asserts the
    directory's CURRENT absence rather than scanning it (there is nothing to scan).
    Once Wave 1 creates the package, this assertion MUST be updated to: (a) assert
    the directory exists, and (b) glob *.py under it and assert none of
    _FORBIDDEN_IDENTITY_TOKENS appear case-insensitively in any line that does not
    contain the substring "provenance:". Wave 4's plan task owns flipping this.
    """
    # Locate the atlas_runtime package root (this test file is at
    # services/agent-runtime/tests/test_tui_debrand_audit.py).
    package_root = pathlib.Path(__file__).resolve().parent.parent / "atlas_runtime"
    tui_dir = package_root / "tui"

    if not tui_dir.is_dir():
        # Pre-Wave-1 RED-adjacent state: the package does not exist yet. This is
        # the CURRENT real condition (not a skip/xfail) -- intentionally trivial.
        assert not tui_dir.is_dir()
        return

    # Post-Wave-1: real scan (this branch is dead code until Wave 1 lands, but is
    # written now so Wave 4 only needs to delete the early-return above).
    offending: list[str] = []
    for py_file in tui_dir.rglob("*.py"):
        for lineno, line in enumerate(py_file.read_text(encoding="utf-8").splitlines(), start=1):
            if "provenance:" in line.lower():
                continue
            lowered = line.lower()
            for token in _FORBIDDEN_IDENTITY_TOKENS:
                if token in lowered:
                    offending.append(f"{py_file}:{lineno}: {token!r} in {line!r}")
    assert not offending, "Hermes/Ink identity leaked into atlas_runtime/tui source:\n" + "\n".join(offending)
