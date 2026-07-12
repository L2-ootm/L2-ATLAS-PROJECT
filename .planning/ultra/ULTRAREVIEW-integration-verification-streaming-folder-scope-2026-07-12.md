# ULTRAREVIEW — Integration Verification, Streaming, Folder Display, Workspace Scope

Date: 2026-07-12
Method: 3 parallel explore subagents + manual code tracing
Triggered by: operator asked ATLAS about its integrations, noticed streaming
broken, wrong folder shown, no workspace scope prompt

---

## 1. Integration Verification — 28 Claims Audited

ATLAS listed 28 integrations. Audit result: **17 confirmed, 9 partial, 2 fabricated**.

### Confirmed (real code exists)

| # | Integration | Evidence |
|---|------------|----------|
| 1 | Discord | Full bot: `services/discord-bot/bot/main.py` (L2Bot class, cogs, AI agent, tools) |
| 2 | Telegram | 5,861-line adapter: `foundation/atlas-hermes/gateway/platforms/telegram.py` |
| 4 | GitHub CLI | ATLAS adapter wrapping `gh`: `services/agent-runtime/atlas_runtime/tools/adapters/github.py` |
| 5 | Subagent delegation | `delegate_tool.py` + `subagent_service.py` + UI dialog |
| 6a | Claude Code CLI | `agents/claude_code.py` — drives `claude-agent-sdk` |
| 6b | OpenAI Codex CLI | 34+ files: `agent/codex_runtime.py`, transports, models |
| 7 | MCP client | 3,700-line client: `tools/mcp_tool.py` (stdio/HTTP/SSE/OAuth) |
| 12 | Web screenshots | `browser_vision` tool in `tools/browser_tool.py` |
| 13 | Webhooks | `gateway/platforms/webhook.py` (925 lines, HMAC, rate limiting) |
| 16 | Linear | `skills/productivity/linear/scripts/linear_api.py` (445-line GraphQL CLI) |
| 17 | Google Workspace | `skills/productivity/google-workspace/scripts/google_api.py` (1,221 lines) |
| 19 | PowerPoint | `skills/productivity/powerpoint/` (SKILL.md + scripts + schemas) |
| 20 | PDF | Read (pymupdf), OCR (marker-pdf), generate (reportlab) |
| 22 | Image generation | 5 backends: FAL, OpenAI, Codex, xAI, Krea |
| 23 | ComfyUI | Full skill with workflows, setup, batch execution |
| 24 | Spotify | `plugins/spotify/` (client + tools + tests) |
| 25 | YouTube | `skills/media/youtube-content/` (transcript API) |
| 26 | GIF search | `skills/media/gif-search/` (Tenor API via curl) |
| 27 | Audio TTS + songs | `tools/tts_tool.py` (10+ providers) + HeartMuLa skill |

### Partial (skill-based or incomplete)

| # | Integration | Reality |
|---|------------|---------|
| 3 | Email "via Himalaya" | Real IMAP/SMTP in `gateway/platforms/email.py`, but uses raw Python imaplib/smtplib, NOT Himalaya CLI. Agent fabricated the "Himalaya" detail. |
| 6c | OpenCode CLI | Only a provider profile (`plugins/model-providers/opencode-zen/`), not agent delegation like Claude Code/Codex. |
| 6d | MiMoCode | The agent-running tool itself, not an integration ATLAS built. |
| 9 | llama.cpp | Client-side compatibility code only (error recovery, grammar parse, metadata). Not bundled or directly integrated. |
| 11 | Browser "Playwright + Cloakbrowser" | Playwright used only for Chromium install. Actual browser backends: `agent-browser` CLI, Camofox (not Cloakbrowser), Browserbase cloud. Agent fabricated "Cloakbrowser". |
| 14 | Obsidian | Prompt-based skill (SKILL.md instructions), no dedicated API code. |
| 15 | Notion | Skill + curl instructions, not a built-in tool. |
| 18 | Airtable | Curl-based skill instructions, no built-in tool. |
| 21 | Word docs (.docx) | Side capability in PowerPoint/OCR skills, no dedicated tool. |
| 28 | SVG diagrams | Stubbed `skills/diagramming/` — only a 3-line DESCRIPTION.md, no implementation. |

### Fabricated (no evidence)

| # | Integration | Reality |
|---|------------|---------|
| 8 | "Native MCP — built-in native MCP client" | No MCP code in `native/atlas-core-rs/`. The MCP client is entirely in Python (`tools/mcp_tool.py`). Agent conflated the MCP catalog feature (`mcp_catalog.py`, `mcp_picker.py`) with a "native" Rust client. |
| 10 | "Jupyter — live kernel" | Zero evidence anywhere in the codebase. No jupyter, ipykernel, or notebook references. |

### Root cause of hallucination

The agent's identity prompt (`atlas_core.md`) says "use tools for current facts" but the agent was likely answering from training knowledge about Hermes capabilities rather than probing its actual tool registry. The `atlas_core.md` prompt is only 13 lines and contains no instruction to verify claims against available tools before responding. A "verify before claiming" directive would prevent this class of hallucination.

---

