# Durable Actor / Chat Regression — Forensic Review

## Scope

Investigate the reported visible Windows terminal, the opaque `ATLAS_ACTOR`
card, missing live child integration, lost Chat whitespace, and broken transcript
scrolling. Fixes were authorized by the operator in the same request.

## Findings

### F-01 — Conflicting Windows process flags could flash a console (critical)

- Evidence: the worker launch combined `DETACHED_PROCESS` with
  `CREATE_NO_WINDOW` and used the console Python executable.
- Root cause: those flags are conflicting Windows creation modes; the detached
  console path can still materialize a visible console window.
- Fix: `actor_worker.py:41` selects `pythonw.exe` when available and
  `actor_worker.py:76` now uses only `CREATE_NEW_PROCESS_GROUP |
  CREATE_NO_WINDOW`, with closed inherited descriptors.
- Proof: the Windows spawn regression test asserts `pythonw.exe`, both required
  flags, absence of `DETACHED_PROCESS`, and `close_fds=True`.

### F-02 — Durable actors used the Hermes session namespace (high)

- Evidence: the plugin supplied `parent_agent.session_id`, while surface replay
  is anchored to the ATLAS parent run's `runs.session_id`.
- Root cause: Hermes and ATLAS surface session IDs are different namespaces.
  Child events could persist correctly yet never appear in the Chat surface.
- Fix: `actor_service.py:152` derives the authoritative surface session from the
  parent run and overrides the advisory caller value.
- Proof: regression coverage passes a deliberately wrong Hermes session and
  asserts the actor retains the parent surface session.

### F-03 — Child run linkage arrived only at terminal completion (high)

- Evidence: `child_run_id` was written by complete/fail, after execution.
- Root cause: the UI had no way to associate live child audit events with the
  actor while it was working.
- Fix: `actor_service.py:223` binds the child run immediately after `start_run`
  and emits a `working` lifecycle event. `ChatActorWorkspace.tsx:51` combines
  actor lifecycle events with events whose run ID matches that child.
- Proof: service and component tests assert the working link and live tool row.

### F-04 — The durable tool rendered twice and the raw copy was the worse one (medium)

- Evidence: Chat rendered both the durable lifecycle rail and the generic
  `atlas_actor` tool call card.
- Root cause: the generic card cannot express actor lifecycle and remained an
  opaque running row.
- Fix: `Chat.tsx:762` suppresses only the redundant `atlas_actor` tool card; the
  auditable lifecycle remains visible in the inline rail and actor workspace.

### F-05 — The first redesign collapsed three intended zones into two (high)

- Evidence: the grid had only transcript + 310px actor columns, consuming the
  operator's intentionally empty left region. The TopoScroll wrapper had no
  definite height, so history expanded behind the composer instead of scrolling.
- Fix: `Chat.tsx:609-614` restores an explicit reserved left zone and gives the
  transcript scroller a 100% height. `app.css:1569-1586` defines a 200px / fluid /
  400px desktop grid and an independently contained scroll viewport.
- Proof: Playwright measured `clientHeight=702`, `scrollHeight=2305`,
  `scrollTop=1603`, and `overflowY=auto` after inserting a temporary scroll probe.

## Verification

- Agent runtime: 918 passed, 1 skipped.
- Shared `atlas-core`: 97 passed.
- WebUI: 129 passed.
- TypeScript production build and bundle budget: passed.
- ESLint and Ruff: passed.
- Playwright: wide layout, narrow layout, actor drawer, composer focus, model
  overlay, and live scroll containment inspected in rendered pixels.

## Residual Risk

- The visible-terminal assertion verifies the exact Windows creation contract;
  final operator UAT should still confirm no window flashes on the installed
  Python/runtime combination.
- Model registry/config overlay displays an honest gateway error when the Vite
  development page is run without the gateway. Live model mutation requires the
  rebuilt gateway already used by the cockpit.
