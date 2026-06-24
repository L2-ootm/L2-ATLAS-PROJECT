# ATLAS TUI Intake Decisions

## Source baseline

- Upstream: `https://github.com/XiaomiMiMo/MiMo-Code`
- Release: `v0.1.2`
- Commit: `86d95a79bf0879bcb442ffe6b12914f6d8e68a4e`
- Audited subtree: `packages/opencode/src/cli/cmd/tui`
- Inventory: 180 files, 2,630,082 bytes
- Audit date: 2026-06-24

The intake is deny-by-default. Every source item is classified as exactly one
of `adopt-pattern`, `rewrite`, or `reject`. An unclassified item is rejected.
`adopt-pattern` records a useful concept; it does not authorize verbatim copy.

## Classification totals

| Classification | Files | Bytes | Meaning |
|---|---:|---:|---|
| `adopt-pattern` | 4 | 19,335 | Reimplement a presentation or terminal-platform concept in ATLAS-owned code. |
| `rewrite` | 80 | 517,068 | Useful interaction shape, but coupled to donor state or dependencies; rebuild against ATLAS contracts. |
| `reject` | 96 | 2,093,679 | Do not import into shipped code. |
| **Total** | **180** | **2,630,082** | Complete pinned-source set. |

## Area summary

| Area | Files | Bytes | Adopt | Rewrite | Reject |
|---|---:|---:|---:|---:|---:|
| root | 7 | 57,673 | 1 | 4 | 2 |
| asset | 7 | 1,409,659 | 0 | 0 | 7 |
| component | 37 | 170,198 | 3 | 18 | 16 |
| component/prompt | 7 | 100,592 | 0 | 7 | 0 |
| config | 4 | 14,609 | 0 | 0 | 4 |
| context | 18 | 105,227 | 0 | 12 | 6 |
| context/theme | 33 | 160,864 | 0 | 0 | 33 |
| feature-plugins/home | 3 | 9,669 | 0 | 0 | 3 |
| feature-plugins/sidebar | 11 | 25,603 | 0 | 10 | 1 |
| feature-plugins/system | 1 | 7,659 | 0 | 0 | 1 |
| i18n | 9 | 247,518 | 0 | 0 | 9 |
| plugin | 5 | 44,068 | 0 | 0 | 5 |
| routes | 1 | 5,652 | 0 | 1 | 0 |
| routes/session | 10 | 157,009 | 0 | 10 | 0 |
| ui | 10 | 56,997 | 0 | 10 | 0 |
| util | 17 | 57,085 | 0 | 8 | 9 |

## Hard rejection boundary

The following donor authorities and product surfaces are rejected:

- SDK and sync clients;
- provider and model selection;
- authentication, account, organization, token-plan, and hosted-service flows;
- configuration, migration, key/value, local-state, memory, and session storage;
- telemetry, observability, process metadata, and remote service coupling;
- updater, share, hosted documentation, product tips, and agreement flows;
- plugin, marketplace, workflow, skill, and donor MCP runtimes;
- voice, VAD, audio, image, and media assets;
- internationalization bundles and locale-specific search;
- donor themes, logos, product copy, commands, environment variables, paths, URLs, and package names.

ATLAS already owns the agent, tools, policy, audit, Project registry, Current
Focus, wiki/Brain memory, configuration, provider/model registry, and approval
state. A terminal client must not create a second authority for any of them.

## Small Phase 10.1 shell subset

Only four source items are marked `adopt-pattern`: border characters, a
background pulse concept, a star-field concept, and the Windows console-input
guard. They are references for clean-room reimplementation, not copy targets.

The Phase 10.1 proof remains smaller still:

- compact ATLAS text identity;
- workspace placeholder;
- status line;
- empty transcript region;
- composer placeholder;
- deterministic snapshot mode;
- clean exit;
- no backend, provider, account, network, memory, plugin, update, or share call.

All other useful UI, composer, session, permission, task, sidebar, and dialog
ideas are `rewrite` candidates for later phases after the corresponding ATLAS
contracts exist.

## Dependency and runtime budgets

| Metric | Phase 10.1 budget |
|---|---:|
| Direct runtime dependencies | <= 3 |
| Direct development dependencies | <= 3 |
| ATLAS TUI source files | <= 30 |
| ATLAS TUI source size | <= 250 KB |
| Standalone artifact | <= 120 MB target; >140 MB blocks |
| Cold start to snapshot/first draw | <= 2.0 s p95 on the reference Windows host |
| Warm start to snapshot/first draw | <= 1.0 s p95 |
| Idle working set after 5 seconds | <= 150 MB |
| Unexpected network calls | 0 |
| Forbidden identity, paths, and URLs | 0 outside approved documentation/notices |

The initial runtime dependency ceiling is `@opentui/core`,
`@opentui/solid`, and `solid-js`, pinned to the audited line. Additional
dependencies require a reproduced need and measured justification.

## Review and distribution gate

The upstream tree contains an MIT license and a separately published
`USE_RESTRICTIONS.md`. ATLAS preserves the required MIT notices and records
the restrictions document without asserting a legal conclusion. Internal
technical evaluation may continue; public distribution of derivative code is
gated on explicit review or upstream clarification.