## 2. Response Streaming Not Working

### Symptom

Messages appear only when complete, not streamed token-by-token.

### Root cause: adapter never emits delta events

The TUI has infrastructure for streaming deltas (`message.part.delta` in
`sync.tsx:514-530`) but the adapter **never emits them**.

### Full data flow chain

```
Gateway SSE (lib.rs:359)
  Polls SQLite every 500ms (STREAM_POLL, line 30)
  Emits coarse "audit" events (completed llm_call snapshots)
       ↓
Gateway Client (gateway.ts:166-211)
  Reads SSE stream, parses frames — per-frame, works fine
       ↓
Chat Adapter (chat.ts:346-423)
  onRunEvent() translates audit → DonorPart
  appendPart() (chat.ts:334-343) creates NEW part with FULL text
  Emits message.part.updated (full replacement)
  *** NEVER emits message.part.delta ***
       ↓
EventBus Bridge (atlasFetch.ts:202-238)
  Forwards bus events as SSE — pass-through, works fine
       ↓
SDK SSE Client (sdk.tsx:76-111)
  Consumes SSE, 16ms batch window — works fine
       ↓
Sync Store (sync.tsx:493-530)
  message.part.updated → full part reconcile (what runs)
  message.part.delta → append text (EXISTS but NEVER TRIGGERED)
       ↓
TUI Render (session/index.tsx:1560-1592)
  Renders part.text — streaming cursor only, not text content
```

### Two layered problems

**Problem 1 — Coarse audit events (gateway/runtime layer):**
The gateway polls SQLite every 500ms. The Python runtime writes `llm_call`
audit rows containing the **completed** text/summary for that call — a
snapshot, not a stream of tokens. The gateway can only relay what the
runtime writes.

**Problem 2 — No delta emission (adapter layer):**
Even if the runtime emitted finer-grained events, the adapter would still
not stream them because `appendPart()` always creates a new part with the
full text and emits `message.part.updated`. The adapter **never** emits
`message.part.delta` (confirmed: zero occurrences in `src/adapter/`).

### Key file:line references

| Layer | File:Line | Status |
|-------|-----------|--------|
| Gateway SSE poll | `lib.rs:30` (STREAM_POLL=500ms) | Coarse but functional |
| Gateway SSE endpoint | `lib.rs:359-474` | Functional |
| Gateway client parse | `gateway.ts:166-211` | Functional |
| Adapter event translation | `chat.ts:346-423` | **Full-text only** |
| Adapter part emit | `chat.ts:334-343` | **message.part.updated only** |
| Adapter delta emit | — | **Missing entirely** |
| Sync delta handler | `sync.tsx:514-530` | **Exists but never triggered** |
| Sync update handler | `sync.tsx:493-511` | What actually runs |

### Fix required (two changes)

1. **Runtime layer**: The Python runtime needs to emit per-token (or per-chunk)
   audit events instead of only complete-call snapshots.
2. **Adapter layer**: `onRunEvent()` needs to detect delta events and emit
   `message.part.delta` via the bus, so the TUI's existing delta handler
   (`sync.tsx:514`) can append text incrementally.

---

## 3. Wrong Folder Displayed in TUI

### Symptom

TUI shows `~\Desktop\Projects\L2-ATLAS-PROJECT\services\atlas-terminal:main`
as the path — the atlas-terminal package directory, not the user's cwd.

### Root cause: subprocess cwd overwrites process.cwd()

**File:line:** `atlas_terminal.py:75`

```python
completed = subprocess.run(
    [bun, "run", "dev"],
    cwd=os.fspath(terminal_dir),   # <-- sets cwd to atlas-terminal package dir
    env=env,
    check=False,
)
```

The `cwd` parameter forces the Bun child process's working directory to
`services/atlas-terminal/`, not the user's original directory.

### Data flow chain

| Step | File:Line | What happens |
|------|-----------|--------------|
| 1. User runs `atlas` | `main.py:178-185` | `_root()` calls `_launch_atlas_terminal()` |
| 2. Launcher spawns bun | `atlas_terminal.py:73-78` | `subprocess.run(cwd=terminal_dir)` — **BUG HERE** |
| 3. TUI reads cwd | `main.tsx:43` | `directory: process.cwd()` — returns atlas-terminal dir |
| 4. SDK stores it | `sdk.tsx:24` | `currentDirectory = props.directory` |
| 5. Project context seeds | `project.tsx:14-19` | `directory: sdk.directory ?? ""` |
| 6. Adapter returns it | `atlasFetch.ts:330` | `process.cwd()` for `/path` endpoint |
| 7. Footer displays it | `home/footer.tsx:10`, `sidebar/footer.tsx:17` | `props.api.state.path.directory \|\| process.cwd()` |

### Fix

Capture the user's cwd before launching the subprocess and pass it as an
environment variable (e.g., `ATLAS_WORK_DIR`) to the Bun process. Then
`main.tsx` reads `process.env.ATLAS_WORK_DIR ?? process.cwd()`.

---

## 4. No Workspace Scope Prompt

### Symptom

The `atlas` command should ask "execute inside this folder only, or default
ATLAS workspace?" but currently doesn't.

