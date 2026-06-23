# Golden Workflows v0

ATLAS ships three **golden workflows** — demo-stable, deterministic orchestrations
that prove the system survives repeated demos on the wedge's three use cases. They
are not LLM prompts: each is a deterministic orchestrator that performs real reads
through the tool layer and writes artifacts / wiki entries / audit events directly,
so output is reproducible with no provider credentials and no network. (The mock LLM
provider emits only canned text — golden workflows deliberately do not depend on it.)

## Safety model (read this first)

- **Repo Triage** and **Research Brief** are *internal-risk*: they auto-run and write
  their artifact + wiki page immediately. Both writes are scoped to `golden/`-prefixed
  artifact paths and `repo-triage-*` / `research-brief-*` wiki slugs.
- **Self-Review never writes without approval.** Its review-note write routes through
  the same `tool_service` policy chokepoint as every other write-class tool (see
  [docs/tools.md](tools.md)) and lands as a **pending `ToolApproval`** — nothing is
  written to disk until you explicitly `atlas tools approve <id>`.
- **Audit-first.** Every workflow emits `golden_workflow_started` / `golden_workflow_completed`
  bookend events (tagged with the `workflow_id`), plus — for Repo Triage — the
  `tool_requested` / `tool_completed` pair from each workspace read.

## The three workflows

| id | risk | what it produces |
|----|------|------------------|
| `repo_triage` | internal (auto) | scans the workspace (top-level listing + README via the `workspace` tool) → a triage artifact + a `repo-triage-<date>` wiki page |
| `research_brief` | internal (auto) | offline FTS5 search of the codex for a topic → a brief artifact + a `research-brief-<topic>` wiki page (zero network) |
| `self_review` | approval | surveys the recent audit trail → **proposes** a review-note write, gated behind an explicit approval (never auto-written) |

## Repo Triage

Reads the workspace through the `workspace` tool (a top-level `list` and a README
`read`), builds a markdown triage summary, records it as an `Artifact`
(`golden/repo-triage-<date>.md`), and upserts a `repo-triage-<date>` wiki page with
provenance. A missing README degrades gracefully to a "No README found" note.

Sample output: [sample-data/repo-triage-sample.md](../.planning/phases/10.0.5-golden-workflows-quality-gate/sample-data/repo-triage-sample.md)
(real output generated against this repository).

## Research Brief

Searches the codex (`atlas_wiki.wiki_service.search_wiki`, FTS5 — offline by
construction, never `web_fetch`) for a topic, writes a brief artifact
(`golden/research-brief-<topic>-<date>.md`) and a `research-brief-<topic>` wiki page.
An empty search degrades to an honest "No wiki entries matched" line.

Sample output: [sample-data/research-brief-sample.md](../.planning/phases/10.0.5-golden-workflows-quality-gate/sample-data/research-brief-sample.md)

## Self-Review

Surveys the recent audit events for the operator run and **proposes** a review note
via `tool_service.invoke(tool_name="golden_review_write", …)`. Because
`golden_review_write` is a `write`-class tool, the policy chokepoint short-circuits it
to a **pending** `ToolApproval` (reason `golden_workflow:self_review`) — the proposed
file is never written inline. Execute it with `atlas tools approve <id>`, or discard
it with `atlas tools reject <id>` (approval surface documented in [docs/tools.md](tools.md)).

Sample output (the *proposed*, not-yet-written note):
[sample-data/self-review-sample.md](../.planning/phases/10.0.5-golden-workflows-quality-gate/sample-data/self-review-sample.md)

## Running the workflows

```bash
# list the three workflows
atlas golden list

# run an internal workflow (writes immediately)
atlas golden run repo_triage --workspace .
atlas golden run research_brief --topic atlas

# run self-review (proposes a gated write — nothing is written yet)
atlas golden run self_review --workspace .
#   -> prints a pending approval id; then either:
atlas tools approve <id>     # execute the proposed write
atlas tools reject  <id>     # discard it
```

## Quality gate

The SC1/SC2 proof — each workflow run 3× with consistent structure — is a single test:

```bash
cd services/agent-runtime
python -m pytest tests/test_golden_workflows_smoke.py -v
```

It asserts structure, not byte-equality: artifact rows accrue, the audit bookends and
(for Repo Triage) tool events are present, wiki entries exist, and Self-Review yields
**exactly** one new pending approval per call with no inline write.

## Demo-reset

To re-run a clean demo, reset only the golden-workflow-tagged rows:

```bash
atlas golden reset            # DRY-RUN by default — reports what would be deleted, deletes nothing
atlas golden reset --confirm  # actually delete
```

Reset is scoped to `golden/` artifact paths, `repo-triage-*` / `research-brief-*` /
`self-review-*` wiki slugs, and `golden_workflow:*` approval reasons. It never touches
`audit_events`, `missions`, or `runs` — your real run/audit history stays intact.

## Audit event naming

Golden workflows add two additive `AuditEvent.event_type` values:
`golden_workflow_started`, `golden_workflow_completed` (each carries `workflow_id` in
its `data`). Repo Triage's workspace reads emit the standard `tool_requested` /
`tool_completed` pair through the shared tool chokepoint.

See [docs/known-failures.md](known-failures.md) for documented limitations.
