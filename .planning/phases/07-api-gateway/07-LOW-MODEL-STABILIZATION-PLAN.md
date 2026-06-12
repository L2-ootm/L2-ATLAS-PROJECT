# Phase 7 Low-Model Stabilization Plan

Date: 2026-06-11  
Status: ready for execution by a standard coding model  
Scope: low-risk hygiene/documentation tasks remaining after the high-context stabilization pass

## Purpose

This plan captures the remaining low-complexity cleanup items from the latest stabilization report so they can be executed later without using a top-tier reasoning model.

These tasks are intentionally bounded. They should not change architecture, implement Phase 7 endpoints, move directories, or touch the vendored foundation.

## Context

Latest high-context stabilization report concluded:

- Working tree was clean after audited commits.
- Live architecture documents now align around D-018, D-021, and D-022.
- Phase 7 has a canonical Rust gateway direction.
- Remaining risks are minor and suitable for lower-cost follow-up.

Known remaining risks:

1. Twenty official compose is Docker-targeted. Podman compatibility is unvalidated until a container engine is installed.
2. CRLF warnings are cosmetic but should be prevented with `.gitattributes`.
3. `wiki/raw/` ingestion rules and `docs/qa/VALIDATION_INDEX.md` are missing.
4. Older architecture docs still contain pre-D-022 diagrams/language; they need supersession headers.

## Non-goals

Do not:

- implement Rust gateway endpoints;
- modify `foundation/atlas-hermes/`;
- move `native/atlas-core-rs/`;
- install Podman/Docker;
- run or mutate Twenty;
- rewrite old architecture docs;
- change accepted ADRs;
- modify L2-BOT or Discord state.

## Files to read first

- `AGENTS.md`
- `docs/README.md`
- `docs/architecture/OVERVIEW.md`
- `docs/plans/PHASE_7_8_READINESS.md`
- `.planning/phases/07-api-gateway/CONTEXT.md`
- `docs/operations/TWENTY_LOCAL_SETUP.md`
- `docs/architecture/FOUNDATION_STRATEGY.md`
- `docs/architecture/SYSTEM_OVERVIEW.md`
- `.gitignore`

## Task 1 — Add `.gitattributes`

### Objective

Prevent line-ending churn while preserving Windows script compatibility.

### Files

- Create: `.gitattributes`

### Required content

```gitattributes
# Normalize source/docs to LF in the repository.
* text=auto eol=lf

# Windows command scripts should remain CRLF for native Windows tooling.
*.ps1 text eol=crlf
*.bat text eol=crlf
*.cmd text eol=crlf

# Binary/media files.
*.png binary
*.jpg binary
*.jpeg binary
*.gif binary
*.webp binary
*.ico binary
*.pdf binary
*.docx binary
*.zip binary
*.7z binary
*.db binary
*.sqlite binary
*.sqlite3 binary
```

### Verification

Run:

```bash
git status --short .gitattributes
```

Expected: `.gitattributes` appears as new or modified only.

## Task 2 — Add QA validation index

### Objective

Create the missing validation index from the production file set.

### Files

- Create: `docs/qa/VALIDATION_INDEX.md`

### Required sections

- Purpose
- Authority
- Current validation records
- Phase 7 validation targets
- Evidence rules
- Where generated artifacts go

### Required content constraints

The file must say:

- committed validation summaries belong in `docs/qa/`;
- generated coverage/runtime artifacts belong in ignored `artifacts/` or local caches;
- Phase 7 must validate Rust gateway build, endpoint contract tests, SSE latency, JSON Schema compatibility, and D-022 budget checks;
- validation records should link exact commands and outcomes.

### Verification

Run:

```bash
git status --short docs/qa/VALIDATION_INDEX.md
```

Expected: file is new and non-empty.

## Task 3 — Add supersession headers to old architecture docs

### Objective

Prevent stale architecture docs from being mistaken for current truth.

### Files

- Modify: `docs/architecture/FOUNDATION_STRATEGY.md`
- Modify: `docs/architecture/SYSTEM_OVERVIEW.md`

### Required header

Add this near the top, after the title/frontmatter if present:

```markdown
> **Supersession note — 2026-06-11:** This document is historical/contextual.
> For the current architecture, use `docs/architecture/OVERVIEW.md` and accepted ADRs
> D-018, D-021, and D-022. Do not treat pre-D-022 diagrams or phase layout in this
> document as canonical if they conflict with those sources.
```

Do not rewrite the full documents.

### Verification

Run a content search for `Supersession note — 2026-06-11` in both files.

## Task 4 — Add wiki ingestion rules note

### Objective

Document minimal rules for `wiki/raw/` ingestion without changing the wiki runtime.

### Files

Preferred:

- Create: `wiki/raw/README.md`

If `wiki/raw/` should remain empty and ignored by policy, create instead:

- `docs/operations/WIKI_INGESTION_RULES.md`

### Required rules

- raw ingested sources are preserved only when safe and intentional;
- no secrets, raw personal data, credentials, or private chat exports;
- every raw source must have provenance in the SQLite/source registry or related wiki metadata;
- compiled knowledge belongs in `wiki/entities/`, `wiki/concepts/`, `wiki/comparisons/`, or `wiki/index.md`;
- generated/runtime artifacts do not belong in `wiki/raw/`.

### Verification

Run:

```bash
git status --short wiki/raw/README.md docs/operations/WIKI_INGESTION_RULES.md
```

Expected: exactly one of the target files is new/modified.

## Task 5 — Podman/Twenty note only

### Objective

Record that Podman compatibility is unvalidated without installing anything.

### Files

- Modify: `docs/operations/TWENTY_LOCAL_SETUP.md`

### Required patch

Add a short note:

- Twenty's official compose is Docker-targeted.
- The current script prefers Podman for no-bloat local operation and falls back to Docker.
- Podman healthcheck/volume/network semantics are not validated until an engine is installed.
- Operator action: install Podman with `winget install RedHat.Podman` if/when Twenty testing is needed.

Do not run Twenty.
Do not install Podman.

## Task 6 — Final verification

Run:

```bash
git diff --check
git status --short
```

If available and cheap, also run:

```bash
cargo build -p atlas-gateway
```

from `native/atlas-core-rs/`.

Do not run long suites unless needed.

## Expected final report

The executing model should report:

1. Files created.
2. Files modified.
3. Commands run and results.
4. Whether any stale architecture docs remain without supersession headers.
5. Whether the working tree contains only expected cleanup changes.
6. Whether any task was skipped and why.

## Suggested single prompt for executor

```text
Repository: C:\Users\Davi\Desktop\Projects\L2-ATLAS-PROJECT

Execute `.planning/phases/07-api-gateway/07-LOW-MODEL-STABILIZATION-PLAN.md` exactly. This is a bounded cleanup pass only. Do not implement Phase 7 endpoints, do not modify the vendored foundation, do not move directories, do not install Podman/Docker, and do not rewrite architecture docs. Make the small files/patches requested, run the verification commands, and report files changed plus command results.
```
