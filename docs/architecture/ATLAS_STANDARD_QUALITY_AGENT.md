# ATLAS Standard Quality Agent

**Status:** Proposed standard; not implemented

**Date:** 2026-08-09

**Owner:** ATLAS runtime and evidence plane

**Decision boundary:** This document explains a proposed architecture. It does
not amend D-022 or D-023 and does not authorize a second agent runtime.

## Purpose

The Standard Quality Agent is one logical ATLAS role that determines whether a
scoped artifact or run has enough verified evidence to pass a declared quality
contract. It composes deterministic host gates with independent model review,
then emits one typed, auditable receipt.

It is designed to improve the current harness without importing Prime Agent,
Prime Verifiers, or another general-purpose framework. Prime Agent is a
reference for gate and refinement mechanics only.

## Standard outcome

Every quality run must end in exactly one verdict:

- `pass` — all blocking deterministic gates passed, required evidence coverage
  is complete, and no model reviewer rejected the result;
- `fail` — at least one blocking invariant or acceptance criterion failed;
- `abstain` — evidence, coverage, a gate, or the reviewer was unavailable or
  inconclusive;
- `cancelled` — the operator or owning runtime cancelled the run.

Budget exhaustion, a timeout, missing categories, a crashed verifier, and an
unavailable judge can never produce `pass`.

## Core contract

The Rust-first target is a frozen, JSON-stable `QualityReceipt` shared across
the gateway, runtime, CLI, TUI, and Cockpit. A temporary Pydantic v2 source may
be used only on the Hermes-derived Python surface while the contract is being
validated.

```text
QualityReceipt
  receipt_version
  quality_run_id
  subject { kind, id, revision, workspace_root }
  scope { paths, requirements, exclusions }
  contract { id, version, sha256 }
  run_contract_sha256
  tool_catalog_sha256
  started_at / completed_at
  verdict: pass | fail | abstain | cancelled
  coverage { required, observed, missing }
  gates[]
  findings[]
  reviewer_assessments[]
  budgets { attempts, elapsed_ms, tokens }
  remediation_refs[]
  provenance[]
```

Each gate record includes its stable ID, kind, command or evaluator reference,
timeout, attempt number, exit status, bounded output digest, artifact hashes,
and result. Each finding includes severity, subject location, claim, evidence,
confidence, and a stable fingerprint for deduplication.

Secrets and raw personal data are never receipt fields. Evidence stores hashes,
redacted previews, and artifact references instead.

## Execution protocol

1. **Freeze scope.** Resolve the subject revision, workspace, acceptance
   criteria, required evidence dimensions, exclusions, and budgets before any
   judgment runs.
2. **Capture provenance.** Bind the immutable ATLAS run contract, prompt
   version, tool catalog, policy revision, and relevant build identity.
3. **Run deterministic gates.** Execute schema, unit, lint, policy, security,
   contract, and domain gates in declared order. Gate execution is owned by the
   host, not by model prose.
4. **Check evidence coverage.** Missing required categories or minimum samples
   produces `abstain`; empty denominators never receive a perfect score.
5. **Run independent review.** A fresh-context reviewer may reject a
   deterministic pass or add findings. It may never override a deterministic
   failure. If the reviewer is required but unavailable, verdict is `abstain`.
6. **Issue the receipt.** Persist the typed receipt and a readable report before
   displaying a completion claim on any surface.
7. **Propose remediation.** Fixes and harness refinements are separate
   proposals. Writes continue through ATLAS policy and approval authority.
8. **Re-run from a fresh baseline.** A fix invalidates the prior pass candidate.
   Re-execute affected gates and detect regressions before replacing the
   receipt.

## Retry and budget rules

- Gate attempts, wall time, model tokens, and autonomous continuations are
  explicit positive budgets.
- Gate timeouts stop the owned process tree and record a failed or unavailable
  gate; they do not silently continue.
- Failed gate output is bounded, redacted, and supplied to the next remediation
  attempt.
- An unchanged subject plus the same failed-gate fingerprint is not rerun
  indefinitely. It consumes an attempt and moves toward `fail` or `abstain`.
- Passing all required gates permits completion. Reaching a retry, turn, token,
  or time limit does not.

These rules adapt Prime Agent’s autonomous-gate semantics to ATLAS’s existing
mission, policy, audit, and evidence authorities.

## Refinement policy

Quality runs may propose small improvements to supplemental harness state:

- prompt addenda;
- memory or failure-pattern entries;
- reusable skill descriptions;
- quality-contract or reviewer-role specifications.

The immutable ATLAS core prompt and accepted decisions are not self-rewritten.
Every refinement proposal must cite the failed receipt and evidence, remain a
small reviewable diff, pass policy, receive approval when it changes durable
state, create a versioned snapshot, and support rollback. Executable skills
still require ordinary code review and tests.

This adapts Prime Agent’s Continual Harness model while preserving ATLAS’s
auditable authority boundaries.

## Integration with the current harness