### Root cause: no prompt exists in the launch path

| File:Line | What's there |
|-----------|-------------|
| `main.py:177-185` | `_root()` directly calls `_launch_atlas_terminal()` — no `typer.prompt()`, no confirmation |
| `atlas_terminal.py:47-81` | `launch()` takes only `gateway_url`, immediately spawns subprocess |
| `go_tui.py:137-152` | Legacy Go TUI also has no scope prompt |
| `main.tsx:43` | Directory unconditionally set to `process.cwd()` |

### What exists but isn't used at launch

The TUI has an experimental workspace feature (`ATLAS_TUI_EXPERIMENTAL_WORKSPACES`
flag in `sdk.tsx:90-94`) that syncs workspace lists from the gateway **after**
launch. This is reactive UI state, not a launch-time scope prompt.

### What would be needed

A prompt in `_root()` (or `_launch_atlas_terminal()`) before spawning the TUI:
"Execute inside [current folder], or switch to default ATLAS workspace?" The
user's choice would be passed as an env var or CLI arg.

---

## 5. "Hardcoded to Command Center Loop"

### Symptom

ATLAS always presents the Command Center WP status table regardless of what
the user asks. The user says it "makes sense as the spine of atlas, but being
hardcoded is not cool."

### Root cause: context injection is automatic, not opt-in

**File:line:** `context_service.py:197-214`

```python
# Loop-engineering operating contract (Layer 7)
if focus is not None:
    lines.append("## Operating Contract")
    lines.append(
        "- Advance the Current Focus and its goals above; treat the open tasks "
        "as the actionable surface and the observations as prior learning."
    )
    ...
```

The Operating Contract (including the directive to "Advance the Current Focus
and its goals") is injected into **every** agent run whenever a Current Focus
exists in the database. There is no flag to suppress it, and no per-surface
control over whether it's included.

### What's happening

1. User set a Current Focus in the database (likely titled "Command Center
   Loop" with WP-0 through WP-6 as goals)
2. Every `atlas` prompt triggers `assemble_context()` in `context_service.py`
3. The focus + goals + Operating Contract get injected as system context
4. The agent faithfully presents this context in its response — it's doing
   exactly what the context tells it to do

### This is NOT a bug in the agent

The agent is working correctly — it receives the Command Center context and
presents it. The issue is that the context injection has no opt-out mechanism.
The operator context should be:
- **Optional** per run (flag to skip context injection)
- **Surface-aware** (TUI interactive prompts might not need the full context;
  mission runs do)
- **Scoped** (the Operating Contract instruction should be conditional on
  whether the user's prompt relates to the Focus)

### Fix locations

| File | Change |
|------|--------|
| `context_service.py:197` | Gate Operating Contract on a flag, not just `focus is not None` |
| `atlas_terminal.py` | Pass a flag (e.g., `ATLAS_SKIP_CONTEXT=1`) for interactive TUI sessions |
| `main.py` (CLI) | Add `--no-context` flag to bare `atlas` command |
| `native.py:314` | Respect the skip flag when building system_message |

---

## Summary

| Issue | Root Cause | Severity | Fix Complexity |
|-------|-----------|----------|----------------|
| Integration hallucination | Agent answers from training knowledge, not tool registry | Medium | Low (add verify-before-claim directive to `atlas_core.md`) |
| No streaming | Adapter never emits `message.part.delta`; runtime emits coarse snapshots | High | High (two-layer fix: runtime + adapter) |
| Wrong folder | `subprocess.run(cwd=terminal_dir)` overwrites user's cwd | Medium | Low (pass cwd as env var) |
| No workspace scope | No prompt exists in launch path | Low | Low (add `typer.prompt()` before spawn) |
| Hardcoded context | Operating Contract injected automatically on every run | Medium | Medium (flag + surface-aware gating) |

---

## Fix Status — 2026-07-12 follow-up session

| Issue | Status | Commit |
|-------|--------|--------|
| 1. Integration hallucination | FIXED — `atlas_core.md` now requires enumerating the tool registry/skills before asserting capabilities; prompt goldens regenerated | 22f1041b |
| 2. No streaming | **OPEN** — requires runtime per-token audit events + adapter `message.part.delta`; deferred as its own slice | — |
| 3. Wrong folder | FIXED — launcher exports `ATLAS_WORK_DIR`; `main.tsx` chdirs back before any `process.cwd()` read | 059c63ba |
| 4. No workspace scope | FIXED — TTY-only prompt in `_root()`/`atlas tui`: this folder vs `workspace_service.global_root()` | 059c63ba |
| 5. Hardcoded context | FIXED — `include_operator_context` param > `ATLAS_SKIP_CONTEXT` env > `context.inject_operator_context` config knob; `--no-context` CLI flag; contract now says don't recite Focus on unrelated prompts | b4a4ce11 |

Verification: agent-runtime 775 passed + 2 new gating tests; atlas-core 97
passed; atlas-terminal typecheck + 52 tests + `--smoke` (LIVE gateway) green.
Interactive UAT still owed: scope prompt UX, footer folder, `--no-context` run.
