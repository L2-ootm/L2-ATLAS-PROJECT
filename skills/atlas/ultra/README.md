# ATLAS Ultra — Subagent-Native Execution Doctrine

The ATLAS Ultra skill pack provides 9 modes for systematic, proof-based work
using parallel subagents. Each mode follows a defined pipeline that produces
a structured artifact with verifiable evidence.

## Mode Router

| Mode | Use when | File |
|---|---|---|
| `ultraplan` | strategic planning, architecture, specs | `ultraplan.md` |
| `ultrareview` | investigation, debugging, forensics | `ultrareview.md` |
| `ultradesign` | UI/UX design, frontend, dashboards | `ultradesign.md` |
| `ultraexecute` | implementation, shipping, building | `ultraexecute.md` |
| `ultraresearch` | research, analysis, comparison, surveys | `ultraresearch.md` |
| `ultrasimulate` | dry-runs, blocker prediction, walkthroughs | `ultrasimulate.md` |
| `ultraaudit` | security sweeps, architecture audits, compliance | `ultraaudit.md` |
| `ultrasynthesize` | cross-source fusion, finding synthesis | `ultrasynthesize.md` |
| `ultramigrate` | migrations, ports, upgrades, transitions | `ultramigrate.md` |

## ATLAS Integration

- **Missions**: Ultra modes can run as ATLAS missions (`mission-ok` tag)
- **Durable actors**: Parallel steps use `atlas_actor` spawn/status/wait (`[actor-ok]` tag)
- **Audit ledger**: Artifacts cite audit run ids for reproducibility
- **Handoff**: Follows `skills/atlas/handoff.md` format

## GSD Chain

```
ultraplan → gsd/init → gsd/discuss → gsd/plan → gsd/execute → gsd/ship
```

- `ultraplan` is strategic; `gsd/plan` is tactical
- `ultraexecute` wraps `gsd/execute` per wave
- `ultrareview` is parallel multi-angle; `gsd/debug` is single-agent root cause
- `ultraaudit` is proactive sweep; `gsd/verify` is per-deliverable gate

## Rules

1. Read state before editing; the repo is the memory, not the conversation.
2. Every claim carries evidence or the label "not verified".
3. Parallelize independent work; isolate heavy context.
4. Artifacts persist between modes; chain outputs to inputs.
5. Quality gates pass before declaring done.
6. Failures are reported with output, never smoothed over.
