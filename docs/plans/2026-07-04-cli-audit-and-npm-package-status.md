# CLI audit + npm package status (TASK 7, 2026-07-04)

Scoped per the TUI Connectivity & Auth sprint: TASK 7 is conditional on TASK
1-6 passing (they do — see HANDOFF.md 2026-07-04 entry) and is framed as an
audit + plan, not a full refactor. This is that audit, plus a status update
on the existing npm packaging plan (`docs/plans/2026-07-03-wsb-installer-plan.md`,
§7 sequencing) rather than a duplicate design.

## CLI audit findings

**`--json` coverage is a real, mixed convention** — two patterns coexist:

- Dedicated `json` subcommand (separate from the human-readable one):
  `auth json`, `channels json`, `config json`.
- `--json` flag on the existing command: `atlas doctor --json` (new this
  session), `atlas version --json`, `atlas terminal status --json` (new this
  session), `models`, `discord`, `surface`, `tools`, `provider`, `golden`
  (existing, `--json` flag per-command).

Neither pattern is wrong on its own, but an operator scripting against
`atlas` has to know per-group which one applies. **Not fixed this session** —
standardizing means touching ~9 CLI modules plus their tests, which is a
real refactor, not an audit-scope change. Recommendation: adopt `--json` as
the flag going forward (it's the majority pattern and what this session's
new commands used) and fold `auth json`/`channels json`/`config json` into
`--json` flags on their `status`/`show` commands in a dedicated pass —
don't do it inline with unrelated feature work.

**Named-drift spots called out in the sprint prompt** (`purge-archived`,
`config json`, `channels status`) were checked live and are already
consistent — `mission purge-archived`, `config json`, `channels status` all
resolve correctly with clear help text. No action needed; this concern
appears to have been resolved in an earlier session.

**Error contract**: `atlas doctor` (extended this session) and
`atlas terminal status` both now return `{"check": {"status": str, "ok":
bool}}` / a flat report object under `--json`. Older groups
(`provider status`, `models`) return ad hoc shapes rather than a uniform
`{error: {code, message, remediation}}` envelope. Not touched this session —
same reasoning as the `--json` convention: a real cross-cutting change,
not an audit-scope fix.

**Help/discoverability**: `atlas -h` / `atlas --help` at the root and every
subgroup (`atlas config -h`, `atlas auth -h`, etc.) already produce clear,
consistent Typer-rendered help with one-line command summaries — this part
of the sprint's ask is already in good shape, nothing further needed.

## npm package status

The architecture, decision, and sequencing are already fully specified in
`docs/plans/2026-07-03-wsb-installer-plan.md` (npm wrapper + versioned
release bundle, `~/.atlas/versions/<v>/` + `current` pointer, install/
update/rollback/uninstall/doctor commands). That plan's own §7 sequencing
already reflects real progress: step 1 (`packages/atlas-cli/` launcher
mechanics) and step 2 (doctor checksum/manifest checks) are marked DONE;
steps 3-6 (clean-machine runbook, TUI binary-manifest decision, real CI
publishing, first real gate run) remain open.

**What changed this session that's relevant to that plan:**
- `atlas-terminal` is now installer-integrated (TASK 4: build step in both
  `scripts/install-atlas-cli.ps1` and `scripts/setup.sh`, plus `atlas
  terminal status`) — this doesn't yet resolve §6's "which TUI ships"
  question (Go TUI is still the default `atlas`/`atlas tui` entry), but it
  means atlas-terminal is no longer a source-checkout-only surface; the
  installer plan's manifest work can reference it directly once the
  retirement gate decision is made.
- `atlas doctor` now reports binary staleness, sidecar reachability, and
  model-registry freshness (TASK 3) — this is exactly the "installed-vs-
  running drift" check §3.2's `manifest.json` section anticipates; the npm
  package's `atlas doctor` extension (checksum-vs-manifest) can build on
  this session's staleness-check pattern (`gateway_control.binary_stale()`)
  rather than inventing a new one.

**Not started this session** (unchanged from the WS-B plan's own open
items): the real release-fetch path (`--version X --channel stable`
download + checksum verify), the clean-machine runbook script, and any CI
publishing. These remain correctly out of scope until the TUI retirement
gate (STAGE 3, tracked separately) resolves which binaries the release
bundle manifest actually needs to list.
