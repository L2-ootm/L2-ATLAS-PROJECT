# Next Plausible Steps

**Written:** 2026-06-22
**Context:** 10.0.4 planning complete, execution pending. 10.0.3 in-flight. 10.0.5–10.0.6 not started.

---

## Phase 10.0.4: Developer Integrations & Tool Manifest

The six plans are committed and plan-checked PASS. Execution order:

| Wave | Plan | What | Key Risk |
|------|------|------|----------|
| 0 | `10.0.4-00-PLAN.md` | Test stubs + temp-DB conftest + confirm audit_event_type TEXT has no CHECK | Wave 0 must go RED before going GREEN. The grep-based verify (W-5 in plan-check) can pass spuriously — use `pytest` exit code, not token grep. |
| 1 | `10.0.4-01-PLAN.md` | `ToolManifest`/`ToolResult`/`ToolApproval` schemas + `AuditEvent` +3 verbs + `policy.decide()` | `ToolManifest` must be `frozen=True` (D-012/Pitfall 5). `policy.decide` is the single chokepoint — if it leaks past a write-class tool, the whole gate is broken. |
| 2 | `10.0.4-02-PLAN.md` | Four adapters (workspace/github/web_fetch/webhook_notify) + manifests + SSRF guard | SSRF is the hardest threat: `_assert_safe` must block RFC1918, loopback, link-local, non-http(s) schemes, and non-GET. Test against 5+ vectors. `gh` must use `subprocess.run([...])` (argv), never `shell=True`. |
| 3 | `10.0.4-03-PLAN.md` | `tool_registry` fail-fast load + `tool_service.invoke()` chokepoint + approval state machine + `0013` migration | TOCTOU claim must use `UPDATE ... SET status='executing' WHERE id=? AND status='pending'` with rowcount==1 — copy Phase C exactly. Redact args once at boundary (SECRET_PATTERNS), never twice. |
| 4 | `10.0.4-04-PLAN.md` | `atlas tools` CLI + gateway `/v1/tools/*` + approvals routes (dispatch-only) | Gateway is dispatch-only (D-022): validate, shell to `atlas`, parse JSON, return. No DB/state in Rust. Empty body must 400. Monkeypatch `_get_connection` in tests — never hit live CLI. |
| 5 | `10.0.4-05-PLAN.md` | System POLICY panel + Tools list + Approvals queue + docs | SC3 is the only non-automatable gate: the read-only badge, risk legend, and no-sensitive-data posture must render as literal strings in the UI. Requires `atlas up` + manual browser verification. |

### Execution Notes

- **pyyaml declaration**: Add `"pyyaml>=6,<7"` to `services/agent-runtime/pyproject.toml` dependencies. It's already installed transitively but not declared — make it supply-chain-honest.
- **conftest fixture**: Reuse Phase C's migration-applying pattern. Apply ALL migrations including `0013_tool_approvals.sql` against a `tmp_path` DB. The `atlas` CLI hits `~/.atlas/atlas.db` regardless of `ATLAS_HOME` — never drive the CLI in unit tests.
- **Wave 0 RED-first**: Write stubs that reference not-yet-existing symbols (ToolManifest, tool_service.invoke, etc.). Confirm they fail. Then implement to make them pass.
- **VALIDATION.md**: Flip `nyquist_compliant: true` / `wave_0_complete: true` after Plan 00 executes. Reconcile the stale Plan 06 reference and wave numbering (W-3 from plan-check).

---

## Phase 10.0.3: Loose Ends

10.0.3 is the identity & cockpit redesign phase. The six-item scope (items 1–5) shipped. Remaining:

| Item | Status | Action |
|------|--------|--------|
| Foundation de-brand hermes→atlas | DEFERRED (item 6) | Dedicated session (~12.9k refs, foundation-locked tree, test-gated). Plan exists at `10.0.7-foundation-debrand/PHASE.md`. |
| UI-SPEC + per-page redesign wave | In-flight, no plans | Brand direction approved, palette tokens + logo system landed, topographic shell redesigned. Per-page redesign not started. ROADMAP shows 0 plans. |
| ROADMAP closure | Not done | 10.0.3 should be marked complete once the per-page wave ships (or explicitly deferred). Currently shows "Not started" in the progress table despite significant work done. |

**Recommendation:** Either close 10.0.3 by deferring the remaining per-page work to a later phase, or finish it before 10.0.5 (golden workflows depend on the cockpit being visually coherent).

---

## Phase 10.0.5: Golden Workflows & Quality Gate

**Depends on:** 10.0.4 (tool integrations must exist for the demo workflows to run).

**What it delivers:** Three golden workflows (Repo Triage, Research Brief, Self-Review) that each run 3 times with consistent output. Sample data, screenshots, known-failures list.

**Pre-conditions to verify before starting:**
1. All four integration adapters from 10.0.4 are wired and callable.
2. `atlas tools invoke` works end-to-end through CLI + gateway.
3. Mock mode is stable (demo workflows will use mock mode for repeatable output).
4. `demo_seed.py` produces enough data to exercise the workflows.

**Risks:**
- "Consistent output" is hard to guarantee with non-deterministic LLM calls — mock mode solves this for demos but real runs won't be deterministic.
- Self-Review workflow must never write without approval — the approval gate from 10.0.4 must be tested in this context.

---

## Phase 10.0.6: Public Release Prep & Distribution

**Depends on:** 10.0.5 (golden workflows must be verified before release).

**What it delivers:** README final, technical report, roadmap, demo assets, repo made public, private beta, launch message.

