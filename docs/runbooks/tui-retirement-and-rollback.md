# Terminal Default Decision, Retirement, and Rollback

## Authority and guardrail

The candidate `atlas-terminal` is the present default for bare `atlas` and `atlas tui`.
The retained Go workbench is the fallback behind `atlas dev-go-tui`. No removal, release push,
milestone archive, or provider-mesh activation is authorized by this document. Only the dated,
operator-owned UAT record may authorize a default change or retirement decision.

## Pre-switch probe

Run these commands from `services/agent-runtime` and attach only redacted output to the UAT record:

```powershell
python -m atlas_runtime.cli.main terminal status --json
python -m atlas_runtime.cli.main doctor --json
python -m atlas_runtime.cli.main version
python -m atlas_runtime.cli.main config show
python -m atlas_runtime.cli.main models list --all
```

Probe the current default interactively: start `atlas`, confirm it starts atlas-terminal, then exit.
Probe the fallback interactively:

```powershell
python -m atlas_runtime.cli.main dev-go-tui --gateway http://127.0.0.1:8484
```

Expected: default and fallback both reach the healthy loopback gateway, show their correct identities,
and preserve the workspace/session boundary. If either probe fails, do not switch or retire anything.

## Candidate-default switch rehearsal

This repository's default routing is code-owned: bare `atlas` and `atlas tui` dispatch to
`atlas_runtime.cli.atlas_terminal.launch`; `dev-go-tui` dispatches to the retained Go sidecar.
There is no runtime config key for switching defaults. Therefore the only valid candidate-default
rehearsal is a temporary, reviewed dispatch change in a dedicated local branch or worktree, never an
invented `atlas config set` key.

1. Record the current commit and source proof:

   ```powershell
   git rev-parse --short HEAD
   git diff -- services/agent-runtime/atlas_runtime/cli/main.py services/agent-runtime/atlas_runtime/cli/atlas_terminal.py services/agent-runtime/atlas_runtime/cli/go_tui.py
   python -m pytest services/agent-runtime/tests/test_tui_app_entry.py -q
   ```

2. Make the proposed dispatch change only after `go` authorization and record its commit. The change
   must preserve `dev-go-tui` as an explicit fallback and must not remove the Go source, binary
   resolution, attribution, or tests.
3. Execute bare `atlas`, `atlas tui`, and `atlas dev-go-tui` in a real terminal. Record the observed
   default, candidate, fallback, version/build identities, and gateway health.

## Rollback rehearsal

Rollback is mandatory before any `go` decision. Restore the known-good dispatch by reverting the
single candidate-default commit (or by restoring the exact recorded source files); do not use a
blanket reset and do not modify credentials/configuration.

```powershell
git revert <candidate-default-commit>
python -m pytest services/agent-runtime/tests/test_tui_app_entry.py -q
python -m atlas_runtime.cli.main terminal status --json
python -m atlas_runtime.cli.main doctor --json
python -m atlas_runtime.cli.main version
python -m atlas_runtime.cli.main dev-go-tui --gateway http://127.0.0.1:8484
```

Then launch bare `atlas` and `atlas tui` interactively. Expected: both resolve to the restored
known-good default; the fallback remains launchable; tests, version/identity, and health probes pass.
Record the rollback commit, UTC timestamps, redacted probe output, and any recovery receipt in
`10.8-UAT-RECORD.md`. A failed rollback rehearsal means `no-go`; an incomplete rehearsal means
`defer`.

## Dated retention/removal decision

The operator must fill these fields in the UAT record after successful UAT and rollback:

- Decision date and operator identity.
- Candidate default and restored fallback identity/version.
- Retain Go TUI through date, or remove it in a separately approved future plan.
- Removal preconditions: successful rollback rehearsal, retention window elapsed, explicit release
  authorization, attribution preserved, and a separately reviewed removal commit.
- Evidence links: UAT record, live-battery report, diagnostic capture, switch and rollback commits.

Until those fields contain an explicit `go`, the current default remains in place and the fallback is
retained.
