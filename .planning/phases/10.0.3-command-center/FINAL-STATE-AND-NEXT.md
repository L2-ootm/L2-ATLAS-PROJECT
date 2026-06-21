# Final State & Next Phases — 2026-06-21

**Date:** 2026-06-21
**Branch:** feat/cockpit-p3-glass-p4
**Commits since session start:** 35+
**Total new/modified lines:** ~21,000+

---

## What Shipped (Complete Inventory)

### Command Center (WP-0 through WP-6, LE-0 through LE-5)

| WP | What | LOC |
|----|------|-----|
| WP-0 | Migration runner | — |
| WP-1a | Async executor (subprocess) | 135 |
| WP-1b | In-process executor daemon | 103 |
| WP-2 | Focus entity + gateway CRUD | 185 + 147 (Rust) |
| WP-3 | Context assembly (loop-engineered) | 122 |
| WP-4 | Command Center dashboard | 918 |
| WP-5 | Compounding loop (observations) | 32 |
| WP-6 | Named operations (4 premade instructions) | ~200 |
| LE-1 | Goal hierarchy model + service | 333 + 51 (migration) |
| LE-2 | Gateway goal CRUD | 215 (Rust) |
| LE-3 | NativeAtlasAgent wired to harness | 237 |
| LE-4 | Loop synthesis (goal tree + observations + contract) | 69 |
| LE-5 | Goal-tree UI | ~300 |

### Graphify Visual Refinement

| What | LOC |
|------|-----|
| GraphVisualConfig.ts (category colors, constants) | 92 |
| GraphLightning.ts (3D bolts replacing fog) | 231 |
| Auto-orbit + minimap sync | ~30 |
| Scrollbar refactor + edge-limit pulse | ~120 |

### Setup & Config

| What | LOC |
|------|-----|
| `atlas setup` wizard + config_service.py | ~300 |
| `~/.atlas/config.yaml` schema (Pydantic) | ~150 |
| Gateway `GET /v1/config` | ~20 |

### Channel Management

| What | LOC |
|------|-----|
| CLI: `atlas channels enable/disable/json` | 58 |
| Messaging gateway lifecycle control | 163 |
| Gateway endpoints (channels + messaging) | ~92 |
| System page: channels panel + model registry | ~157 |

### L2-BOT Discord Sidecar

| What | LOC |
|------|-----|
| Vendored `services/discord-bot/` (full bot) | ~8,000+ |
| `discord_control.py` (lifecycle) | 142 |
| `discord_api.py` (read client) | 47 |
| CLI: `atlas discord start/status/stop/guilds/structure` | 109 |
| Gateway: 5 Discord endpoints | ~92 |
| Cockpit: `/discord` route (guild browser, channels, roles) | 255 |

### Console BSP Auto-Tiling

| What | LOC |
|------|-----|
| `bspLayout.ts` (dwindle algorithm) | ~120 |
| Console.tsx BSP mode integration | ~50 |
| CSS `.atlas-workbench-bsp` | ~10 |

### Tests (New This Session)

| File | Tests |
|------|-------|
| test_agents.py | +5 |
| test_goal_service.py | 12 |
| test_run_executor.py | +2 |
| test_context_service.py | +3 |
| test_schemas.py | +3 |
| test_channels_cli.py | ~10 |
| test_discord_cli.py | ~8 |
| test_discord_control.py | ~12 |
| test_messaging_gateway_control.py | ~10 |
| tests/api.rs (gateway) | +4 |

**Total tests:** 182 Python + 68 Rust + web build green

---

## What's Missing

### P0 — Critical Gaps

| Gap | What | Impact |
|-----|------|--------|
| **`atlas` CLI not in PATH** | CLI-dispatched gateway endpoints (operations, graph) return 500 | Operations and graph views broken from cockpit |
| **No `atlas tui` command** | TUI lives only in foundation (`hermes --tui`) | No ATLAS-branded terminal UI entry point |
| **TUI dist not built** | `ui-tui/dist/` empty | TUI cannot run without `npm install && npm run build` |
| **Native agent provider routing** | `model=""` in harness config | Agent can't select provider/model from Focus |
| **No retry/recovery for failed runs** | Mission transitions to `failed`, no resume | Operator must create new mission |

### P1 — Important Gaps

