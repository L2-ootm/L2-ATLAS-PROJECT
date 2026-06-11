# ATLAS Production Repository Structure

Date: 2026-06-11  
Status: proposed structure standard for production launch  
Scope: repository hierarchy, file ownership, and launch-facing organization only

## 1. Context from current scan

The project is now materially wired, not just conceptual. Current relevant state:

- `foundation/atlas-hermes/` exists as the vendored Hermes-derived foundation.
- `foundation/README.md`, `ATTRIBUTION.md`, and `DIVERGENCE_LOG.md` establish the correct posture: evolve the Hermes foundation in-place, never treat it as a black-box wrapper.
- `packages/atlas-core/` contains shared Pydantic/domain contracts.
- `services/agent-runtime/` and `services/wiki-runtime/` contain real runtime work.
- `native/atlas-core-rs/` has started the Rust cementation path.
- `apps/api/` and `apps/web/` exist as target surfaces but are still empty/waiting for Phase 7/8.
- `docs/decisions/`, `docs/architecture/`, `docs/research/`, `docs/imports/`, and `.planning/` are active and valuable, but currently carry some overlap and historical research density.
- `_EXTERNAL_REPOS/` is correctly a local/reference workspace, not production source.

Core correction that must guide naming and hierarchy:

```text
Hermes Agent foundation -> L2/ATLAS enhanced foundation -> ATLAS product/runtime/cockpit
```

Do not describe the final product as routing through stock Hermes. The production repo should make it obvious that Hermes-derived code is an evolved ATLAS foundation substrate, not an external service dependency.

## 2. Design principles for the final production repo

1. **Operator-facing ATLAS first**  
   Top-level structure should communicate ATLAS product/runtime ownership. Hermes provenance must be preserved, but stock Hermes should not dominate the operator-facing hierarchy.

2. **Foundation separated from product modules**  
   The vendored Hermes-derived foundation should live under `foundation/` with strict provenance/divergence controls. ATLAS-specific product logic should live outside it unless the change intentionally evolves the foundation.

3. **Thin top-level, strong domains**  
   Keep the top-level directory count small and meaningful. Avoid dumping every future feature into `services/` without lifecycle boundaries.

4. **Rust-first for new infrastructure**  
   New gateway/daemon/native infrastructure should live in `native/` or Rust crates. Python remains for the Hermes-derived foundation surface, LLM adapter glue, existing runtime integration, and scripts where justified.

5. **Docs split by authority**  
   Decisions are canonical. Architecture explains current target. Research is input. Plans are execution. Operations are runbooks. These should not compete.

6. **Runtime data is not source**  
   Generated DBs, coverage, run artifacts, local caches, external clones, and secrets must stay out of production source control or under ignored runtime paths.

## 3. Proposed final top-level hierarchy

```text
L2-ATLAS-PROJECT/
├─ README.md
├─ AGENTS.md
├─ LICENSES.md
├─ pyproject.toml                 # only if root Python workspace remains needed
├─ Cargo.toml                     # Rust workspace root once native crates become first-class
├─ package.json                   # only if monorepo JS tooling is needed at root
├─ .gitignore
│
├─ apps/
│  ├─ cockpit-web/                # SvelteKit/Svelte 5 static web cockpit, Phase 8
│  ├─ cockpit-native/             # Tauri shell, Phase 10/v1.1
│  └─ admin-console/              # optional later admin/internal ops surface
│
├─ foundation/
│  ├─ atlas-hermes/               # vendored Hermes-derived ATLAS foundation
│  ├─ ATTRIBUTION.md
│  ├─ DIVERGENCE_LOG.md
│  ├─ README.md
│  └─ patches/                    # optional patch snapshots if divergence tracking needs structure
│
├─ crates/
│  ├─ atlas-core-rs/              # Rust domain/contracts once stable
│  ├─ atlas-gateway/              # REST + SSE gateway, Phase 7
│  ├─ atlas-policy/               # policy/capability engine when cemented
│  ├─ atlas-runtime-daemon/       # future daemon/runner core
│  └─ atlas-cli/                  # future Rust CLI once strangling Python CLI is viable
│
├─ packages/
│  ├─ atlas-core/                 # Python shared contracts while Python remains source-of-truth
│  ├─ atlas-sdk/                  # generated/handwritten client SDKs
│  ├─ atlas-config/               # shared config schema, defaults, validation
│  └─ atlas-ui/                   # shared UI primitives/tokens if reused across web/native
│
├─ services/
│  ├─ agent-runtime/              # ATLAS mission/run/audit integration over evolved foundation
│  ├─ wiki-runtime/               # LLM Wiki ingest/update/search/lint service
│  ├─ worker-runtime/             # async jobs/research/imports after needed
│  ├─ pulse-runtime/              # later monitoring/pulse service
│  └─ integration-runtime/        # sidecar adapters/webhooks; not sidecar source code
│
├─ infra/
│  ├─ migrations/                 # SQLite/Postgres migrations, numbered and immutable
│  ├─ compose/                    # dev/test compose files for sidecars only
│  ├─ systemd/                    # Linux service units later
│  ├─ windows/                    # Windows install/service assets later
│  └─ terraform/                  # only if deployment infra becomes real
│
├─ docs/
│  ├─ architecture/               # current architecture specs
│  ├─ decisions/                  # ADRs; highest authority after AGENTS.md
│  ├─ operations/                 # runbooks, setup, release, recovery
│  ├─ product/                    # user-facing product specs, personas, launch scope
│  ├─ research/                   # raw research inputs and comparative audits
│  ├─ imports/                    # intake notes from donor/reference systems
│  ├─ qa/                         # validation reports, audit reports, test evidence
│  └─ plans/                      # implementation/stabilization plans
│
├─ wiki/
│  ├─ index.md
│  ├─ log.md
│  ├─ raw/                        # raw ingested source copies, if allowed for repo
│  ├─ entities/
│  ├─ concepts/
│  ├─ comparisons/
│  └─ queries/
│
├─ scripts/
│  ├─ dev/
│  ├─ audit/
│  ├─ release/
│  └─ maintenance/
│
├─ tests/
│  ├─ contract/                   # schema/API compatibility tests
│  ├─ e2e/                        # full loop tests
│  ├─ integration/
│  └─ fixtures/
│
├─ tools/
│  └─ local/                      # developer-only helpers that are still source-controlled
│
└─ .planning/                     # GSD planning state; keep for active development, exclude from public release bundle if needed
```

