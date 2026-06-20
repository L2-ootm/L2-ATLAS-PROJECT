# Harness Cherry-Pick — Pi & OpenCode Pattern Intake

**Date:** 2026-06-20
**Author:** session intake (item #5 of the six-item in-flight scope; phase
`.planning/phases/10.0.3-harness-cherrypick/`)
**Stance:** *Borrow the direction, write our own code.* Patterns and page/feature ideas are not
copyrightable; direct code/asset reuse is license-gated and must be verified per source (mirror the
Odysseus baseline stance in STATE). **No repos were cloned**; this is a research intake.

## Subjects

| Harness | What it is | Source | License (verify before any reuse) |
|---|---|---|---|
| **Pi** | Minimal, composable terminal coding harness from the `pi-mono` toolkit (Mario Zechner). 4-tool core (Read/Write/Edit/Bash) + a unified `pi-ai` LLM API (20+ providers); everything else (skills, sub-agents, plan mode, permission gates, path protection, sandbox, SSH exec, MCP, custom editors, status bars) is a TypeScript **Extension**. Runs in 4 modes: interactive, print/JSON, RPC, SDK. | `github.com/earendil-works/pi` (npm `@earendil-works/pi-coding-agent`); related: `can1357/oh-my-pi` | TBD — confirm at adoption |
| **OpenCode** | Terminal-first AI coding agent (SST). Bun/TypeScript **client/server** architecture; provider-agnostic; MCP; **LSP client** exposing real diagnostics to the agent as a tool; TUI; CLI mode auto-approves permissions; real-time collab via Cloudflare Durable Objects. | `github.com/sst/opencode`, `github.com/opencode-ai/opencode` | TBD (MIT-family expected) — confirm at adoption |

## ATLAS baseline (what we already have)

- Harness = vendored Hermes `AIAgent.run_conversation()` — 50+ tools, 28 providers, credential pool,
  context compression, plugin system (hooks/memory/model), MCP.
- Rust gateway (REST/SSE over SQLite) + cockpit; Python messaging gateway (channels).
- Agent runtimes: `NativeAtlasAgent` (harness), `ClaudeCodeAgent` (SDK).
- This session added: config-service (`~/.atlas/config.yaml`), memory router (FTS5 retrieval into
  context assembly), channel cockpit management.
- Planned: Tool Manifest v0 (10.0.4), model_router cutover (10.3), auth store (10.1), ATLAS TUI over a
  stdio JSON-RPC `tui_gateway` (10.4), agentic chat `atlas chat -q` (10.2).

## Survey dimensions

Session/permission model · tool manifest & registry · provider routing & fallback · agent loop / plan
mode / checkpointing · client architecture & run modes · context/memory · extensibility (plugins/MCP/
skills) · code-edit safety · collaboration.

## Findings — classified

