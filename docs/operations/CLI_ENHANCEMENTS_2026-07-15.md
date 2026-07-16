# ATLAS CLI — 2026-07-15 additions and enhancements

Operational reference for the CLI work done this session. Complements (does
not replace) `docs/operations/CLI_VISUAL_MANUAL.md`, which is a frozen v1.0
walkthrough — several of that doc's "Not v1.0" items (`atlas db init`,
configurable CLI DB path) are simply out of date now; this doc covers what
changed after it.

Full, always-current command reference: **`atlas help`** (see below) — it
introspects the live command tree, so it can't drift out of sync with the
code the way a hand-written list can. This document instead explains the
*new/changed* commands and the reasoning behind them.

---

## 1. `atlas help` — interactive tabbed command browser

`atlas help` used to just print the root `--help` banner. It now opens a
full-screen, dependency-free command browser when stdin/stdout are a real
terminal:

```bash
atlas help
```

**Layout:**
- Top: a row of numbered category tabs (`1:Getting Started`, `2:Missions &
  Runs`, `3:Command Center`, `4:Services & Sidecars`, `5:Providers & Models`,
  `6:Data & Knowledge`, `7:Integrations`, `8:Dev / Internal`). A trailing
  `Other` tab appears automatically if a command is ever added without being
  slotted into a category — nothing is ever silently hidden.
- Middle: the commands in the active tab, one per line, with their one-line
  summary (pulled live from each command's own help text).
- Bottom: a keybinding hint line.

**Keybindings:**

| Key | Effect |
|---|---|
| `1`-`8` | Jump directly to a tab |
| `←` / `→` | Cycle tabs (wraps) |
| `↑` / `↓` | Move the selection within the current tab/search results |
| `Enter` | Show the selected command's full `--help` (real output, drilled in via an internal `CliRunner` call — byte-identical to running it yourself); press any key to return |
| `/` | Enter search mode — type to fuzzy-filter every command (name + summary) across all tabs at once |
| `Backspace` (in search) | Edit the search query |
| `Esc` (in search) | Leave search, back to tab browsing |
| `q` / `Esc` / `Ctrl-C` (in tab browsing) | Quit |

**Non-interactive fallback:** if stdin/stdout aren't a real TTY (CI, piped
output, `atlas help | less`), or you pass `--plain`, it prints the same
categorization as a flat listing and exits — no prompt, no hang:

```bash
atlas help --plain
```

**Implementation notes** (for the next person touching this):
- `services/agent-runtime/atlas_runtime/cli/help_browser.py` — the browser.
  Category membership is the one hand-maintained piece (`_CATEGORIES`); the
  command names/summaries themselves come from `typer.main.get_command(app)`,
  so adding a new `atlas <x>` command automatically shows up (in `Other`
  until categorized).
