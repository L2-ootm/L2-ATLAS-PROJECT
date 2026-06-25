# ATLAS Agent Contract Evaluation

**Phase:** 10.2  
**Date:** 2026-06-25  
**Promotion verdict:** PASSED

## Blocking gate

```powershell
pwsh -File scripts/agent-contract-eval.ps1
```

The gate is deterministic and offline. It runs schema, prompt, catalog, Brain,
retrieval, replay, resume, and reference-dataset checks; scans shipped prompt
and catalog artifacts for secret canaries; and exits non-zero on any threshold
or critical invariant failure.

## Thresholds

- Critical deterministic pass rate: 100%
- Unapproved side effects: 0
- Secret leaks: 0
- Retrieval precision: >= 0.80
- Retrieval recall: >= 0.85
- Retrieval abstention: >= 0.90
- Completion honesty: >= 0.95
- Scenario count: >= 30

## Dependency and tracing posture

No network call, model call, external evaluation framework, Phoenix instance,
or OpenTelemetry runtime dependency is required. A future injected judge may
reject a deterministic pass after calibration, but cannot approve a
deterministic failure.

## Recorded evidence

Executed from the repository root:

```text
65 passed in 0.51s
scenario_count: 33
critical_pass_rate: 1.0
retrieval_precision: 1.0
retrieval_recall: 1.0
retrieval_abstention: 1.0
completion_honesty: 1.0
secret_leaks: 0
unapproved_side_effects: 0
catalog_sha256: 9841e636239f3b3c1660388bab7f79e92b13e66930e434f8d2491c0cfd421442
promoted: true
```

The targeted gate completed in under three seconds wall-clock on the local
Windows development machine. Prompt-size, deterministic golden hashes, catalog
generation, and retrieval p95 are enforced by the included targeted tests.

## Known limitations

- The reference dataset is curated and deterministic; it does not yet measure
  real model variance across providers.
- Optional LLM judging remains disabled until calibrated against operator labels.
- Cross-surface TUI/WebUI parity belongs to Phase 10.8.
