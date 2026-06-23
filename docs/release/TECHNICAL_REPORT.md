# ATLAS v0.1 — Technical Report (Open Research Preview)

> **Status: ATLAS v0.1 — Open Research Preview.** Not production-ready,
> enterprise-ready, fully autonomous, self-improving, or secure for sensitive data.
> This is an honest early preview for developer technical critique.

**DRAFT — prepared by the build process; the operator reviews and publishes.**

## 1. What ATLAS is

ATLAS is an auditable AI agent **cockpit + runtime** for developers and power users. It
evolves the MIT-licensed Hermes Agent into an ATLAS-branded foundation
(`foundation/atlas-hermes/`, see `ATTRIBUTION.md`) and layers mission control, an
audit-first event bus, policy, an LLM Wiki, a memory router, a model router, a Rust API
gateway, and a web cockpit around it.

Core thesis: **every autonomous action is accounted for.** State is SQLite (WAL + FTS5);
every mutation flows through one CLI contract and emits an `audit_event`.

## 2. Architecture

```
React cockpit (web-ui-react, static SPA)
        │  fetch / EventSource → 127.0.0.1:8484
        ▼
atlas-gateway (Rust, axum + rusqlite)   D-022: reads = direct SQLite, writes = dispatch `atlas` CLI
        ▼
atlas-runtime (Python: mission/run/audit/policy/wiki/memory/router/tools)
        ▼
SQLite (missions, runs, audit_events, artifacts, wiki + vec, model_registry, tool_approvals)
```

- **Read path:** gateway queries SQLite directly (cheap, synchronous).
- **Write path:** gateway shells the `atlas` CLI — the single audited, policy-checked
  mutation contract (D-022). The UI never writes SQLite directly.
- **Live path:** runs emit `audit_events`; the gateway streams them over SSE on a rowid cursor.

Key decisions (full ADR set, D-001…D-024, in `.planning/STATE.md` / `docs/decisions/`):
audit-first runtime (D-002), SQLite/WAL/FTS5/sqlite-vec datastore (D-003), Rust-first
cementation with budgets (D-022), Hermes-as-evolved-foundation not wrapper (D-018), React
cockpit pivot (D-023).

## 3. What v0.1 demonstrates

| Capability | Surface |
|------------|---------|
| Mission control + run lifecycle | `atlas mission` / cockpit Missions, Mission detail |
| Live audit stream | SSE `/v1/runs/{id}/stream` / cockpit Run detail + Ledger |
| Artifact persistence | `artifacts` table / per-run |
| LLM Wiki (Codex) | FTS5 + sqlite-vec semantic, provenance / cockpit Codex |
| Memory router | budget-aware, secret-redacted brief assembly |
| Model registry + task-class routing (D-017) | `/v1/models` / cockpit Models |
| Extensible tool harness (Manifest v0) | manifest + adapter, policy chokepoint / cockpit System |
| Approval-gated writes | `tool_service` TOCTOU-safe propose→approve→execute |
| Golden workflows | Repo Triage, Research Brief, approval-gated Self-Review |
| Integrations posture board | gateway/tools/channels/Discord/cashflow/modules |

## 4. Safety & policy model

- **Read-only by default.** A tool's `risk_level` decides execution: `read` auto-runs;
  `write`/`shell` land as a **pending approval** and never execute without an explicit
  operator decision. Proven by the golden Self-Review test (exactly-N pending, zero inline writes).
- **No sensitive data stored.** Credentials are `env:VAR` references; tool args/results are
  redacted once at the audit boundary before any row is written.
- **SSRF-guarded** outbound HTTP (loopback/private/link-local/reserved blocked, GET-only,
  size-capped); **workspace-boundary-gated** filesystem access.

## 5. Evaluation & quality gate

- **Test suites:** agent-runtime ~369 passing (1 known optional-SDK env skip), atlas-core 52,
  Rust gateway green, cockpit `tsc -b` + `vite build` + eslint green.
- **Golden-workflow quality gate:** `pytest tests/test_golden_workflows_smoke.py` runs each
  of the 3 workflows 3× under deterministic mock-mode conditions and asserts *structure*
  (artifacts/audit/wiki present; Self-Review yields exactly-N pending approvals, no inline
  write). This is the mechanism behind "ATLAS survives repeated demos."
- **Demo-reset:** `atlas golden reset` (dry-run by default) scopes cleanup to golden-tagged
  rows only, proven non-destructive to real operator data by a differential test.

## 6. Known limitations

See [`docs/known-failures.md`](../known-failures.md). In short: live-LLM output is
non-deterministic by nature (mock mode is the demo-stable path); cockpit screenshots are
operator-UAT-captured; no `web_fetch`-backed Research Brief variant yet; not hardened for
sensitive data.

## 7. Build metrics (at v0.1 prep)

- 392 commits total; ~104 on the v1.0.5 wedge.
- 171 Python modules, 11 Rust files, 17 cockpit routes, 13 SQL migrations.
- 5 developer tools shipped (workspace/github/web_fetch/webhook_notify/golden_review_write).
- 32 logged architecture decisions (D-001…D-024 + impl notes).

## 8. Reproducing

`docs/INSTALL.md` (clone → `setup` → `atlas up` → `atlas doctor`), zero credentials for Mock
Mode. Golden-workflow demo: `docs/golden-workflows.md`.