## 4. What should change from the current structure

### 4.1 Rename `apps/api/` to a clearer target

Current:

```text
apps/api/
apps/web/
```

Recommended:

```text
apps/cockpit-web/
crates/atlas-gateway/
```

Reason: D-022 makes Phase 7 gateway Rust-first. The API gateway should not look like a generic web app. `apps/` should be user-facing applications; Rust gateway belongs in `crates/` or `native/`.

### 4.2 Promote Rust crates from `native/atlas-core-rs/crates/` to top-level `crates/`

Current:

```text
native/atlas-core-rs/crates/...
```

Recommended final:

```text
crates/atlas-gateway/
crates/atlas-core-rs/
crates/atlas-policy/
crates/atlas-runtime-daemon/
```

Reason: Rust is not just a native desktop adjunct anymore. D-022 makes Rust the cementation path for infrastructure. `native/` should become the desktop/native packaging layer, not the home of all Rust.

Transition option: keep current layout until Phase 7 compiles, then move before Phase 8 begins.

### 4.3 Keep `foundation/atlas-hermes/` exactly explicit

This is good as-is.

Production rules:

- Never collapse it into generic `vendor/` without preserving meaning.
- Never mix ATLAS product services inside `foundation/atlas-hermes/` unless the change intentionally evolves the foundation.
- Every change requires `foundation/DIVERGENCE_LOG.md` entry.
- Keep `foundation/ATTRIBUTION.md` close to the vendored tree.

### 4.4 Split docs by authority and reduce duplicated strategic language

Recommended authority order:

1. `AGENTS.md` — local operating constraints.
2. `docs/decisions/` — canonical decisions.
3. `docs/architecture/` — current target architecture.
4. `.planning/` — execution state and phase plans.
5. `docs/research/` and `docs/imports/` — inputs, not current truth by default.

Production cleanup should add a short `docs/README.md` explaining this order.

### 4.5 Move generated artifacts out of the source surface

Current root has generated or local files:

```text
.coverage
coverage.json
coverage_branch.json
services/*/.coverage
services/wiki-runtime/coverage.json
```

Recommended:

```text
artifacts/coverage/             # ignored by git
artifacts/runs/                 # ignored by git
artifacts/reports/              # ignored unless intentionally committed under docs/qa
```

For committed evidence, use:

```text
docs/qa/YYYY-MM-DD_<scope>_VALIDATION.md
```

### 4.6 Keep `_EXTERNAL_REPOS/` local-only

`_EXTERNAL_REPOS/` is useful for diffing and audits, but should remain ignored and absent from production release bundles.

If a reference becomes authoritative, capture it as:

```text
docs/imports/<SYSTEM>_INTAKE_<DATE>.md
docs/research/<SYSTEM>_AUDIT_<DATE>.md
```

Not by relying on the local clone.

## 5. Recommended production module boundaries

### 5.1 Foundation

Owns:

