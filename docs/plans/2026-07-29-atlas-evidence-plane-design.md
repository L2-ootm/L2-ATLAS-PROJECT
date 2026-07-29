# ATLAS Evidence Plane — Product Design

Date: 2026-07-29  
Status: selected direction  
Detailed implementation specification:
`.planning/ultra/ULTRAPLAN_ATLAS_EVIDENCE_PLANE.md`

## Decision

The next ATLAS focus is not another integration or broad visual redesign. It is
an Evidence Plane that makes execution trustworthy:

- semantic, compact tool-call receipts;
- durable and attributable file-change records;
- clickable `+N −N` change summaries;
- a paged and virtualized diff inspector;
- parent/subagent/team aggregation;
- read-only mutation detection;
- lossless result retrieval;
- one cross-run audit API shared by every surface.

Before that feature begins, the 0.1.5 lifecycle blockers—secret disclosure,
team cancellation, team archival/deletion, output truncation, and actor-history
loss—must be closed and released.

## UX direction

Use the existing ATLAS dark cockpit language with a high-agency dashboard
composition: dense but calm, hairline-separated, one scarce celestial accent,
and mono type for paths/counts/IDs. The interaction reference is Claude Code's
change review, but ATLAS adds explicit audit, policy, and actor provenance.

An edit appears in chat as:

```text
EDITED  services/runtime/worker.py                  +42  −11   EULER · 184 ms
```

Selecting it opens a resizable evidence pane with a file rail, unified or
side-by-side hunks, line numbers, context controls, search, and links back to
the run, actor, team, and originating tool. Large changes load hunk pages and
virtualize rows; they are never placed wholesale into the event stream or DOM.

## Execution package

Phase 10.8 is implementation-ready as eleven plans across ten gated waves:

| Wave | Plan | Outcome |
|---|---|---|
| 1 | 05 | Close cancellation, archive/delete, installed-artifact, secret-redaction, and actor-history blockers |
| 2 | 06 | Freeze contracts and storage; implement Rust-authoritative diff/hunk/index and lossless result references |
| 3 | 07 | Capture mutations, reconcile shell/Git writes, enforce read-only policy, and attribute child work |
| 4 | 08 | Expose bounded cursor/range APIs and metadata-only SSE summaries through the Rust gateway |
| 5 | 09 | Add Cockpit receipts, Run Detail parity, Ledger paging, and a row-windowed Evidence Inspector |
| 6 | 11 | Project the shared semantic contract into the Go TUI and atlas-terminal |
| 7 | 10 | Aggregate parent/subagent/team/goal evidence over durable actor history |
| 8 | 01 + 03 | Run prompt/cross-surface and registry-wide tool/RAG/adversarial conformance in parallel |
| 9 | 02 | Run the twenty-run live battery, including at least eight weak-model FreeLLMAPI runs |
| 10 | 04 | Perform operator UAT, rollback rehearsal, and the dated cutover decision |

The plan checker passed after two revision cycles. Frozen gates include a
FreeLLMAPI score of at least 8/10 and zero secret disclosures, unapproved
mutations, false terminal states, silent truncations, or orphan workers.

The detailed local execution package lives under
`.planning/phases/10.8-cross-surface-conformance-uat-cutover/`; begin with
`10.8-05-PLAN.md`. Checkpoints, inline review comments, automated review,
provider mesh, and expansion products remain deferred.

This direction converts ATLAS from “an agent with logs” into an operator system
whose work can be inspected and trusted.
