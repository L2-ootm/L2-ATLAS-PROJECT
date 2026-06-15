# AGENTS.md — L2 ATLAS PROJECT

## Mission

Build L2 ATLAS as an AI operator/company cockpit using Hermes as the main runtime foundation and L2 and imported skill assets as reusable modules.

## Non-negotiables

- Do not copy secrets or raw personal data into this repo.
- Do not destructively reorganize existing repos.
- Do not keep Hermes as a black-box dependency; ATLAS should be built from/enhance the Hermes foundation with documented changes.
- Keep actions auditable: reason, input, tool/action, output, verification.
- Use flexible priority blocks, not rigid schedules.

## Architecture rule

Separate:

1. raw sources;
2. compiled wiki/memory;
3. runtime execution;
4. cockpit UI.

## Language rule (D-013, cementation timing resolved by D-022)

Prototype in Python. Cement in Rust. Avoid C unless necessary.
D-022 (accepted 2026-06-10) makes Rust-first immediate for all new
infrastructure: Phase 7 gateway is Rust; new Python is confined to the
Hermes-derived foundation surface, LLM adapters, and throwaway scripts.

- Python is the current orchestration layer and is **permanent for the Hermes plugin API**.
- The critical runtime (CLI, policy, executor, mission parser, state) will migrate to Rust module by module after behavior is validated in Python.
- All Python code must follow migration prerequisites: frozen Pydantic v2 models, JSON-stable `model_dump()`, no circular deps, no heavy frameworks.
- Approved Python deps: `pydantic`, `prompt_toolkit`, `rich`, `pytest`, `ruff`. No new frameworks without a new decision.
- The `native/` layer is Rust from the start (D-005).

## Planning rule

Update `.planning/STATE.md` after every meaningful step.
