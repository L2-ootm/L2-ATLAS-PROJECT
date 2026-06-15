# v1.0 Post-Archive Gap — CLI / Models / Agentic Chat

Date: 2026-06-15
Trigger: Operator visual inspection of `python -m atlas_runtime.cli.main --help` after v1.0 archive.

## Verdict

Davi's objection is valid.

The archived v1.0 is defensible only as **Operator Cockpit MVP**: persisted missions/runs, Rust gateway, browser cockpit, audit stream, wiki, and read-only model registry.

It is **not** a full ATLAS agent CLI/runtime parity release. The current `atlas_runtime` CLI is a thin operational/database CLI, not an agentic chat harness.

## Evidence observed

Current CLI surface:

```txt
mission
wiki
foundation
models
channels
```

Mission surface:

```txt
create
run
cancel
status
```

Model registry output currently shows only seeded/registered rows:

```txt
claude-fable-5 (anthropic)
claude-sonnet-4-6 (anthropic)
gemini-2.5-pro (google)
```

Local Codex is installed and authenticated on the machine:

```txt
codex-cli 0.128.0
C:\Users\Davi\.codex\auth.json exists
C:\Users\Davi\.codex\config.toml exists
```

But `atlas_runtime` does not currently surface:

- Codex auth detection;
- Hermes-style runtime credential resolution;
- all locally available models/providers;
- an `atlas chat` / `atlas agent` / `atlas run-agent` interactive agentic CLI;
- integrated provider/model selection using local Hermes/Codex auth state.

## Root cause

The v1.0 scope shipped the cockpit loop and the data-plane CLI, while the full Hermes-derived agent UX stayed in the vendored foundation.

Relevant split:

- `services/agent-runtime/atlas_runtime/cli/main.py` = ATLAS operational CLI, DB/service wrappers.
- `foundation/atlas-hermes/` = Hermes-derived agent harness, auth resolver, TUI/chat, providers, tools.

The bridge is incomplete: `atlas_runtime` reports foundation status but does not expose the foundation's chat/runtime capabilities as ATLAS-branded commands.

## Why this feels wrong

The project narrative says ATLAS evolves Hermes into the L2/ATLAS harness. From an operator viewpoint, that implies the CLI should already include:

```txt
atlas chat
atlas agent
atlas auth status
atlas models discover
atlas models list --all-local
```

Instead, the visible CLI looks like an internal service tool. That weakens the claim that v1.0 is an operator-facing ATLAS harness.

## Correct classification

Recommended label:

> v1.0 Operator Cockpit MVP — archived, but agentic CLI parity incomplete.

Do **not** call this a complete ATLAS CLI release.

## Required next-phase work

### P0 — ATLAS agentic CLI surface

Add ATLAS-branded commands that route into the Hermes-derived foundation instead of duplicating it:

```txt
atlas chat [--model ...] [--provider ...]
atlas chat -q "..."
atlas auth status
atlas models discover --include-local-auth
atlas models list --all
atlas doctor
```

### P0 — Codex auth/provider detection

Reuse or port Hermes foundation logic:

- detect `codex` binary;
- detect `~/.codex/auth.json` and `~/.codex/config.toml` without printing secrets;
- resolve Codex runtime credentials the same way Hermes does;
- expose status as `configured/authenticated/not found`.

### P0 — Model registry upgrade

Current model registry is a gateway `/models` sync + DB list. It must also merge:

- configured Hermes providers;
- Codex local auth/runtime provider;
- OpenRouter/custom providers from ATLAS/Hermes config;
- FreeLLMAPI `/v1/models` when sidecar is running;
- seeded models as fallback/defaults only.

### P1 — Browser cockpit alignment

Models page should show provider status and source:

```txt
source: seeded | gateway | codex-auth | hermes-config | free-llmapi
status: available | auth-present | needs-login | offline
```

## Bottom line

The v1.0 archive can stand as a cockpit milestone, but Davi's critique should become a hard Phase 10/v1.1 entry criterion:

> ATLAS is not credible as a Hermes-derived operator harness until the ATLAS CLI exposes agentic chat, auth detection, and real provider/model discovery.