| Existing seam | Keep | Change |
|---|---|---|
| `agent_contract.evaluate_dataset` | Deterministic safety invariants; optional judge can only reject | Enforce category/sample coverage in the evaluator; return unavailable metrics explicitly; persist a receipt |
| `mission_loop_service` | Single continuation owner, immutable judgements, hard run budget | Keep goal progress separate from quality verdicts; add `abstain` and unavailable-judge policy |
| `golden_workflows.self_review` | Approval-gated write and audit lifecycle | Produce a scoped evidence pack, findings, and receipt instead of an event-type digest |
| `RunContractSnapshot` | Immutable prompt/context/tool provenance | Bind its hash into every quality receipt |
| Agent-contract PowerShell gate | Offline deterministic checks and non-zero failure | Declare gates as data, capture bounded per-gate evidence, and write a machine-readable receipt artifact |
| CLI/TUI/Web/Cockpit | One normalized ATLAS surface protocol | Render the same receipt and distinguish review, proposal, approval, and verified-pass state |

## Independence and authority

The quality role is read-only by default. It does not approve its own fixes,
widen permissions, mutate the base prompt, or mark a mission complete. The
runtime owns gate execution and receipt persistence; policy owns side effects;
the operator owns exceptional overrides.

For high-risk subjects, model review should use a fresh context that contains
the frozen scope and evidence but not the builder’s chain of thought. Multiple
reviewers may contribute assessments, but one deterministic reducer produces
the final verdict.

## Initial quality profiles

### `quick`

Changed-file lint, targeted tests, schema validation, secret scan, and evidence
coverage. Intended for local iteration; never a release authority.

### `standard`

`quick` plus affected call-path review, policy/permission checks, independent
model review, and a persisted receipt. Default for phase and harness reviews.

### `release`

`standard` plus clean-environment build/install, cross-surface contract gates,
rollback evidence, operator UAT requirements, and exact artifact identity.

Profiles may add domain gates but cannot weaken zero-tolerance invariants such
as secret leaks, unapproved side effects, missing blocking evidence, or
contract-schema failure.

## Adoption matrix

| Prime Agent pattern | ATLAS disposition | Reason |
|---|---|---|
| Host-owned bounded quality gates | Adopt | Deterministic, auditable, and compatible with Rust-first supervision |
| Failed-gate evidence returned to remediation | Adopt | Improves repair loops without granting new authority |
| Budget exhaustion is not success | Adopt | Required for completion honesty |
| Supplemental harness refinement with snapshots | Adapt | Must route through ATLAS policy, evidence, and accepted-decision boundaries |
| Independent recursive reviewers | Adapt | Use existing ATLAS agent/runtime and explicit authority narrowing |
| Persistent Python/IPython control environment | Do not adopt | Conflicts with D-022 Rust-first infrastructure and expands execution risk |
| Prime Agent or Verifiers as a shipped runtime dependency | Do not adopt | D-023 forbids a second general-purpose agent/eval authority |

## Implementation sequence

1. Fix evaluator coverage semantics and add regression tests for incomplete
   category sets, zero denominators, duplicates, and minimum critical samples.
2. Define `QualityReceipt` and fixtures in `packages/atlas-core`; prove stable
   JSON and secret-safe serialization.
3. Add Rust gateway persistence and read APIs for quality runs and receipts.
4. Wrap the existing agent-contract and focused test commands as declared host
   gates with timeouts, fingerprints, and bounded outputs.
5. Evolve Self-Review to assemble evidence and request an independent reviewer;
   keep all durable writes approval-gated.
6. Add normalized receipt events and surface rendering.
7. Pilot `standard` on the agent harness, compare operator labels, and calibrate
   model review before it can block promotion.

No new runtime dependency is required for this sequence.

## Acceptance criteria

- An incomplete dataset cannot promote, even when every supplied scenario
  passes.
- A verifier outage, judge outage, timeout, or missing evidence yields
  `abstain` or `fail`, never `pass`.
- A deterministic failure cannot be overridden by a model reviewer.
- Every verdict is reproducible from a frozen scope, declared gates, and
  referenced evidence.
- Quality writes and refinements remain separately approval-gated and
  rollbackable.
- CLI, TUI, WebUI, and Cockpit display the same verdict and receipt identity.
- Release claims remain blocked by missing operator UAT when the contract
  requires it.

## References

- [Prime Agent README](https://github.com/PrimeIntellect-ai/prime-agent)
- [Prime Agent usage and autonomous gates](https://github.com/PrimeIntellect-ai/prime-agent/blob/main/packages/coding-agent/docs/usage.md)
- [Prime Agent architecture](https://github.com/PrimeIntellect-ai/prime-agent/blob/main/packages/coding-agent/docs/architecture.md)
- [Continual Harness paper](https://arxiv.org/abs/2605.09998)
- [D-022 — Rust-first cementation policy](../decisions/D-022-rust-first-cementation-policy.md)
- [D-023 — One ATLAS Agent, Multi-Surface Workbench](../decisions/D-023-atlas-multi-surface-agent-contract.md)
- [ATLAS Agent Contract Evaluation](../verification/ATLAS_AGENT_CONTRACT_EVAL.md)
