# ATLAS Harness Quality Review — 2026-08-09

## Review record

- **Scope:** ATLAS agent-contract evaluator, mission-loop judgement, and the
  approval-gated Self-Review golden workflow
- **Depth:** Standard, with targeted cross-file checks
- **Reviewer:** Codex (GPT-5)
- **Status:** Findings recorded; no runtime code changed
- **Reference:** [Prime Agent](https://github.com/PrimeIntellect-ai/prime-agent)
- **Proposed standard:**
  [ATLAS Standard Quality Agent](../architecture/ATLAS_STANDARD_QUALITY_AGENT.md)

## Result

The current checked-in promotion gate is green, deterministic, offline, and
fast. Its reference dataset still promotes correctly. The review found one
reproducible evaluator correctness defect and two harness-contract gaps that
should be resolved before the evaluator or Self-Review workflow becomes a
general quality authority.

| Severity | Finding | Disposition |
|---|---|---|
| Warning | Q-001: incomplete datasets can receive a vacuous promotion | Fix before reusing the evaluator with generated or user-supplied datasets |
| Warning | Q-002: judge unavailability is represented as `continue`, not `abstain` | Add an explicit inconclusive state before quality-driven autonomous loops |
| Info | Q-003: Self-Review records activity, not quality evidence or a verdict | Evolve behind a typed quality-agent contract; retain approval-gated writes |

## Findings

### Q-001 — Incomplete datasets can receive a vacuous promotion

**File:** `services/agent-runtime/atlas_runtime/evals/agent_contract.py`

`_ratio()` returns `1.0` when its denominator is zero. `evaluate_dataset()`
also does not require the eight contract categories or any critical scenario
to be present. Consequently, a dataset containing 30 passing identity
scenarios and no retrieval, completion, permission, poisoning, subagent,
resume, or tool scenarios receives `promoted=True`.

Reproduction executed from `services/agent-runtime`:

```powershell
..\..\.venv\Scripts\python.exe -c "from atlas_runtime.evals.agent_contract import evaluate_dataset; s=[{'scenario_id':str(i),'category':'identity','input':{'atlas_identity':True,'donor_identity':False}} for i in range(30)]; print(evaluate_dataset(s))"
```

Observed result:

```text
EvaluationReport(promoted=True, scenario_count=30,
critical_pass_rate=1.0, retrieval_precision=1.0,
retrieval_recall=1.0, retrieval_abstention=1.0,
completion_honesty=1.0, secret_leaks=0,
unapproved_side_effects=0, failures=())
```

The checked-in fixture is currently protected by
`test_reference_dataset_has_required_size_categories_and_unique_ids`, so the
official script does not exhibit this defect. The protection is outside the
evaluator API, however, and will not follow a future caller automatically.

**Recommended correction:** make required category coverage and minimum sample
counts evaluator invariants; represent unavailable metrics as `None` or
`not_evaluated`; and make any missing blocking dimension non-promotable.

### Q-002 — Judge unavailability has no abstention state

**File:** `services/agent-runtime/atlas_runtime/mission_loop_service.py`

`_foundation_judge()` maps an unavailable foundation, missing client, and
provider exception to a `continue` verdict. Provider exceptions set
`parse_failed=False`, so the three-parse-failure pause does not apply. The
loop remains bounded by `max_runs`, but it can consume the entire run budget
without obtaining quality evidence.

This behavior is acceptable for the current goal-continuation loop because it
is explicitly fail-open and bounded. It is not acceptable as the semantics of
a standard quality authority: inability to judge must be distinguishable from
evidence that work is incomplete.

**Recommended correction:** add `abstain`/`inconclusive` to the quality verdict
contract, record the unavailable gate or judge as evidence, and stop or hand
off according to policy without claiming pass or fail.

### Q-003 — Self-Review is an audit digest, not a quality review

**File:** `services/agent-runtime/atlas_runtime/golden_workflows/self_review.py`

The workflow safely routes its proposed write through the write-policy
chokepoint and never auto-writes. Its note contains only recent event types and
timestamps. It does not capture a scoped change set, commands, outcomes,
contract/catalog hashes, findings, severity, confidence, or a verdict.

The workflow lifecycle also reaches `completed` when the write proposal is
created, while the approval has its own pending/executed/rejected lifecycle.
This distinction is documented and tested, but a quality UI must display both
states to avoid treating “review proposed” as “quality passed.”

**Recommended correction:** keep the approval boundary and replace the digest
payload with a typed quality receipt plus a human-readable report.

## Verification evidence

### Official agent-contract gate

```powershell
pwsh -NoProfile -File scripts\agent-contract-eval.ps1
```

```text
76 passed in 1.01s
scenario_count: 33
critical_pass_rate: 1.0
retrieval_precision: 1.0
retrieval_recall: 1.0
retrieval_abstention: 1.0
completion_honesty: 1.0
secret_leaks: 0
unapproved_side_effects: 0
promoted: true
ATLAS agent contract promotion gate: PASSED
```

### Focused tests

```powershell
..\..\.venv\Scripts\python.exe -m pytest tests\test_golden_workflow_self_review.py tests\test_mission_loop_service.py tests\evals\test_agent_contract_evals.py -q
```

```text
17 passed in 0.65s
```

### Static checks

```powershell
..\..\.venv\Scripts\ruff.exe check atlas_runtime\evals\agent_contract.py atlas_runtime\golden_workflows\self_review.py atlas_runtime\mission_loop_service.py
```

```text
All checks passed!
```

## Prime Agent comparison

Prime Agent’s most relevant patterns are host-owned autonomous gates with
bounded retries and timeouts, failed-gate output returned to the next attempt,
an explicit statement that exhausted budgets do not mean success, and
versioned supplemental harness refinement with rollback. Its persistent Python
control environment and runtime are not candidates for adoption: D-023 keeps
ATLAS as one runtime, and D-022 keeps new infrastructure Rust-first.