- agent loop inherited/evolved from Hermes;
- provider/model plumbing inherited/evolved from Hermes;
- tools/toolsets;
- skills substrate;
- gateway/channel substrate;
- session/memory/delegation/cron substrate;
- operator-facing rebrand where it belongs in the foundation.

Does not own:

- ATLAS product-specific mission semantics unless intentionally inserted as a foundation extension;
- cockpit UI;
- sidecar source code;
- CRM business objects.

### 5.2 Agent runtime

Owns:

- mission lifecycle;
- run lifecycle;
- audit event emission;
- policy enforcement;
- foundation integration plugin(s);
- artifact capture;
- CLI surface while Python CLI remains active.

Should expose contracts to Rust gateway rather than becoming a long-term Python service monolith.

### 5.3 Wiki runtime

Owns:

- source ingest;
- wiki page update;
- FTS/semantic search;
- provenance;
- contradiction/staleness linting;
- markdown output under `wiki/`.

Should not become the general memory system. It is Layer 2/3, not all six memory layers.

### 5.4 Gateway

Owns:

- REST API;
- SSE event stream;
- read-only/direct SQLite query where appropriate;
- command boundary to runtime where writes must preserve audit/policy;
- browser cockpit contract.

D-022 direction: Rust `axum + rusqlite`, not FastAPI.

### 5.5 Cockpit web

Owns:

- mission list/detail/create;
- run timeline;
- live audit stream;
- wiki browser/search;
- provider/model read-only settings panel for v1;
- static/native-portable build constraints.

Should not own business logic or direct database writes.

### 5.6 Sidecar adapters

Own:

- stable ATLAS-branded adapter boundary;
- config for Twenty/FreeLLMAPI/etc.;
- health checks;
- webhook intake;
- audit event mapping.

Do not own upstream sidecar code or rebranding.

## 6. Minimal launch-facing file set

For production launch, the repo should make the following files easy to find:

```text
README.md                         # product + quickstart
AGENTS.md                         # local agent/operator rules
LICENSES.md                       # license map, including Hermes MIT attribution
foundation/ATTRIBUTION.md
foundation/DIVERGENCE_LOG.md
docs/README.md                    # docs authority map
docs/architecture/OVERVIEW.md     # one canonical architecture overview
docs/decisions/INDEX.md           # ADR index
docs/operations/INSTALL.md
docs/operations/RUNBOOK.md
docs/operations/RELEASE.md
docs/operations/SECURITY.md
docs/qa/VALIDATION_INDEX.md
infra/migrations/README.md
wiki/index.md
```

The current repo already has many of the ingredients. The missing production polish is mostly indexing, authority cleanup, artifact hygiene, and clearer app/crate naming.

## 7. Concise final hierarchy recommendation

If forced to choose one final shape, use this:

```text
apps/          user-facing UI shells only
crates/        Rust gateway, daemon, policy, native core, CLI
foundation/    Hermes-derived ATLAS foundation with attribution/divergence
packages/      shared Python/TS/config/UI packages while needed
services/      ATLAS product runtimes that still live outside Rust crates
infra/         migrations, compose, deployment/service assets
docs/          architecture, ADRs, ops, QA, product, research
wiki/          first-class compiled knowledge base
scripts/       deterministic maintenance/dev/release scripts
tests/         cross-package contract/integration/e2e tests
.planning/     active GSD execution state, not product surface
```

This keeps the production story clean:

> ATLAS is an L2-owned operator cockpit/runtime built by evolving the Hermes Agent foundation into an ATLAS-branded harness, then adding mission, audit, policy, wiki, memory, router, gateway, and cockpit layers around that evolved foundation.

## 8. Immediate documentation/cleanup recommendations

Do these before launch hardening:

1. Add `docs/README.md` with authority order and folder purpose.
2. Add `docs/decisions/INDEX.md` listing D-001 through D-022 with status.
3. Add `docs/architecture/OVERVIEW.md` as the single short architecture overview.
4. Decide whether Rust crates move to top-level `crates/` before or after Phase 7 compiles.
5. Rename `apps/web` to `apps/cockpit-web` before implementation begins.
6. Keep `apps/api` empty or remove it once `crates/atlas-gateway` is canonical.
7. Add ignored `artifacts/` for coverage/runs/reports and remove root coverage files from tracked source.
8. Patch remaining phrasing that says “run through enhanced ATLAS/Hermes runtime” into “run through the ATLAS runtime built from the evolved Hermes foundation.”

## 9. Non-goals for this structure pass

- Do not reorganize now just for aesthetics.
- Do not move the vendored foundation without a migration plan.
- Do not rename internal Hermes modules in a big bang.
- Do not collapse research/import docs into architecture without ADR review.
- Do not expose `_EXTERNAL_REPOS/`, local caches, or generated artifacts as product surface.