**Pre-conditions:**
1. `atlas doctor` passes clean on a fresh install.
2. All 10.0.1 trust docs are present and accurate (LICENSE, SECURITY.md, CONTRIBUTING.md, etc.).
3. No secrets in git history (secret scan clean).
4. Docker Compose verified working (still untested — no container engine on dev machine).
5. 10.0.4's human-verify items are confirmed (POLICY panel, GitHub adapter against real repo).

---

## Verification Checklist (Before Each Phase)

### Before 10.0.4 Execution
- [ ] Confirm `pyyaml` importable in runtime venv (`python -c "import yaml"`)
- [ ] Confirm `gh` installed and authenticated (`gh auth status`)
- [ ] Confirm `0012_discord_approvals.sql` is the latest migration (`atlas db status`)
- [ ] Confirm pytest runs clean on full suite before touching anything
- [ ] Confirm gateway binary is built and on PATH

### Before 10.0.5
- [ ] 10.0.4 Plan 05 human-verify checkpoint passed (POLICY panel renders, approval queue works)
- [ ] Mock mode produces deterministic output for all four adapters
- [ ] `demo_seed.py` re-runs idempotently

### Before 10.0.6
- [ ] Secret scan clean (no `.env`, no raw tokens, no credential patterns in committed files)
- [ ] All tests green (Python + Rust + cockpit build)
- [ ] `atlas doctor` passes
- [ ] README quickstart tested from scratch (clone → install → run)
- [ ] 10.0.1 trust docs reviewed against public-release bar

---

## Caution Points

### 1. TOCTOU Race in Approval State Machine
The single most critical pattern. If `tool_service.approve()` does a status check then a separate update, concurrent approve calls can both succeed. **Must** use `UPDATE ... SET status='executing' WHERE id=? AND status='pending'` and check `rowcount == 1`. This is already proven in Phase C `discord_service.py` — copy it verbatim, do not re-invent.

### 2. SSRF Guard Completeness
`web_fetch` and `webhook_notify` both make outbound HTTP. The guard must block:
- Non-http(s) schemes (`file://`, `ftp://`, etc.)
- Loopback (`127.0.0.0/8`, `::1`)
- RFC1918 private ranges (`10.0.0.0/8`, `172.16.0.0/12`, `192.168.0.0/16`)
- Link-local (`169.254.0.0/16`, `fe80::/10`)
- Reserved/special ranges (`0.0.0.0/8`, `224.0.0.0/4`)
- DNS rebinding (resolve, then check IP — not just hostname)

Test with 5+ vectors. A missed range = SSRF vulnerability.

### 3. `gh` Token Safety
The GitHub adapter shells out to `gh` which carries the user's auth. ATLAS must never log, persist, or expose the token. The adapter should capture only stdout/stderr from `gh` commands. Use `subprocess.run([...])` with explicit argv — never `shell=True` (argv injection risk).

### 4. ATLAS_HOME vs Live DB
The `atlas` CLI reads `~/.atlas/atlas.db` regardless of `ATLAS_HOME` env var. All unit tests must inject a temp-DB connection via fixtures. Never run the CLI in a test — it will hit the live database. This is a known antipattern from Phase B (smoke test mutated live DB, had to be hand-restored).

### 5. Migration Ordering
`0013_tool_approvals.sql` must be additive only (CREATE TABLE IF NOT EXISTS). No DROPs, no ALTERs of existing tables. The migration runner tracks applied files — a non-idempotent migration will break existing installs.

### 6. Redaction Boundary
Args and results must be secret-redacted **once** at the `tool_service.invoke()` boundary (using `SECRET_PATTERNS`), not scattered across adapters. If an adapter accidentally logs unredacted args, secrets leak to stdout. The redaction happens before persistence — the audit trail never contains raw secrets.

### 7. Gateway Dispatch-Only
The Rust gateway must never hold tool state, call adapters directly, or read the `tool_approvals` table. It validates the request body, shells to `atlas tools ...`, parses the JSON response, and returns it. If the gateway starts accumulating state, it violates D-022 and creates a second source of truth.

### 8. Frozen Models
`ToolManifest`, `ToolResult`, `ToolApproval` must all be `frozen=True`. Never mutate — construct new instances. Mutating a frozen model raises `ValidationError` at runtime, which is the correct fail-fast behavior.

### 9. pyyaml Declaration
PyYAML is already installed as a transitive dependency but not declared in `pyproject.toml`. Add `"pyyaml>=6,<7"` to make the manifest loader's import explicit. A supply-chain audit will flag undeclared imports.

### 10. Human-Verify Gate (SC3)
Plan 05 is the only non-automatable verification point. The System page must render a literal "READ-ONLY BY DEFAULT" badge, a risk-tier legend, and a "no sensitive data is stored or transmitted by ATLAS" posture statement. These must be visible strings, not derived-only state. Requires `atlas up` + manual browser inspection.

---

## Recommended Execution Order

1. **Push** ✅ (done — 53 commits pushed)
2. **10.0.4 Plan 00** — Wave 0 test stubs (go RED, confirm infrastructure)
3. **10.0.4 Plan 01** — Schemas + policy (go GREEN on stubs)
4. **10.0.4 Plans 02+03** — Adapters + service (parallel if independent, sequential if 03 depends on 02)
5. **10.0.4 Plan 04** — CLI + gateway (dispatch wiring)
6. **10.0.4 Plan 05** — Cockpit UI + docs (human-verify checkpoint)
7. **Close 10.0.3** — Decide: finish per-page wave or defer + mark complete
8. **10.0.5** — Golden workflows (needs 10.0.4 adapters live)
9. **10.0.6** — Public release prep (needs everything green)
