# ATLAS v0.1 — Demo Script

A repeatable ~6-minute demo built on the three golden workflows. Deterministic in Mock
Mode (zero credentials) — see [`docs/golden-workflows.md`](../golden-workflows.md).

**DRAFT — operator runs this live and captures screenshots/video for the launch (SC3).**

## 0. Setup (once)

```bash
cp .env.example .env
./scripts/setup.sh          # or .\scripts\install-atlas-cli.ps1 on Windows
./atlas db init --demo
./atlas up                  # gateway + cockpit
./atlas doctor              # all green
```

Open the cockpit (http://127.0.0.1:5173). No API key needed — Mock Mode runs end-to-end.

## 1. The cockpit at a glance (60s)

- **Observatory** — system health, active missions, recent activity. The brand stage.
- **Ledger** (`/audit`) — "every action accounted for": filter the cross-run audit stream
  by event type / policy. This is the auditability thesis in pixels.

## 2. Golden Workflow 1 — Repo Triage (60s)

```bash
atlas golden run repo_triage --workspace .
```

Show: a triage **artifact** is recorded, a **Codex** (wiki) page is written, and the
**Ledger** shows the `golden_workflow_started/completed` + `tool_requested/tool_completed`
events from the workspace reads. Sample output:
`.planning/phases/10.0.5-golden-workflows-quality-gate/sample-data/repo-triage-sample.md`.

## 3. Golden Workflow 2 — Research Brief (45s)

```bash
atlas golden run research_brief --topic atlas
```

Show: offline FTS5 codex search → a brief artifact + Codex page. No network. Open the page
in **Codex** to show provenance.

## 4. Golden Workflow 3 — Self-Review, approval-gated (90s) — the trust moment

```bash
atlas golden run self_review --workspace .
# prints a PENDING approval id — nothing is written yet
```

Show in cockpit **System ▸ Tool Approvals**: the proposed write sits **pending**. Then:

```bash
atlas tools approve <id>    # now (and only now) the write executes
# or: atlas tools reject <id>
```

This is the headline: **writes never happen without an explicit operator decision.**

## 5. Repeatability + reset (45s)

```bash
cd services/agent-runtime && python -m pytest tests/test_golden_workflows_smoke.py -v
```

Show the quality gate green — each workflow 3×, structure consistent, Self-Review exactly-3
pending. Then reset demo state safely:

```bash
atlas golden reset            # dry-run: shows what would be deleted
atlas golden reset --confirm  # scoped to golden-tagged rows only
```

## 6. Close (30s)

"v0.1 is an open research preview — auditable by construction, extensible by manifest, and
honest about what it isn't. Feedback wanted on auditability, reliability, and extensibility."
Point to repo / technical report / known-failures.