| Gap | What | Impact |
|-----|------|--------|
| **Discord write operations** | Bot API has CRUD but not wired to ATLAS | Can't create/edit/delete channels from cockpit |
| **Approval-gating for Discord writes** | Operating model requires policy approval | Write surface blocked until audit trail exists |
| **No `HANDOFF.md` rendering** | Observations are the primitive but no file output | Cross-session continuity is DB-only, not portable |
| **No entropy reduction** | 8-class scan not implemented | Code/docs drag accumulates unchecked |
| **Memory router not budget-aware** | Context assembly is linear, no FTS5/semantic retrieval | Agent sees limited context |
| **No embedding infrastructure** | `wiki_vec` migration not created | Semantic search always falls back to FTS5 |
| **Graph engine hook** | Audit events don't trigger graph mutations | Graph is static snapshot, not living |
| **No graph node animation** | Nodes are static spheres | Graph doesn't look like neurons |

### P2 — Nice-to-Have

| Gap | What | Impact |
|-----|------|--------|
| **No `atlas setup` in cockpit** | Setup is CLI-only | No visual first-run experience |
| **No config import/export** | Config is local only | No backup/restore |
| **No audit trail viewer in cockpit** | Logs tab not built | Operator can't browse audit events |
| **No Discord message sending** | Read-only browser | Can't send embeds from cockpit |
| **No Discord permission management** | Read-only | Can't edit channel permissions |
| **No cross-scope graph linking** | Scopes are independent | Fragmented knowledge views |
| **No graph export** | No GEXF/GraphML | Can't analyze in external tools |

---

## Current Constraints

### Architectural

1. **D-001 (No foundation edits):** The Hermes foundation code cannot be modified. All ATLAS extensions go through the plugin system, CLI dispatch, or vendored sidecars.

2. **D-022 (Rust gateway, Python runtime):** The gateway is Rust (read-only REST + CLI dispatch). Business logic lives in Python. Agent adapters are permanent Python exceptions.

3. **D-012/013 (Pydantic source of truth):** All domain models are frozen Pydantic v2. JSON-stable `model_dump()`. Migrations are additive only.

4. **Single-operator concurrency:** One `threading.Lock` + SQLite WAL. Won't survive multi-user deployment.

5. **CLI dispatch overhead:** Every write spawns a Python subprocess (~50-100ms). Eliminated at L4 when Rust absorbs service functions.

### Operational

1. **Two gateways:** Rust REST gateway (port 8484) + Python messaging gateway (port varies). Independent processes. No shared lifecycle.

2. **Two Discord integrations:** Foundation messaging adapter (full, production) + vendored L2-BOT sidecar (read-only browser). Can't run both on same token.

3. **Two venvs:** ATLAS runtime venv + discord-bot venv. Separate dependency trees. `bot_python()` resolves the correct interpreter.

4. **No `atlas` CLI in PATH:** The Rust gateway's CLI-dispatched endpoints fail when `atlas` isn't on PATH. This is the immediate blocker for operations and graph views.

5. **Config split:** ATLAS config at `~/.atlas/config.yaml`. Foundation config at `~/.hermes/config.yaml`. Channels read from foundation config (D-001).

### Technical

1. **Hermes foundation is ATLAS:** The code at `foundation/atlas-hermes/` IS the ATLAS harness. Rebranded via entry points and skin. But import paths still reference `hermes_cli`, `hermes_constants`, `HERMES_HOME`.

2. **TUI not ATLAS-specific:** The TUI is Hermes upstream. ATLAS skin overrides visuals but there are no ATLAS-specific views (mission dashboard, goal tree).

3. **Context assembly is shallow:** Agent sees Focus + Goal tree + Observations + Project + Runs. No wiki retrieval, no semantic search, no graph context, no skill matching.

4. **Graph is static:** Markdown file scanner, no runtime entity integration, no incremental updates, no activity tracking.

5. **No watchpoint on agent execution:** 30-min max-runtime watchdog exists but no per-step timeout, no heartbeat, no cancellation propagation to the harness.

---

## Plausible Next Phases

### Phase A: Foundation Polish (1-2 weeks)

| WP | What | Effort | Impact |
|----|------|--------|--------|
| A1 | Add `atlas` to PATH in install script | 0.5 day | Gateway endpoints work |
| A2 | Build TUI dist (`npm install && npm run build`) | 0.5 day | TUI runnable |
| A3 | Add `atlas tui` command (thin wrapper over foundation TUI) | 1 day | ATLAS entry point |
| A4 | Wire native agent provider routing (Focus.framework → model selection) | 1 day | Agent selects right model |
| A5 | Add retry/recovery for failed missions | 1 day | No more "create new mission" |
| A6 | Config import/export | 0.5 day | Backup/restore |

