# Milestones

## v1.0 Operator Cockpit MVP (Shipped: 2026-06-15)

**Scope:** 10 phases (incl. decimals 4.5 / 8.5 / 9.5), 32 plans. 34/34 v1.0
requirements complete. Git range `214e3d6` → `caab693`.

**Delivered:** the first closed operator loop — create mission → run through the
ATLAS runtime (built on the vendored Hermes foundation) → capture a structured audit
trail → file artifacts to the LLM Wiki → monitor it all in a web cockpit.

**Key accomplishments:**

- Vendored the Hermes Agent foundation (MIT, v0.14.0, SHA `e8b9369a9…`) into
  `foundation/atlas-hermes/` with ATTRIBUTION + DIVERGENCE_LOG and an authoritative
  extension-surface audit — foundation transformation, not a wrapper (D-018).
- Established the Pydantic v2 domain model + SQLite (WAL/FTS5) schema as the single
  data contract, with an audit-first event bus emitting structured AuditEvents for
  every tool/LLM/subagent/approval/artifact action (D-002, D-003, D-012).
- Shipped the mission/run lifecycle (create / run / cancel / complete, lock-guarded
  state machine) and the LLM Wiki runtime (ingest / update / FTS search / lint /
  provenance) behind a typed `atlas` CLI.
- Built the Rust API gateway (`atlas-gateway`, axum + rusqlite, loopback-only, SSE
  audit stream, CORS allowlist) as the first native crate — 2.5 MB release binary,
  <80 MB idle (D-022).
- Shipped the SvelteKit operator cockpit (adapter-static, native-portable): missions,
  live run monitoring, audit/JSONL export, wiki browser, read-only model registry —
  full loop verified live in-browser (COCKPIT-01..06).
- Classified ~266 skills into Core / Operator / L2 packs (D-008) and ran a v1.0 public
  hardening + assisted manual operator UAT: quarantined unsafe default skills,
  secret/path scans, self-hosted fonts (loopback-only), verdict
  `APPROVED_FOR_V1_ARCHIVE`.

**Known deferred items at close:** Phase 08 `VERIFICATION.md` was `human_needed` and
its UAT flagged open — both are now effectively satisfied by the comprehensive 09.5
manual operator UAT, which exercised every Phase 8 cockpit surface end-to-end.
Non-blocking public-release follow-ups remain in
`docs/operations/PUBLIC_RELEASE_HARDENING.md §4` (path scrub, `.planning/` exclusion,
`atlas db init`, offensive-skill auth gate, CLI `ATLAS_DB`, SPA-fallback hosting).

---
