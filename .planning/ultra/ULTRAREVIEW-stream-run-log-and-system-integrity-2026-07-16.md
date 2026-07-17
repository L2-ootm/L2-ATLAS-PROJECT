# ULTRAREVIEW — Stream, Run, Log, and System Integrity

Date: 2026-07-16

## Scope

Investigate intermittent WebUI response truncation, reduce delta-log noise without
weakening audit evidence, reorganize Runs around sessions, inspect ATLAS's generated
self-description, and verify retention/integration integrity.

## Findings and root causes

### F1 — Complete stream replaced by capped final event (critical, fixed)

The reported run `a48318b8-9f0c-4c5b-ab12-df0fc6889424` contained 175 `llm_delta`
events totaling 7,700 characters. Its `llm_call.data.text` and transition summary
were both exactly 2,000 characters and ended at the same partial heading. Native
mapping used `final_response[:_SUMMARY_CAP]` for both the compact summary and the
authoritative final-surface event. The client reconcile behaved correctly and exposed
the server truncation.

Resolution: preserve the 2,000-character `RunOutcome.summary`, but emit the complete
final response in `llm_call`, with `text_length` metadata. A long-response regression
test locks the distinction.

### F2 — Core policy compiled but not delivered (high, fixed)

`compile_prompt` produced the deterministic L0–L4 stable policy and its digest, but
`RunContractSnapshot` retained only the digest. `_contract_system_message` sent the
bootstrap/context envelopes and omitted the stable policy. Therefore rules about
identity, current-fact verification, tools, and language were absent from actual
native model calls.

Resolution: prompt v1.0.1 stores the exact stable policy in the immutable snapshot and
delivers it under `Core Operating Policy`. The bootstrap also resolves the persisted
WebUI/TUI/CLI surface and workspace instead of hard-coding `cli`. Old snapshots remain loadable. The policy
now requires explicit distinctions between registered, configured, reachable, and
verified-live state, and prevents memory-system conflation.

### F3 — Failed integration probes fabricated offline state (high, fixed)

The Integrations page replaced rejected status promises with `{running:false}` and
displayed `OFFLINE`. This made “endpoint unreachable” indistinguishable from a live
adapter reporting “stopped.”

Resolution: rejected probes display `UNKNOWN` and `status unavailable`; `OFFLINE` is
reserved for reachable adapters that explicitly report stopped.

### F4 — Delta audit rows obscured navigation (medium, fixed)

Raw `llm_delta` rows dominated Run Detail and Ledger. Deleting or coalescing stored
events would weaken evidence and cursor semantics.

Resolution: a dependency-free projection groups only consecutive same-run deltas.
Groups retain all member IDs/cursors, character counts, and reconstructed text, and
expand on demand. Non-delta boundaries always flush the group. Raw storage is intact.

### F5 — Runs indexed prompts instead of conversations (medium, fixed)

Each prompt creates a mission/run, but prompts already share a durable
`runs.session_id`. The page rendered the flat run feed and hid that relationship.

Resolution: group by the persisted session id, sort sessions and turns by activity,
expand sessions into prompt runs, and route each run to its existing evidence page.
Null-session legacy runs remain individual.

### F6 — Retention transaction had incomplete dependents and a blocking trigger (high, fixed)

Archived-mission purge removed only tool calls, artifacts, audit events, and runs.
Approvals and soft run links could remain. More seriously, migration 0015's no-delete
snapshot trigger blocked SQLite cascade and made purge fail for native runs with a
contract snapshot.

Resolution: migration 0020 removes only the no-delete trigger; no-update immutability
remains. Purge now removes raw run dependents and detaches compact observations,
sources, and provenance so compiled knowledge survives without dangling run links.
The Storage UI invokes only this real due-archive transaction behind confirmation.

## Verification evidence

- Agent runtime: 847 passed, 2 skipped.
- ATLAS core: 97 passed.
- Atlas terminal: 59 passed; TypeScript clean.
- WebUI: 94 passed; ESLint and TypeScript clean; production build and bundle budgets green.
- Repository whitespace/error check: `git diff --check` clean.

## Remaining work

- Operator browser/terminal UAT after rebuilding/restarting the local stack.
- A transactional retention preview, arbitrary date/session filters, and an automatic
  scheduler. These are deliberately not represented as active controls yet.
- Server-side session pagination/aggregation once the 500-run recent window becomes a
  practical limit; current client grouping is correct but bounded.
