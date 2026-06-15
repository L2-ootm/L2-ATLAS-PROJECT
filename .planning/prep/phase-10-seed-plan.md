# Phase 10 Seed Plan — ATLAS Agentic CLI + Native Operator Shell

**Status:** seed plan, not execution plan.  
**Created:** 2026-06-15.  
**Use:** input for `/gsd-new-milestone` and then `/gsd-plan-phase 10`.

## Phase intent

Phase 10 should make ATLAS feel like a real local operator harness, not only a browser cockpit plus internal service CLI.

The implementation should start with the CLI/harness bridge, because the native shell needs something meaningful to host.

## Proposed subphases

### 10.0 — CLI/harness bridge

**Goal:** expose the Hermes-derived foundation as ATLAS-branded agentic commands.

Candidate commands:

```txt
atlas chat
atlas chat -q "..."
atlas auth status
atlas doctor
```

Key tasks:

- inspect foundation CLI/chat entrypoints;
- choose wrapper strategy: direct import vs subprocess handoff;
- make `atlas` command available without `python -m`;
- implement one-shot chat path;
- implement interactive chat path or clear TUI handoff;
- add tests for command availability and no-secret output.

Acceptance:

```bash
atlas --help
atlas auth status
atlas chat -q "ping"
atlas doctor
```

### 10.1 — Auth/provider discovery

**Goal:** detect local AI runtime/auth state like Hermes does.

Key tasks:

- detect `codex` executable and version;
- detect `~/.codex/auth.json` and `~/.codex/config.toml` safely;
- inspect/reuse Hermes `hermes_cli.auth` logic;
- detect Hermes/ATLAS active profile and provider config;
- report provider readiness without secrets.

Acceptance:

```bash
atlas auth status
```

Shows Codex installed/auth-present on Davi's machine.

### 10.2 — Model discovery and registry upgrade

**Goal:** replace seeded-only model perception with real discovery.

Key tasks:

- design merged model source view;
- preserve historical model rows for audit;
- discover FreeLLMAPI `/v1/models` when available;
- discover Codex/Hermes/OpenRouter/custom provider availability;
- update CLI output;
- update cockpit Models page.

Acceptance:

```bash
atlas models discover --include-local-auth
atlas models list --all
```

Output includes source/status/auth columns.

### 10.3 — Native shell scaffold

**Goal:** Tauri 2 shell wraps the existing SvelteKit cockpit.

Key tasks:

- create Tauri 2 scaffold in the approved native location;
- embed static SvelteKit build;
- verify no Electron;
- define IPC allowlist;
- write threat model.

Acceptance:

Native app opens the existing cockpit locally.

### 10.4 — PTY + operator loop integration

**Goal:** native shell hosts CLI pane and cockpit in one local operator surface.

Key tasks:

- embed PTY terminal pane;
- run `atlas --help` inside PTY;
- preserve cwd and command lifecycle signals if feasible;
- link shell UI to auth/model readiness;
- run manual UAT.

Acceptance:

Davi can visually open the shell, see cockpit, open terminal pane, run `atlas chat -q`, inspect model/auth status, and launch/monitor a mission.

## Hard gates

- No secret leakage.
- No copied personal auth files into repo.
- No Electron.
- No CRM/Pulse scope creep unless explicitly pulled forward.
- No parallel second chat runtime if Hermes foundation can be wrapped.
- No claim of complete v1.1 until both CLI and visual shell pass UAT.

## Suggested first investigation commands

```bash
cd /c/Users/Davi/Desktop/Projects/L2-ATLAS-PROJECT
python -m atlas_runtime.cli.main --help
python - <<'PY'
import importlib.util
for mod in ['hermes_cli.auth', 'hermes_cli.main', 'run_agent']:
    print(mod, importlib.util.find_spec(mod))
PY
codex --version
python - <<'PY'
from pathlib import Path
for p in [Path.home()/'.codex/auth.json', Path.home()/'.codex/config.toml']:
    print(p, p.exists())
PY
```

## Files likely touched

- `services/agent-runtime/atlas_runtime/cli/main.py`
- `services/agent-runtime/atlas_runtime/cli/models.py`
- `services/agent-runtime/atlas_runtime/model_registry.py`
- new `services/agent-runtime/atlas_runtime/cli/auth.py`
- new `services/agent-runtime/atlas_runtime/cli/chat.py`
- new tests under `services/agent-runtime/tests/`
- `services/web-ui/src/routes/models/` or equivalent model page files
- `native/atlas-core-rs/` or new native shell location decided by roadmap

## Output artifacts expected

- updated requirements;
- updated roadmap;
- CLI/auth/model design note;
- threat model for native shell IPC;
- manual UAT guide for v1.1;
- screenshots or terminal captures of CLI and native shell.
