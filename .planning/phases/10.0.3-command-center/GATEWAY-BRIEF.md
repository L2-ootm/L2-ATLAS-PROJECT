# Gateway & CLI/TUI Brief — 2026-06-20

## Gateway

**Binary:** `atlas-gateway.exe` (4.1MB release)
**Port:** 8484 (loopback only)
**Status:** ONLINE
**Health:** `{"db":"ok","status":"ok","version":"0.1.0"}`

### 39 Routes

| Category | Routes | Status |
|----------|--------|--------|
| Health | /health | Working |
| Missions | CRUD + archive + run + cancel | Working (reads direct, writes CLI-dispatch) |
| Runs | detail + events + SSE stream | Working |
| Wiki | pages CRUD + search | Working (reads direct, writes CLI-dispatch) |
| Models | list | Working |
| Projects | CRUD + register + detail | Working |
| Focus | list + current + create + archive + tree | Working |
| Goals | create + archive | Working (CLI-dispatch) |
| Tasks | create + set status | Working (CLI-dispatch) |
| Observations | create | Working (CLI-dispatch) |
| Operations | list + run | Fails without atlas CLI in PATH |
| Modules | list + activate + deactivate | Working |
| Cashflow | status + summary + start + stop | Fails (module not running) |
| Console | chat + stream | Working (CLI-dispatch) |
| Graph | build | Fails without atlas CLI in PATH |
| Host | select-folder | Working (PowerShell) |

### vs Hermes Gateway

| Dimension | ATLAS | Hermes |
|-----------|-------|--------|
| Type | REST API over SQLite | Multi-platform messaging daemon |
| Language | Rust (axum) | Python (asyncio) |
| Platforms | None (API only) | 22+ built-in + 8 plugin |
| Sessions | Stateless | SQLite-backed, reset policies |
| Streaming | SSE audit events | Live token delivery per platform |
| Auth | None (loopback) | Slash command access, role-based |
| Restart | PID file kill | Graceful drain |
| Goal hierarchy | Full CRUD + tree | None |
| Operations | 4 premade instructions | None |
| Focus entity | Singleton working context | None |
| Compounding loop | Observations feed back | None |

### What ATLAS Gateway Does Better

- Rust performance (<1ms routing)
- Type safety (compile-time guarantees)
- Goal/task/observation hierarchy
- Operations with write-back contract
- Focus as operator intent primitive
- Compounding loop (learning across runs)
- D-012 contract enforcement (Pydantic ↔ Rust schema tests)

### What Hermes Gateway Does Better

- 22+ messaging platform adapters
- Session persistence with reset policies
- Live token streaming per platform
- Provider routing with credential pool
- Platform-native message formatting
- Auth and access control
- Graceful restart with drain
- Crash forensics

### The Gap

ATLAS gateway is a REST API. Hermes gateway is a messaging daemon. They are complementary:
- ATLAS manages knowledge/work (missions, goals, focus, context)
- Hermes manages channels (Discord, Telegram, Slack, etc.)
- Both share the same SQLite database and audit bus
- `atlas-agent gateway` starts the Hermes messaging layer

---

## CLI

**ATLAS CLI:** 15+ groups, 864 lines Typer. Production quality. Clean separation: thin handlers → service layer → SQLite.

**Hermes CLI (upstream):** 14k lines argparse. Battle-tested. Profiles, TUI, gateway lifecycle, setup wizard.

**Missing:** `atlas tui` command. TUI lives in foundation only.

---

## TUI

**Hermes TUI:** 23+ components, Ink/React, nanostores, JSON-RPC gateway transport, full theme system. Production quality.

**Status:** Not built in this checkout. Needs `npm install && npm run build` in `ui-tui/`.

**Branding:** ATLAS skin is fork default. Skin engine overrides visuals. But no ATLAS-specific cockpit views in TUI.

**Gap:** No `atlas tui` entry point. No mission dashboard or goal tree in TUI.

---

## Rebranding

| Layer | Status | Next |
|-------|--------|------|
| Skin/colors/ASCII | Done | — |
| CLI entry points | Done | — |
| Gateway binary name | Done | — |
| `banner.ts` fallback | Partial | Skin overrides at runtime |
| `hermes` CLI name | Not done | Rename to `atlas` |
| Foundation import paths | Not done | `hermes_cli` → `atlas_cli` |
| `~/.hermes/` config path | Not done | Move to `~/.atlas/` |
| TUI component names | Not done | `@hermes/ink` → `@atlas/ink` |
| ATLAS-specific TUI views | Not done | Mission dashboard, goal tree |

**Future harnesses (PI, OpenCode):** Cherry-pick patterns, not fork code. The ATLAS harness should be a standalone agent runtime that can ingest good ideas from multiple sources.
