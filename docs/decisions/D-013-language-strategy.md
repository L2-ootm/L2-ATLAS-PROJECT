---
id: D-013
created: 2026-06-05
status: locked
---

# D-013 — Language Strategy: Prototype in Python, Cement in Rust

## Decision

ATLAS uses a hybrid language architecture with a deliberate migration path:

**Now (prototype phase):** Python is the orchestration layer.
**Medium-term:** Migrate the critical runtime to Rust, module by module.
**Long-term:** Rust owns the core binary; Python is relegated to adapters and experiments.

**Principle: Prototype in Python. Cement in Rust. Avoid C unless necessary. Watch Zig, don't bet on it.**

---

## Layer Assignment

| Layer | Language | Status | Rationale |
|-------|----------|--------|-----------|
| Hermes plugin hooks | Python | Permanent | Plugin ABI is Python — no choice |
| LLM adapter / provider config | Python | Permanent | LLM SDKs are Python-first; I/O-bound, language overhead is noise vs API latency |
| CLI (atlas command) | Python → Rust | Migrate | clap + crossterm; single binary, fast cold start |
| Runtime orchestration | Python → Rust | Migrate | Policy, executor, session dispatch — latency-sensitive |
| Mission Control parser/writer | Python → Rust | Migrate | Deterministic text processing; correctness-critical writeback |
| Policy engine | Python → Rust | Migrate | Safety boundary; must be fast, correct, and auditable |
| Executor (subprocess/PowerShell) | Python → Rust | Migrate | Process lifecycle, kill-tree, timeout — OS-level primitives |
| State (JSONL, SQLite, sessions) | Python → Rust | Migrate | WAL + concurrent reads; Rust SQLite bindings (rusqlite) are mature |
| Skills layer | Python → WASM? | TBD | Skills as isolated processes + manifest JSON; WASM optional future |
| Scripts, experiments, research tools | Python | Permanent | Low friction, throwaway, no perf requirement |
| Native desktop app / overlay | Rust | Locked (D-005) | Slint/egui/Tauri; D-005 already ratified |

---

## Why Not Rewrite Now

The project is still validating what the system should do:

- Mission Control lifecycle (plan → approve → execute → log → writeback)
- Terminal agent UX (chat, plan, run, apply, status, doctor)
- Policy model (workspace sandbox, command risk classification)
- LLM adapter (provider config, context limits, tool boundary)
- Session state and correlation IDs
- Skills discovery and classification

Rewriting to Rust before these contracts are stable means rewriting twice. Python iteration speed is the correct tool for architecture discovery. The migration happens after behavior is proven, not before.

---

## Why Rust (Not Zig or C)

**Rust vs C:** C has maximum performance but manual memory management is a net negative for a complex, evolving system. ATLAS is not a kernel or embedded device.

**Rust vs Zig:** Zig is philosophically clean and excellent for small binaries, but its ecosystem for CLI, async, Windows, parsing, and integration is materially smaller than Rust's. Zig is a calculated bet; Rust is a production choice.

**Rust pros for ATLAS:** single binary, `clap` CLI, `ratatui`/`crossterm` TUI, `rusqlite`, `tokio` async, `serde`/`serde_json`, strong Windows support, memory safety without GC, mature error handling (`thiserror`/`anyhow`).

---

## Migration Prerequisites (for Python code written now)

All current Python code MUST comply with these rules to remain migratable:

1. **JSON-stable serialization** — `model.model_dump()` is the canonical wire format; no Python-specific types in serialized output.
2. **Frozen immutable models** — `model_config = ConfigDict(frozen=True)` per D-012; maps cleanly to Rust `#[derive(Clone)]` structs.
3. **No circular module dependencies** — each package has one direction of import flow.
4. **Pure functions where possible** — stateless computation is trivially portable.
5. **No heavy framework lock-in** — current acceptable deps: `prompt_toolkit`, `rich`, `pydantic`, `pytest`, `ruff`. No new frameworks without explicit decision.
6. **Schema fields must map to Rust primitives** — no untyped `dict[str, Any]` in public model fields; use typed nested models.
7. **CLI arguments are data** — pass structured objects, not argparse namespaces, across module boundaries.

---

## Rust Target Module Map (medium-term)

```
native/atlas-core-rs/
  crates/
    atlas-cli/        # clap, crossterm — replaces cli.py
    atlas-runtime/    # tokio, async dispatch — replaces orchestrator.py
    atlas-mission/    # MD parser/writer — replaces mission_control/
    atlas-policy/     # command validation, path sandbox — replaces policy.py
    atlas-exec/       # subprocess, PowerShell, Windows-first — replaces powershell.py
    atlas-state/      # JSONL, rusqlite, session store — replaces jsonl_logger.py + state
```

This mirrors the `native/` directory from D-011 canonical layout.

---

## Current Python Dependency Budget

Acceptable now:
- `pydantic>=2.0` (Rust-backed, aligns with D-012)
- `prompt_toolkit>=3.0` (will be replaced by crossterm in Rust CLI)
- `rich>=13.9` (will be replaced by ratatui in Rust TUI)
- `pytest`, `ruff` (dev-only, never ship)

Not acceptable without a new decision:
- Any ORM (SQLAlchemy, etc.) — use raw SQLite via `sqlite3`
- Any web framework (FastAPI, Flask) — services use raw stdlib `http.server` or are Rust
- Any heavy async framework (Celery, etc.) — use `asyncio` directly or port to Rust
- Any serialization framework other than Pydantic v2

---

## Phase Impact

| Phase | Impact |
|-------|--------|
| Phase 2 (Schemas) | Use Pydantic v2 frozen models with JSON-stable `model_dump()` — this IS the migration contract |
| Phase 4 (Audit Bus) | Python Hermes plugin layer — permanent; Rust migration does not apply here |
| Phase 5–6 (Mission/Wiki) | Design for clean JSON contracts so Rust parser can consume same data |
| Phase 7+ (API Gateway) | **Resolved by D-022 (2026-06-10): Rust from the start** — axum/rusqlite gateway is the first `native/atlas-core-rs` crate; cementation timing is no longer open |
| Native layer | Already Rust by D-005 |