- `services/agent-runtime/atlas_runtime/cli/interactive_select.py` —
  shares its raw-terminal key reader (`_read_key`, extended this session
  with left/right/backspace support) with the `atlas up` picker (see below).
  Both are stdlib-only (`msvcrt` on Windows, `termios`/`tty` on POSIX) — no
  new dependency (matches this codebase's existing anti-bloat convention).
- Detail view deliberately shells out to `typer.testing.CliRunner` rather
  than constructing a `click.Context` by hand — the latter renders some
  option defaults incorrectly outside the real invocation path (a click/typer
  quirk); `CliRunner.invoke` goes through the exact same code path a user's
  terminal does.
- Tests: `tests/test_help_browser.py` (13 tests) — the state machine is
  fully covered via an injectable `read_key`, same pattern as
  `tests/test_interactive_select.py`. The actual live terminal feel (arrow
  keys, redraw-in-place) is not, and can't be, exercised from an automated
  environment — worth a quick manual pass in a real terminal.

---

## 2. `atlas up` — interactive service picker

Previously `atlas up` always attempted gateway + cockpit + freellmapi, with
cashflow/discord unreachable except via manual subcommands. It's now
health-aware and, on a real TTY, interactive:

```bash
atlas up
```

Checks `health_ok()` on all 5 services first (gateway, cockpit, freellmapi,
cashflow, discord). Already-running ones show as locked/checked in the
picker (can't be toggled off — nothing to do). Space toggles a service,
Enter confirms, `q`/Esc/Ctrl-C cancels (exits 1, nothing started).

Non-interactive/scripted paths are unchanged in spirit — they use the same
default set as before (gateway, cockpit, freellmapi; cashflow/discord stay
opt-in) without prompting:

```bash
atlas up --yes                        # default set, no prompt
atlas up --services gateway,cashflow  # explicit set, no prompt
atlas up --json                       # implies non-interactive; machine-readable
```

Sidecars selected by the operator (or via `--services`) still only start
once gateway+cockpit are actually healthy — this generalizes the prior
D-015 freellmapi-specific gating to all sidecars.

`atlas down` is unchanged.

Implementation: `_up_cmd` in
`services/agent-runtime/atlas_runtime/cli/main.py` (`_UP_SERVICE_REGISTRY`).
Tests: `tests/test_cli_up.py` (13 tests, 7 new this session).

---

## 3. `atlas freellmapi install` — sidecar lifecycle, ATLAS-controlled

Prior gap: FreeLLMAPI (the optional free-tier LLM sidecar, D-015) only
resolved from inside this monorepo checkout (`_EXTERNAL_REPOS/` or a sibling
folder) — paths that don't exist for someone who installs `atlas` via
npm/pip with no git repo on disk. The operator had to manually
`git clone`+build it themselves with no CLI path to do so.

New default install location — inside the ATLAS install home itself:

```bash
atlas freellmapi install                 # clones+builds into <ATLAS home>/sidecars/freellmapi
atlas freellmapi install --target <dir>  # or a custom directory
atlas freellmapi install --force         # wipe+re-clone if something non-checkout is in the way
```

`<ATLAS home>` honors `ATLAS_DB`/`ATLAS_HOME` at call time (same resolution
`atlas`'s own database and workspace root use) — `freellmapi_control.sidecar_home()`.
Resolution order for `atlas freellmapi start/status`: `ATLAS_FREELLMAPI_DIR`
env > remembered state file > `sidecar_home()` > the old dev-checkout sibling
paths (kept as back-compat fallback, not removed — an existing manual
checkout next to the repo still resolves correctly).

Implementation: `services/agent-runtime/atlas_runtime/freellmapi_control.py`.
Tests: `tests/test_freellmapi_control.py` (17 tests, 8 new this session).

---

## 4. `atlas logs` — tail/follow the rotating log file

New. Every ATLAS entry point already writes to a rotating log file
(`logging_config.py`, F13) but there was no CLI path to read it — you had to
know `<ATLAS home>/logs/atlas.log` existed and go find it yourself.

```bash
atlas logs               # last 50 lines
atlas logs --tail 200    # last 200 lines
atlas logs --tail 0      # whole file
atlas logs --follow      # keep streaming new lines (Ctrl-C to stop); survives log rotation
atlas logs --path        # just print the resolved path, don't read it
```

Implementation: `_logs_cmd` in `cli/main.py` +
`logging_config.log_file_path()` (new public accessor for what was
previously a private `_default_log_dir()` helper). Tests:
`tests/test_cli_logs.py` (6 tests; `--follow`'s polling loop isn't covered —
it only exits on Ctrl-C, not practical to drive from a test).

---

## 5. Minor: `atlas surface` subcommand help text

`get`, `list`, `heartbeat`, `suspend`, `resume`, `cancel`, `close` had no
docstrings, so `atlas surface --help` showed them with a blank description.
Added one-liners for each — no behavior change.

---

## Verification (this session)

- `services/agent-runtime`: full pytest suite **825 passed** (0 failed).
- Live-checked: `atlas help`, `atlas help --plain`, `atlas up --json`,
  `atlas freellmapi status`, `atlas logs --path` all run correctly against a
  real (not mocked) ATLAS home on this machine.
- **Not verified**: the actual live keyboard feel of `atlas help`'s and
  `atlas up`'s interactive pickers (arrow keys, in-place redraw, terminal
  resize behavior) — this environment has no real TTY to drive one from.
  Worth a first-touch check in a real terminal session.
