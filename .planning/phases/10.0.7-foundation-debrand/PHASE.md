# Phase 10.0.7 — Foundation De-brand (Hermes → ATLAS, with ethical attribution)

> Status: **planned** (insert into ROADMAP via `/gsd-phase`; sequence **before** 10.0.6 public
> release — shipping upstream branding publicly is the trigger to resolve first).
> Owner concern: foundation/runtime, not the UI. Gate: the foundation test suite stays green.

## Intent

ATLAS is built on a **vendored** copy of the Hermes agent (MIT), at `foundation/atlas-hermes/`
(D-018 / D-021). The foundation has diverged enough that it is ATLAS's own runtime, not stock
Hermes (we "do not route through stock Hermes; foundation transformation, not wrapper"). This phase
**removes Hermes as the product brand** from the vendored tree — folders, package names, imports,
CLI name, user-facing strings, docs — **while fully retaining attribution** as MIT requires and as
ethics demands. Hermes is no longer the name of our thing; it remains **credited** as the origin.

This is a de-branding + internal-rename refactor. It changes **no behavior**.

## Scope

**In scope — `foundation/atlas-hermes/` (tracked, vendored):**
- Python distribution: `name = "hermes-agent"` → an ATLAS name (e.g. `atlas-foundation`); update all
  `[project]` metadata, optional-dependency extras (`hermes-agent[cli]` → `atlas-foundation[cli]`),
  `MANIFEST.in`, `egg-info`.
- Package/module dirs: `hermes_cli/` → `atlas_foundation_cli/` (or `atlas_cli`), and any other
  `hermes_*` packages; update **every import** across `agent/`, `tools/`, `acp_*`, `plugins/`, tests.
- CLI command name `hermes` → `atlas-foundation` (or fold under the existing `atlas` CLI); console
  entry points; `cli-config.yaml.example`.
- Runtime/infra strings: `docker/s6-rc.d/main-hermes`, `.github/actions/hermes-smoke-test`,
  Dockerfile labels, plugin/skill dir names containing `hermes`.
- User-facing strings: banners, help text, log prefixes, READMEs, dashboard titles.

**Explicitly OUT of scope (retain, do not touch):**
- `LICENSE` (MIT) — retained verbatim; required.
- `ATTRIBUTION.md` — **expanded**, not removed: clear statement that this foundation is *derived from
  Hermes (MIT), © original authors*, with a link/commit SHA. This is the ethics anchor.
- `DIVERGENCE_LOG.md` — append the de-brand as a divergence entry.
- `_EXTERNAL_REPOS/hermes-agent/` — pristine upstream clone; **gitignored already**; the reference
  source for attribution and diffing. Never branded over.
- `.venv/.../hermes_agent-*` — installed artifact; out of scope (rebuilt from the renamed dist).
- Upstream `RELEASE_v*.md` history — keep as provenance, or move to `THIRD_PARTY/hermes-history/`.

## Ethics & license posture (the point of the phase)

- MIT permits rebranding/forking **provided the copyright notice and license text are retained.**
  We retain `LICENSE` and strengthen `ATTRIBUTION.md`. We do **not** claim Hermes' code as
  originally ours; we claim our **divergence** as ours.
- The de-brand is about **product identity** (ATLAS is the product), not erasing credit. After this
  phase, "Hermes" appears in the repo **only** in `ATTRIBUTION.md`, `DIVERGENCE_LOG.md`, `LICENSE`/
  notices, and `THIRD_PARTY/` — i.e. exclusively where it credits the origin. Grepping `hermes`
  outside those files returns nothing in the vendored tree.
- Release blockers already logged (D-008): quarantine `red-teaming/godmode` + `inference/obliteratus`
  from the vendored default tree before public distribution; `l2-mind`/`vault-scan` never ship. Fold
  these quarantines into this phase since it already walks the whole vendored tree.

## Approach (mechanical, test-gated)

1. **Freeze a baseline:** run the foundation test suite; record green baseline + a `hermes` grep
   census (counts per dir) as the burn-down metric.
2. **Rename in dependency order**, one unit per atomic commit, suite green after each:
   a. dist metadata + entry points → b. top-level `hermes_*` package dirs → c. imports (codemod:
   `hermes_cli` → new name, repo-wide, AST-aware where possible) → d. infra (docker/s6, CI actions)
   → e. user-facing strings/docs.
3. **Attribution pass:** expand `ATTRIBUTION.md`, append `DIVERGENCE_LOG.md`, add `THIRD_PARTY/` if
   moving upstream release notes.
4. **Quarantine pass:** remove/gate the D-008 release-blocker skills from the default tree.
5. **Verify:** suite green; `grep -ri hermes foundation/atlas-hermes` returns only attribution/
   license/third-party files; gateway + cockpit boot via the local-run recipe (the gateway shells the
   `atlas` CLI — confirm the renamed foundation CLI contract still satisfies it).

## Risks & mitigations

| Risk | Mitigation |
|---|---|
| Import rename breaks the running foundation (ATLAS depends on it) | Atomic per-unit commits; foundation test suite is the hard gate after each; codemod + grep census burn-down to zero |
| Gateway↔CLI contract breaks (writes dispatch the CLI) | The gateway calls the `atlas` CLI, not `hermes` directly (D-022); verify the dispatch path + run a create-mission round-trip post-rename |
| Hidden dynamic imports / string-built module paths | grep for string `"hermes"` import patterns + `importlib` usage before declaring done |
| Accidentally stripping required attribution | Attribution/license files are explicitly out-of-scope and tested by the "only-here" grep gate |
| Entry-point / packaging drift (extras renamed) | Rebuild the dist into the venv and re-run a smoke install |

## Acceptance

- Foundation test suite green (same count as baseline).
- `grep -ri hermes foundation/atlas-hermes` → matches **only** in `ATTRIBUTION.md`,
  `DIVERGENCE_LOG.md`, `LICENSE`/notices, `THIRD_PARTY/`.
- `ATTRIBUTION.md` clearly credits Hermes (MIT) as the origin with SHA; `DIVERGENCE_LOG.md` records
  the de-brand.
- Gateway + cockpit boot; a create-mission → run round-trip works through the renamed foundation CLI.
- D-008 release-blocker skills quarantined from the default vendored tree.

## Notes

- This phase is a prerequisite for **10.0.6 public release / distribution** (cannot publish under, or
  leaking, upstream branding). Recommend inserting as **10.0.6-pre** or resequencing 10.0.6→10.0.7.
- Pure de-brand: **no behavioral change**. If behavior must change, that is a different phase.
