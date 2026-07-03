# Finish Mission — Analysis, Problem Inventory & Execution Order

**Captured:** 2026-07-03
**Scope:** multi-session mission to finish v1.1 + finish-sprint (deadline 2026-07-09).
**Companion docs:** `2026-07-03-sprint-to-2026-07-09-milestone-finish.md` (sprint contract),
`2026-07-03-mimo-donor-tui-refactor-plan.md` (main task), 
`docs/architecture/OMNI_SURFACE_WIRING_STRATEGY.md` (wiring law),
`.planning/reports/handoff-roadmap-consistency-review-2026-07-03.md` (session-start audit).

## Operator task list (2026-07-03) mapped to workstreams

| # | Operator task | Workstream | Priority |
|---|---------------|------------|----------|
| 1 | TUI refactor with MiMoCode donor | WS-A (STAGE 1→3) | **First — main task** |
| 2 | Installation package (npm, updates) | WS-B | High |
| 3 | CLI polish (intuitive commands, fallbacks, help) | WS-C | High |
| 4 | `atlas up` doesn't boot full infra; model fetch should "just work" via gateway | WS-D | High |
| 5 | TUI caching (pages slow that could be cached) | WS-E | Medium (may be absorbed by WS-A if atlas-terminal replaces Go TUI) |
| 6 | Full connection between all surfaces | WS-F | Continuous law (OMNI strategy doc) |
| 7 | Cashflow interactivity/plug-and-play | WS-G | Document only this sprint |

## WS-A — MiMo donor TUI refactor (MAIN, finish first)

State: STAGE 0 committed 2026-07-03 (`services/atlas-terminal`, adapter skeleton, 5 bun
tests, smoke boot LIVE against :8484). Staged plan in the donor refactor doc.

STAGE 1 contract work (next):
- Donor TUI's only backend seam is `createOpencodeClient({ fetch })` + `sdk.global.event`
  SSE. Donor SDK v2 client + `openapi.json` (445 KB) define the endpoint surface.
- Map: `session.create/list/messages/prompt` → `/v1/surface-sessions` + `/v1/missions` +
  `/v1/missions/{id}/run` + `/v1/runs/{id}/stream`; `permission.*` → `/v1/tools/approvals`
  (+ owner-token claim); SSE bridge ATLAS SurfaceEvents → donor `message.part.updated`,
  `session.status`, `permission.asked` et al.
- Reuse the Go TUI's SSE conformance fixtures for bridge replay tests.

STAGE 2: wholesale copy of `packages/opencode/src/cli/cmd/tui` (~180 files / 28k LOC,
SolidJS + OpenTUI) + vendored sdk v2 types/client + identity scrub + boundary-scanner
extension. STAGE 3: parity audit vs Go TUI + operator UAT + retirement gate.

## WS-B — Installation package

Today: `scripts/install-atlas-cli.ps1` (Windows venv + `atlas.cmd` shim) and
`scripts/setup.sh` (POSIX). Both are source-checkout installers; no versioned artifact,
no update path, no uninstall.

Reality constraint: the product spans Python (runtime), Rust (gateway binary), Go (TUI),
Bun (atlas-terminal, future), Node (freellmapi/discord sidecars, external). A pure npm
package cannot carry this; viable options:

1. **npm wrapper + platform artifacts** (recommended): `npm i -g @l2/atlas` installs a
   thin launcher that downloads/verifies a versioned release bundle (gateway exe, TUI exe,
   python wheel or pinned venv bootstrap) into `~/.atlas`; `atlas update` re-fetches;
   `atlas doctor` validates. Mirrors how modern CLIs ship (opencode/MiMo do exactly this
   via npm + bun-compiled binaries).
2. Per-OS installer scripts only (status quo + versioning) — cheapest, no npm story.
3. Full binary compile (PyInstaller etc.) — high risk with the vendored Hermes foundation.

Deliverables per sprint contract: install, update, uninstall/rollback, doctor, clean-machine
docs, versioned artifact.

## WS-C — CLI polish (inventory findings, 2026-07-03)

Full inventory: ~20 groups / ~100 commands (agent survey; cited against
`atlas_runtime/cli/`). Key defects to fix:

1. **`--json` coverage is uneven**: mission/focus/goal/task/observe/gateway/cashflow/db
   have none; tools/discord/surface/golden/provider are complete. Standard: every
   read command gets `--json`; every mutating command gets structured result output.
2. **Error contract drift**: tools/discord/surface use structured
   `{error:{code,message,remediation}}`; auth/config/models echo raw strings; some paths
   can emit bare tracebacks (e.g. unguarded import in `cli/tui.py:49`).
3. **Naming drift**: `purge-archived` hyphenation vs verb-only convention; `config json`
   vs `config show`; `channels status` vs `channels gateway status` confusion.
4. **Discoverability**: bare `atlas` launches the TUI (correct product choice) but there is
   no `atlas help` alias; group invocation without subcommand should print group help
   (`no_args_is_help` per group); no command aliases for common flows.
5. **Wiki group silently disappears** when `atlas_wiki` is missing (ImportError → pass) —
   should surface an explanatory stub.

## WS-D — `atlas up` completeness + model fetch

