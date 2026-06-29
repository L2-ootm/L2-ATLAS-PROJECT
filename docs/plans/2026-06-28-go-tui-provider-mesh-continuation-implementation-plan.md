# Go TUI Provider Mesh Continuation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development
> (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use
> checkbox (`- [ ]`) syntax for tracking.

**Goal:** Finish the operator-pivoted Go/BubbleTea terminal workbench through P6–P8, close the
missing secret-safe provider wiring path, and return the project to the active v1.1 sequence
(10.7 then 10.8) without pulling the full v1.2 rulebook/Models suite into the wrong milestone.

**Architecture:** The Go binary remains a render/input/HTTP client. Python remains the owner of
auth, config, provider resolution, probes, and run state; the Rust gateway remains a dispatch-only
adapter. P6 enriches raw audit-event rendering without a new event bus. P7 configures the one
currently active provider through existing masked config contracts plus a new stdin-only auth
dispatch route, then probes through the existing mission/run/SSE path. P8 switches the launcher
and installers to the Go binary while retaining the Rich workbench as a hidden rollback until
Phase 10.8 completes cross-surface cutover.

**Tech Stack:** Go 1.26/BubbleTea/Bubbles/Lipgloss; Rust/Axum/Tokio; Python 3.11/Typer/Pydantic v2;
pytest, cargo test, and Go test/vet/build.

**Budgets:** no new dependency; Go binary remains under 15 MiB (baseline 11,331,072 bytes);
launcher performs no network call before the UI starts; provider/auth writes remain local,
audited, bounded by the gateway timeout, and secrets never enter argv/log/audit output.

---

## Recovered state and locked sequencing

- Branch: `feat/go-tui-provider-mesh`, 12 commits above `bd914a1`, no upstream.
- Working tree: only untracked `.pytest-cache/`; preserve it.
- P1–P5 and deferred P3 are implemented. Fresh Go baseline: tests pass, vet passes, build passes,
  11,331,072-byte Windows binary.
- Active GSD milestone remains v1.1 at 6/8 phases complete. The operator pivot is an explicit
  post-10.6 follow-up and must finish before 10.7.
- The larger function registry, CLI setup expansion, provider test substrate, and WebUI Models
  suite remain v1.2 work. P7 delivers only the current-provider TUI slice needed to wire and probe
  the four existing auth modes.

## Task 1: Planning alignment and seam correction

**Files:**
- Modify: `docs/plans/2026-06-28-model-function-routing-and-test-suite-plan.md`
- Modify: `.planning/milestones/v1.2-ROADMAP-DRAFT.md`
- Modify: `.planning/milestones/v1.2-REQUIREMENTS-DRAFT.md`
- Modify: `.planning/ROADMAP.md`
- Modify: `.planning/STATE.md`

- [x] Record the completed Hermes seam spike:
  `main=routed`, `curator=routed`, `auxiliary.<task>=routed`,
  `background-review=inherited`.
- [x] Correct the snapshot claim: `RunContractSnapshot` currently freezes prompt/tool/context,
  not provider/model bindings.
- [x] Add PM-07 for shared CLI/TUI/WebUI provider/model surfaces and update v1.2 dependencies and
  requirements.
- [x] Record the safe P8 sequencing: Go becomes default; Rich remains a hidden rollback until
  10.8 rather than being deleted early.
- [x] Update STATE after this meaningful planning step.

## Task 2: P6 rich transcript renderer (TDD)

**Files:**
- Create: `services/atlas-tui/internal/tui/events.go`
- Create: `services/atlas-tui/internal/tui/events_test.go`
- Create: `services/atlas-tui/internal/tui/model_test.go`
- Modify: `services/atlas-tui/internal/tui/model.go`
- Modify: `services/atlas-tui/internal/tui/theme.go`
- Modify: `services/atlas-tui/README.md`

- [x] Write failing table tests for audit rendering:

```go
func TestRenderEventKinds(t *testing.T) {
    cases := []struct{ name, payload, want string }{
        {"text", `{"event_type":"llm_call","data":{"text":"hello"}}`, "hello"},
        {"reasoning", `{"event_type":"llm_call","data":{"surface_kind":"reasoning","text":"checking"}}`, "reasoning"},
        {"tool", `{"event_type":"tool_call","tool_name":"terminal","data":{"input":{"cmd":"go test ./..."}}}`, "terminal"},
        {"diff", `{"event_type":"artifact","tool_name":"Write","data":{"surface_kind":"diff","path":"a.go","additions":3,"deletions":1}}`, "a.go"},
        {"retrieval", `{"event_type":"wiki_update","data":{"surface_kind":"retrieval","title":"Provider mesh"}}`, "Provider mesh"},
    }
    // Each payload is wrapped as client.RunEvent{Name:"audit", Data:...}.
}
```

- [x] Run `go test ./internal/tui -run TestRenderEventKinds -v` and confirm RED because the
  specialized renderer does not exist.
- [x] Implement a small `auditFrame` decoder and deterministic renderers. Never render arbitrary
  secret-bearing maps wholesale; use an allowlist of display fields and fall back to event type +
  tool name.
- [x] Add failing render tests that force ASCII and Unicode glyph sets, strip ANSI, render at
  80x24 and 140x40, and assert no replacement rune (`�`) or out-of-contract donor branding.
- [x] Force glyph selection safely through the documented test environment overrides while leaving
  automatic environment detection in production.
- [x] Run `go test ./...`, `go vet ./...`, `go build`, record binary size, and keep it below 15 MiB.
- [x] Commit P6 atomically and update STATE.

## Task 3: Secret-safe non-interactive auth contract (TDD)

**Files:**
- Modify: `services/agent-runtime/atlas_runtime/cli/auth.py`
- Modify: `services/agent-runtime/tests/test_auth_cli.py`
- Modify: `native/atlas-core-rs/crates/atlas-gateway/src/lib.rs`
- Modify: `native/atlas-core-rs/crates/atlas-gateway/tests/api.rs`

- [x] Add a failing Python CLI test:

```python
def test_auth_add_stdin_reads_secret_without_prompt_or_argv(...):
    secret = "stdin-only-secret-9876"
    result = runner.invoke(
        app,
        ["auth", "add", "openrouter", "--stdin", "--source", "gateway"],
        input=secret + "\n",
    )
    assert result.exit_code == 0
    assert secret not in result.output
    assert auth_service.resolve_secret("openrouter") == secret
```

- [x] Run the focused test and confirm RED because `--stdin` is absent.
- [x] Implement `--stdin` using `sys.stdin.readline()`; keep the default hidden prompt. Do not add
  an API-key argv option. Restrict `--source` to stable values and keep audit output metadata-only.
- [x] Add a failing Rust route test for `POST /v1/auth/providers` whose stub asserts the secret is
  present on stdin and absent from `sys.argv`, then emits masked JSON.
- [x] Run the focused cargo test and confirm RED because the route/helper is absent.
- [x] Implement `dispatch_atlas_raw_with_stdin` with piped stdin, timeout, killed-on-drop child,
  bounded secret length, and structured error parsing. Dispatch:
  `atlas auth add <provider> --stdin --source gateway [--base-url ...]`.
- [x] Run focused Python and Rust tests, then the full agent-runtime and gateway suites.
- [x] Commit the auth/gateway contract atomically and update STATE.

## Task 4: P7 Go control-plane client (TDD)

**Files:**
- Modify: `services/atlas-tui/internal/client/types.go`
- Modify: `services/atlas-tui/internal/client/client.go`
- Modify: `services/atlas-tui/internal/client/client_test.go`

- [x] Write failing httptest cases for:
  `GET /v1/config`, `PATCH /v1/config`, `GET /v1/models`,
  `POST /v1/auth/providers`, `POST /v1/auth/codex/import`,
  and `POST /v1/missions/{id}/archive`.
- [x] Confirm RED for missing methods.
- [x] Implement only typed HTTP adapters:

```go
func (c *Client) Config(ctx context.Context) (ConfigSnapshot, error)
func (c *Client) PatchConfig(ctx context.Context, expected int64, changes map[string]any) (ConfigSnapshot, error)
func (c *Client) Models(ctx context.Context) ([]ModelEntry, error)
func (c *Client) StoreAPIKey(ctx context.Context, provider, secret, baseURL string) (AuthStatus, error)
func (c *Client) ImportCodex(ctx context.Context) (CodexImportResult, error)
func (c *Client) ArchiveMission(ctx context.Context, missionID string) error
```

- [x] Keep validation and routing policy out of Go. Decode structured gateway errors into an error
  type with status/code/remediation for display.
- [x] Run `go test ./internal/client -v`, then `go test ./...` and `go vet ./...`.

## Task 5: P7 provider/settings pane and probe (TDD)

**Files:**
- Create: `services/atlas-tui/internal/tui/settings.go`
- Create: `services/atlas-tui/internal/tui/settings_test.go`
- Modify: `services/atlas-tui/internal/tui/model.go`
- Modify: `services/atlas-tui/internal/tui/theme.go`
- Modify: `services/atlas-tui/README.md`

- [x] Write failing state-machine tests for opening settings (`s`), selecting all four modes,
  mode-specific required fields, masked API-key input, freellmapi privacy warning, optimistic config
  save, conflict remediation, and escape without mutation.
- [x] Confirm RED before implementation.
- [x] Implement the leanest form using the already-present Bubbles module (`textinput` adds no new
  dependency). Current-provider fields only:
  provider, model, base URL, optional API key. Named profiles and per-function bindings remain PM-04.
- [x] For `oauth_import`, invoke Codex import before config patch. For `api_key`, store the secret
  over the stdin-backed auth route and patch only references/non-secret fields. For
  `claude_code`/`freellmapi`, patch the current provider fields only.
- [x] Write failing tests for `ctrl+t` probe: create a clearly titled probe mission, start a native
  run, stream it, report live/mock/failure from audit frames, then archive the terminal mission.
- [x] Implement the probe using existing mission/run/SSE/archive endpoints. Do not add a second
  probe engine in Go; PM-05 will later centralize `POST /v1/provider/test`.
- [x] Add 80x24 and 140x40 settings render tests in ASCII and Unicode modes.
- [x] Run all Go tests/vet/build, record binary size, and perform one local mock-mode probe.
- [x] Commit P7 atomically and update STATE.

## Task 6: P8 launcher, installer, and rollback (TDD)

**Files:**
- Create: `services/agent-runtime/atlas_runtime/cli/go_tui.py`
- Create: `services/agent-runtime/tests/test_go_tui_launcher.py`
- Modify: `services/agent-runtime/atlas_runtime/cli/main.py`
- Modify: `services/agent-runtime/tests/test_tui_app_entry.py`
- Modify: `scripts/install-atlas-cli.ps1`
- Modify: `scripts/setup.sh`
- Modify: `services/atlas-tui/.gitignore`
- Modify: `services/atlas-tui/README.md`

- [x] Write failing launcher tests for resolution order:
  `ATLAS_TUI_BIN` → `ATLAS_HOME/bin/atlas-tui[.exe]` → source-checkout build output → PATH.
- [x] Write failing tests that bare `atlas` and `atlas tui` call the Go launcher, while a hidden
  `dev-rich-tui` command still calls `run_workbench` as a dated rollback.
- [x] Confirm RED.
- [x] Implement a subprocess launcher with argv arrays only, inherited TTY, forwarded gateway URL,
  clean missing-binary remediation, and no shell.
- [x] Update PowerShell/bash installers to build Go into `ATLAS_HOME/bin`; replace the obsolete
  foundation npm TUI build step. Gracefully skip only when Go is absent and print the exact
  remediation.
- [x] Verify PowerShell parses, `bash -n scripts/setup.sh`, Python launcher tests, Go tests/vet/build,
  and a real TTY launch against the local gateway.
- [x] Measure cold launcher time, idle memory, and binary size; record the baseline in README/STATE.
- [x] Commit P8 atomically and update STATE. Do not delete the Rich implementation until 10.8.

## Task 7: Return to the active milestone

**Files:** generated by the normal GSD workflows under `.planning/phases/10.7-*` and `10.8-*`.

- [x] Re-run `gsd-sdk query roadmap.analyze`; confirm the next active phase is 10.7.
- [ ] Execute 10.7 discuss → UI contract → plan → implementation → review → verification.
- [ ] Execute 10.8 conformance/UAT/cutover. This is where the hidden Rich rollback is either removed
  or retained with an explicit dated exception based on evidence.
- [ ] Run milestone audit; do not archive v1.1 while human validation or conformance gaps remain.
- [ ] Only after v1.1 archive, activate the corrected v1.2 PM-01–PM-07 roadmap.

## Final verification matrix

| Surface | Command/evidence |
|---|---|
| Python runtime | `.venv/Scripts/python -m pytest services/agent-runtime/tests -q` |
| Rust gateway | `cargo test -p atlas-gateway` |
| Go TUI | `go test ./... && go vet ./... && go build ./...` |
| PowerShell installer | PowerShell parser + focused build block test |
| POSIX installer | `bash -n scripts/setup.sh` |
| Branch hygiene | `git diff --check`; no secret values; no edits under `foundation/atlas-hermes` |
| Runtime budget | Go binary <15 MiB; launcher startup/memory recorded; no new dependency |
| Operator UAT | all four modes can be selected; available modes can save and fire a probe; mock/live/failure shown honestly |