### Phase B: Context Intelligence (2-3 weeks)

| WP | What | Effort | Impact |
|----|------|--------|--------|
| B1 | Create `wiki_vec` migration (0010 or 0011) | 0.5 day | Embedding storage |
| B2 | Wire FTS5 into context assembly | 0.5 day | Wiki retrieval |
| B3 | Add embedding computation to `update_wiki_page()` | 1 day | Semantic search |
| B4 | Build MemoryRouter class (budget-aware) | 2 days | 8K-token RAG context |
| B5 | Add audit pattern retrieval | 0.5 day | Failure-aware context |
| B6 | Add skill matching | 0.5 day | Domain-specific context |

### Phase C: Discord Write Surface (1-2 weeks)

| WP | What | Effort | Impact |
|----|------|--------|--------|
| C1 | Approval-gate framework (policy engine) | 2 days | Safety for write ops |
| C2 | Discord write CLI commands | 1 day | `atlas discord create-channel` etc. |
| C3 | Discord write gateway endpoints | 1 day | Cockpit can manage Discord |
| C4 | Discord write cockpit UI | 2 days | Channel/role management |
| C5 | Audit trail for Discord actions | 1 day | Every write logged |

### Phase D: Living Graph (3-4 weeks)

| WP | What | Effort | Impact |
|----|------|--------|--------|
| D1 | Graph schema + SQLite migration | 2 days | Entity graph storage |
| D2 | Entity extractors (missions, runs, wiki, decisions) | 3 days | Runtime entities as nodes |
| D3 | Graph builder pipeline (incremental) | 2 days | Event-driven updates |
| D4 | Node animation (pulse, breathe, fire) | 3 days | Living neuron visual |
| D5 | Activity scoring + nebula glow | 2 days | Hot cluster visualization |
| D6 | Agent Context tab (live) | 2 days | Runtime knowledge graph |

### Phase E: Full Rebrand (1 week)

| WP | What | Effort | Impact |
|----|------|--------|--------|
| E1 | `hermes_cli` → `atlas_cli` import rename | 2 days | Clean import paths |
| E2 | `~/.hermes/` → `~/.atlas/` config path | 1 day | Unified config space |
| E3 | `@hermes/ink` → `@atlas/ink` TUI package | 1 day | ATLAS-branded TUI |
| E4 | ATLAS-specific TUI views (mission dashboard, goal tree) | 3 days | TUI becomes ATLAS-native |
| E5 | Foundation code reference cleanup | 1 day | No `hermes` references in ATLAS code |

### Phase F: Future Harnesses (ongoing)

| WP | What | Source | What to Cherry-Pick |
|----|------|--------|---------------------|
| F1 | PI (Perplexity) harness patterns | PI | Research-first execution, citation-backed responses |
| F2 | OpenCode harness patterns | OpenCode | Clean agent abstraction, tool registry design |
| F3 | Evaluate ACP (Agent-Client Protocol) | OpenHands | Vendor-agnostic agent interop |
| F4 | Evaluate LightRAG for graph context | LightRAG | Dual-level retrieval (community + entity) |

---

## Recommended Sequence

```
Phase A (Foundation Polish)  ← unblocks everything
  ↓
Phase B (Context Intelligence)  ← agent gets smarter
  ↓
Phase C (Discord Write Surface)  ← operator gets power
  ↓
Phase D (Living Graph)  ← knowledge becomes visible
  ↓
Phase E (Full Rebrand)  ← ATLAS identity complete
  ↓
Phase F (Future Harnesses)  ← continuous improvement
```

**Phase A is the immediate priority.** Adding `atlas` to PATH unblocks the operations and graph endpoints that are currently 500-ing. Building the TUI dist and adding `atlas tui` gives the operator a terminal entry point. Wiring provider routing means the native agent can actually use the right model.

---

## Metrics Summary

| Metric | Session Start | Session End |
|--------|--------------|-------------|
| Git commits | f30b2a1 | 25b8bd9 (~35 commits) |
| Gateway endpoints | 20 | 44 |
| Pydantic models | 7 | 10 |
| SQL migrations | 9 | 10 |
| CLI subcommand groups | ~10 | ~18 |
| Tests (Python) | ~64 | 182 |
| Tests (Rust) | ~30 | 68 |
| React routes | 11 | 13 (/command, /discord) |
| React components | 15 | 20+ |
| New source files | 0 | 25+ |
| Lines added | 0 | ~21,000+ |