| # | Pattern (source) | ATLAS state | Verdict | Rationale | Owning phase |
|---|---|---|---|---|---|
| 1 | **Minimal trusted tool core + opt-in extensions** (Pi: 4-tool core; rest composed) | 50+ always-on tools | **ADAPT** | ATLAS's Tool Manifest v0 should declare a small trusted core (read/search/edit/bash) at low risk and make everything else opt-in and risk-tiered, instead of a monolithic surface. Reduces blast radius and matches read-only-by-default. | 10.0.4 |
| 2 | **Run-mode taxonomy: interactive / print(JSON) / RPC / SDK** (Pi) | CLI + gateway; SDK-ish (claude-agent-sdk) | **ADOPT** | Make this the ATLAS agent-surface contract: `atlas chat -q`/`--json` (one-shot), interactive TUI, **RPC over stdio JSON-RPC** (exactly the planned `tui_gateway`), embeddable SDK. Clean, already half-planned. | 10.2 (one-shot/json), 10.4 (RPC) |
| 3 | **LSP client as an agent tool** (OpenCode: real diagnostics via language servers) | None | **ADOPT** | High leverage for code-work missions — the agent sees real type/lint errors instead of guessing. Add a gated `lsp.diagnostics` tool to the harness toolset. Strong differentiator with low conceptual cost. | 10.0.4 (new tool) / harness |
| 4 | **Composable permission gates: path protection + sandbox levels + SSH-exec** (Pi) | risk-gated policy + approval (internal auto / outward approve) | **ADAPT** | Fold path-allowlists and explicit sandbox levels into the ATLAS policy engine; surface them in the cockpit (10.0.4 "permissions visible in UI"). Keep ATLAS's audit-first + risk-tier model as the spine. | 10.0.4 |
| 5 | **Attach multiple clients to one live agent session** (OpenCode client/server) | client/server exists (gateway+cockpit), but agent runs via run_executor/daemon, not a long-lived attachable session | **ADAPT** | Let the Console attach to a *live* run's stream and interact (not just watch SSE) — reuse the existing SSE+audit plumbing; promote the run_executor daemon to an attachable session host. | console / runtime |
| 6 | **Hash-anchored edits** (oh-my-pi: edits keyed to content hash to reject stale writes) | harness edit tools | **ADOPT (consider)** | Cheap robustness win for the native agent's write path — refuse edits when the anchor content drifted, preventing silent clobbers. Evaluate against Hermes' existing edit tool. | harness toolset |
| 7 | **Unified provider API surface** (Pi `pi-ai`; OpenCode provider-agnostic) | 28 providers via Hermes + planned model_router | **SKIP (covered)** | Already have breadth; adopt only the *ergonomic* idea of one clean provider interface for the 10.3 model_router cutover. | 10.3 (reference) |
| 8 | **Extension/plugin ergonomics** (Pi TS Extensions; skills/templates/themes) | Hermes plugin system; 90+ skills; operations (premade instructions) | **SKIP (covered)** | ATLAS operations ≈ Pi prompt templates; Hermes plugins ≈ Pi extensions. Keep as a DX reference for ATLAS skill/extension authoring, not a port. | — |
| 9 | **Real-time collab via Cloudflare Durable Objects** (OpenCode) | local-first, single-operator, loopback-only | **SKIP (anti-fit)** | Conflicts with ATLAS's local-first, audit-owned, no-external-calls posture. Not adopted. | — |

## Recommended adoptions (ranked)

1. **LSP-diagnostics tool** (#3) — highest leverage, self-contained, slots into the Tool Manifest.
2. **Run-mode taxonomy incl. stdio JSON-RPC** (#2) — directly shapes 10.2 + the 10.4 `tui_gateway`.
3. **Minimal trusted core + risk-tiered manifest** (#1) and **composable permission gates** (#4) —
   converge on the 10.0.4 manifest + permissions-in-UI work.
4. **Attachable live agent session** (#5) and **hash-anchored edits** (#6) — opportunistic robustness.

## License & ethics gate

Before any *code* is lifted from Pi or OpenCode: confirm each repo's license, retain notices, and prefer
clean-room reimplementation of the *pattern*. Ideas (LSP-as-tool, run-mode taxonomy, minimal core) are
free to adopt; verbatim source/asset reuse is gated exactly like the Hermes/Odysseus precedent.

## Notes

- "PI" resolved to the `pi-mono` coding harness (earendil-works/pi), not Inflection's consumer "Pi".
- OpenCode previously appeared in-tree only as a *provider* benchmark
  (`docs/research/FREELLMAPI_OPENCODE_KILO_BENCHMARK_2026-06-07.*`); this intake covers it as a *harness*.

Sources: [pi (earendil-works)](https://github.com/earendil-works/pi) ·
[oh-my-pi](https://github.com/can1357/oh-my-pi) ·
[awesome-cli-coding-agents](https://github.com/bradAGI/awesome-cli-coding-agents) ·
[OpenCode (SST)](https://github.com/sst/opencode) ·
[opencode-ai/opencode](https://github.com/opencode-ai/opencode)
