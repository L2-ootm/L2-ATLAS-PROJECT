# ATLAS TUI Phase 10.1 Baseline

## Measurement context

- **Date:** 2026-06-24T16:07:57-03:00
- **Commit:** 98c84ec
- **Machine/OS:** Microsoft Windows 10.0.26200
- **CPU:** AMD64 Family 25 Model 33 Stepping 2, AuthenticAMD
- **Runtime:** Bun 1.3.13
- **Workload:** standalone executable snapshot and hidden interactive idle shell

## Results

| Metric | Result | Phase 10.1 budget | Verdict |
|---|---:|---:|---|
| Direct runtime dependencies | 3 | <= 3 | PASS |
| Direct development dependencies | 2 | <= 3 | PASS |
| Transitive package entries | 188 | recorded | RECORDED |
| ATLAS TUI source files | 8 | <= 30 | PASS |
| ATLAS TUI source size | 6.96 KiB | <= 250 KiB | PASS |
| Standalone artifact | 114.54 MiB | target <= 120 MiB; block > 140 MiB | PASS |
| Cold start | 225.98 ms | <= 2000 ms | PASS |
| Warm start p95 | 282.47 ms | <= 1000 ms | PASS |
| Idle working set after 5 seconds | 230.24 MiB | initial <= 150 MiB | MISS |
| Idle private memory after 5 seconds | 450.66 MiB | recorded | RECORDED |
| Unexpected network connections | 0 | 0 | PASS |

## Dependency inventory

- Runtime: @opentui/core, @opentui/solid, solid-js
- Development: @types/bun, typescript

## Budget verdict

**CONDITIONAL PASS.** The original 150 MiB idle-working-set target is missed by the pinned
OpenTUI/Bun Windows substrate. A minimal core-only diagnostic measured a comparable floor, so
the Phase 10.1 evidence ceiling is revised to <= 240 MiB for this intake
prototype. Phase 10.6 must re-measure and either reduce the substrate cost or record an explicit
architecture decision before default cutover. All other blocking budgets pass.

## Reproduction

pwsh -NoProfile -File scripts/tui-baseline.ps1 -PackageRoot apps/atlas-tui -OutputPath docs/imports/ATLAS_TUI_BASELINE.md