- `atlas up` (`cli/main.py:961-974`) boots gateway (:8484, 15 s health poll) + cockpit
  preview (:5173) only, sequentially, no transitive dependency (cockpit "succeeds" even
  if gateway failed). It does NOT start/probe: freellmapi (:3001), cashflow (:3000),
  discord sidecar (:8081), messaging gateway — each has its own `start/status/stop` with
  independent `~/.atlas/*.json` state files and `poll_seconds=0` (fire-and-forget, no
  readiness wait).
- **Stale gateway binary is not detected**: source-staleness detection exists for the Go
  TUI (`go_tui.py:47-51`) but `atlas up`/`doctor` never compare the running gateway
  binary against sources — the single most recurring failure mode in STATE.md history.
- `atlas doctor` (`cli/doctor.py:23-112`) checks db/config/gateway/cockpit (fail) +
  provider/claude-code (informational); it does not cover sidecars, model registry
  freshness, or binary staleness; no `--json`.
- Model fetch: `atlas models refresh` targets the **LLM gateway** (freellmapi,
  `DEFAULT_GATEWAY_URL = http://127.0.0.1:3001/v1`, `model_registry.py:33`), which
  requires a bearer key. Fixed 2026-07-03 by auto-wiring the sidecar's `unified_api_key`
  (`freellmapi_control.get_api_key()`); ATLAS gateway `/v1/models/refresh` now dispatches
  successfully after the :8484 binary rebuild.
- Remaining gap: the registry only learns freellmapi models; codex/claude/api-key
  provider catalogs come from static config. A provider-mesh-wide refresh is v1.2
  territory — document, don't build this sprint.
- Direction per OMNI strategy: `atlas up` should become the one-command boot of the full
  local topology (gateway [with staleness check] → sidecars per active modules → cockpit),
  each with health probe + remediation, idempotent.

## WS-E — TUI caching (inventory findings, 2026-07-03)

Survey of `services/atlas-tui` (agent, file:line cited): **no client-side caching at any
layer** — every view/action is a fresh HTTP request. All fetches are async `tea.Cmd`
(UI never hard-blocks), but perceived slowness comes from:

1. **Settings open (worst):** ctrl+p fires `GET /v1/config` then `GET /v1/models`
   **sequentially** (`settings.go:233-237`) and re-fetches on every open — parallelize +
   cache models with short TTL.
2. **Settings save:** StoreAPIKey/ImportCodex → PatchConfig sequential chain
   (`settings.go:269-306`); auth failure silently prevents the patch.
3. **Probe:** CreateMission → StartRun sequential (`settings.go:311-333`).
4. **Idle polling:** heartbeat + approvals + surface-events every 4 s
   (`model.go:475-484`) ≈ 18 req/min with no conditional requests.
5. Mission select does an extra `GET /v1/missions/{id}` for latest-run resolution
   (`model.go:884`, `286-291`).

Decision: apply only the cheap, high-yield fixes to the Go TUI (parallelize settings
load; TTL-cache /v1/models and provider modes; keep polling as-is); real caching
architecture belongs to the donor adapter in WS-A (the donor already ships a sync/store
layer with optimistic caching).

## WS-F — Omni-surface wiring

Law captured in `docs/architecture/OMNI_SURFACE_WIRING_STRATEGY.md`. Standing checks:
- No surface shells out to donor CLIs; no env-var side channels.
- Config changes propagate to all surfaces without restart (revisioned PATCH already in
  place; TUI/Discord must re-read per interaction or subscribe).
- Sessions/missions visible across surfaces (surface-session protocol is the substrate).
- Flag carried from consistency review: `freellmapi status` returns the sidecar api_key
  cleartext (local-only convenience; diverges from masked-secret contract — operator to
  ratify or revert).

## WS-G — Cashflow (document only)

Current state: vendored Next.js app, ATLAS-branded, gateway launcher handoff
(`/cashflow/full`), 15/15 route smoke, spacing root cause fixed (2026-07-03). It is
effectively **read-only**: no plug-and-play connectors feed it live spend data.
Desired (post-sprint): connector model where paid API usage (e.g., OpenRouter spend)
flows into cashflow automatically — a "plug" per provider with usage polling → expense
entries, and the same connector dynamic for other modules/pages. Requires: connector
registry, per-connector auth, idempotent ingestion (no duplicate expenses on retry),
and a cockpit "connect" UX. Captured as v1.2 candidate; NOT this sprint.

## Execution order (multi-session)

1. **WS-A STAGE 1** — adapter chat loop (sessions/prompt/SSE/permissions). ← current
2. **WS-A STAGE 2** — donor tree copy + scrub + boundary scan.
3. **WS-A STAGE 3** — parity audit + operator UAT gate.
4. **WS-D** — `atlas up` full-topology boot + doctor deepening.
5. **WS-C** — CLI polish pass (json/error/naming/discoverability).
6. **WS-B** — installer/package path (needs WS-A outcome to know what ships).
7. **WS-E** — TUI caching decision (Go TUI patch vs atlas-terminal adoption).
8. Sprint acceptance sweep vs `2026-07-03-sprint-...-milestone-finish.md` acceptance bar.

Each session: verify continuation state first (l2-handoff-verifier), execute scoped work,
re-run gates (agent-runtime pytest, cockpit tsc/lint/test/build, Go test/vet, bun test),
update STATE.md + HANDOFF.md before stopping.
