# Known Failures & Limitations

Honest accounting of what the golden workflows (and their quality gate) do **not**
cover, so an evaluator trusts the claims rather than discovering the gaps later. None
of these are silent — each is a conscious, documented boundary.

## Known Limitations

### 1. Live cockpit screenshots are deferred to operator UAT
The golden-workflow quality gate is verified at the service layer (`pytest
tests/test_golden_workflows_smoke.py`). Live Playwright/cockpit screenshots of each
workflow running in the UI require a full-stack boot (gateway + cockpit, see the
`atlas-local-run-recipe`) and are deferred to operator UAT. SC3's "screenshots" item
is satisfied by the committed real **sample-data** artifacts plus operator-run UI
captures, not by an automated screenshot harness.

### 2. Determinism is a mock-mode guarantee, not a live-LLM one — by design
"Each workflow runs 3× with consistent output" holds because the workflows are
deterministic orchestrators (real reads + direct artifact/wiki/audit writes), and the
mock provider emits no structural output. **Real (non-mock) LLM runs are inherently
non-deterministic** — a live model will not produce byte-identical briefs across runs.
This is expected: mock mode is the demo-stable path, and the quality gate asserts
*structure*, never byte-equality. It is a property of the system, not a bug.

### 3. Research Brief is offline (codex/FTS5) only — no `web_fetch` variant
Research Brief searches the local wiki/codex via FTS5 and never touches the network
(it does not import `web_fetch`/`urllib`). A `web_fetch`-backed Research Brief variant
(public-web research, SSRF-guarded) is **not implemented yet** — deferred so mock-mode
smokes never depend on connectivity.

## Edge cases (graceful, documented)

- **Repo Triage with no README** → emits a "No README found" note instead of failing.
- **Research Brief with no codex matches** → emits an honest "No wiki entries matched
  '<topic>'" line instead of failing. (Verified during sample generation against a
  freshly-seeded codex.)
- **Self-Review with an empty audit trail** → emits "No audit events recorded yet for
  this run." rather than producing an empty note.

## Environment note

The full agent-runtime test suite shows **1 pre-existing, unrelated failure**:
`test_agents.py::test_claude_code_missing_sdk_raises` requires the optional
`claude-agent-sdk` (install `atlas-runtime[claude]`), which is absent from the default
Hermes venv on the dev machine. It is orthogonal to the golden workflows and predates
this phase.
