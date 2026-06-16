# Agent-Reach Integration Plan — ATLAS Internet Capability Layer

**Date:** 2026-06-15  
**Repo:** https://github.com/Panniantong/Agent-Reach  
**Inspected commit:** `71b85f8b978d8a8c5febd7152c602d2d4a5d2eea`  
**License:** MIT  
**Package:** `agent-reach` v1.5.0  
**Language:** Python 3.10+  
**Status:** approved for ATLAS documentation and future implementation planning; use all functions intentionally.

## Decision update

Davi's directive: document Agent-Reach as a real ATLAS capability layer, not merely a cautious external curiosity.

Earlier notes about cookies, login surfaces, platform volatility, and ToS are implementation design notes, not reasons to avoid use. For an agentic developer/operator environment, these are normal capability-layer concerns:

- credentials remain local;
- the operator controls installation and login;
- `doctor` surfaces readiness;
- fallbacks are expected;
- channel breakage is handled by route updates.

ATLAS should treat Agent-Reach as a useful reference and candidate sidecar for full internet reach.

## Why Davi flagged it

Agent-Reach addresses a major ATLAS need: agents should not repeatedly reinvent platform access. ATLAS needs a reach layer that can search/read across web platforms, diagnose broken routes, and expose readiness cleanly inside a TUI/native shell.

It targets:

- web page reading;
- YouTube transcript/search;
- RSS;
- GitHub;
- Twitter/X;
- Reddit;
- Bilibili;
- Xiaohongshu;
- LinkedIn;
- semantic web search via MCP/Exa;
- podcast/audio transcription;
- health checks and route diagnosis via `agent-reach doctor`.

## Repository summary

From README/package metadata:

> “Give your AI Agent eyes to see the entire internet. Search + Read 10+ platforms.”

Core model:

- Agent-Reach is a capability/routing/install/diagnostic layer.
- It chooses and prepares upstream tools per platform.
- It uses ordered backend fallbacks.
- It gives agents practical internet reach without each agent manually solving every platform.

## CLI surface inspected

```txt
agent-reach [-h] [-v] [--version]
  {setup,install,configure,doctor,uninstall,skill,format,transcribe,check-update,watch,version}
```

Commands:

| Command | Purpose | ATLAS mapping |
|---|---|---|
| `setup` | Interactive configuration wizard | `atlas reach setup` |
| `install` | One-shot installer with flags | `atlas reach install` / admin-only |
| `configure` | Set config or auto-extract cookies from browser | `atlas reach configure` / credential surface |
| `doctor` | Check platform availability | `atlas reach doctor` + TUI readiness panel |
| `uninstall` | Remove config/tokens/skill files | `atlas reach uninstall` |
| `skill` | Manage agent skill registration | Convert to ATLAS skill/tool docs |
| `format` | Clean platform API output, currently `xhs` | utility wrapper |
| `transcribe` | Transcribe URL/local audio via Groq/OpenAI Whisper | `atlas reach transcribe` |
| `check-update` | Check new versions/changes | scheduled maintenance |
| `watch` | Quick health + update check | cron/watchdog integration |
| `version` | Show version | diagnostics |

Important flags:

```bash
agent-reach install --env local|server|auto
agent-reach install --proxy <proxy>
agent-reach install --safe
agent-reach install --dry-run
agent-reach install --channels twitter,xiaoyuzhou,xueqiu,xiaohongshu,reddit,bilibili,linkedin,all
agent-reach configure proxy|github-token|groq-key|openai-key|twitter-cookies|youtube-cookies|xhs-cookies <value>
agent-reach configure --from-browser chrome|firefox|edge|brave|opera
agent-reach doctor --json
agent-reach uninstall --dry-run --keep-config
agent-reach skill --install|--uninstall
agent-reach format xhs
agent-reach transcribe <source> --provider auto|groq|openai -o <file>
```

## Stack / dependencies

From `pyproject.toml`:

- Python >=3.10
- `requests`
- `feedparser`
- `python-dotenv`
- `loguru`
- `pyyaml`
- `rich`
- `yt-dlp`

Optional:

- `playwright`
- `browser-cookie3`
- `mcp[cli]`

CLI entrypoint:

```txt
agent-reach = agent_reach.cli:main
```

## Supported channels from repo docs

| Channel | Notes | ATLAS use |
|---|---|---|
| Web | Jina Reader style reading | source acquisition, scholarship research, documentation verification |
| YouTube | subtitles + search via yt-dlp | technical learning, transcript ingestion, product research |
| RSS | feedparser | monitoring blogs, universities, scholarships, release notes |
| Search | Exa via MCP/mcporter | broad research when search tool quality matters |
| GitHub | gh CLI | repo vetting, issue/PR research, OSS monitoring |
| Twitter/X | CLI/OpenCLI/browser-login routes | product/public sentiment; optional authenticated mode |
| Reddit | login/browser-state routes | bug/community research; optional authenticated mode |
| Bilibili | bili-cli/OpenCLI fallback | technical/video research for Chinese ecosystem |
| Xiaohongshu | OpenCLI/MCP/xhs-cli routes | market/social research where relevant |
| LinkedIn | MCP/Jina fallback | organization/person/company research |
| V2EX/Xueqiu/podcasts | additional channels | niche research and audio ingestion |

## ATLAS integration thesis

ATLAS should not merely “have web search.” It should have a structured reach layer:

```txt
operator intent → ATLAS reach command/tool → Agent-Reach route/doctor → upstream backend → source snapshot → wiki/project context
```

Agent-Reach can be used as:

1. **External CLI sidecar** — quickest and safest integration.
2. **ATLAS reach adapter** — wrapper commands under `atlas reach ...`.
3. **TUI panel** — channel readiness, missing credentials, backend selected.
4. **Source-ingestion bridge** — read/search results become LLM Wiki/source snapshots.
5. **Cron/watchdog source monitor** — `agent-reach watch` or RSS/search checks.
6. **Skill/runbook** — teach agents which channels exist and how to call them.

## Proposed ATLAS command surface

```bash
atlas reach doctor [--json]
atlas reach setup
atlas reach install --channels web,youtube,rss,github,search
atlas reach install --channels all
atlas reach configure <channel>
atlas reach web <url>
atlas reach youtube <url-or-query>
atlas reach rss <feed-url>
atlas reach github <repo-or-query>
atlas reach search <query>
atlas reach transcribe <url-or-file>
atlas reach watch
atlas reach update-check
```

Initial wrappers can shell out to `agent-reach` and/or the upstream tools it installs. Later wrappers can become native ATLAS tools if needed.

## TUI/native shell placement

In the v1.1 ATLAS Agent Harness, include a Reach panel:

```txt
REACH
  web        ready    Jina Reader
  youtube    ready    yt-dlp
  rss        ready    feedparser
  github     ready    gh authenticated
  search     ready    Exa/mcporter
  twitter    login    cookie/browser route missing
  reddit     login    browser route missing
  xhs        login    cookie route missing
```

Operator actions:

- `Enter` opens setup instructions for a channel.
- `d` runs doctor.
- `j` exports JSON readiness.
- `r` retries route probing.
- `c` configures credentials/cookies locally.

## Implementation posture

Use all functions, but gate them by operator intent:

| Capability | Default | Notes |
|---|---|---|
| Web/RSS/YouTube/GitHub public | enabled after install | low friction, high utility |
| Search via MCP/Exa | enabled after setup | document dependency |
| Transcription | enabled if Groq/OpenAI key exists | use local output files when needed |
| Twitter/Reddit/XHS/LinkedIn login routes | available but explicit | not a blocker; just requires operator-provided session/cookie/browser state |
| Browser cookie extraction | explicit operator command | useful for devs; keep local |
| Uninstall | exposed | important for reversibility |

## Security and credential handling as implementation rules

These are not blockers; they are requirements:

- Keep cookies/tokens local.
- Never commit Agent-Reach config, cookies, or exported browser state.
- Redact secrets from `doctor --json` before storing in project docs.
- Store only readiness summaries in repo/planning files.
- Any social/login channel should be activated by explicit operator action.
- Prefer local `~/.agent-reach/` state, not project-local credentials.
- Public-source channels should be safe defaults.

## Development tasks for ATLAS

### P0 — Documentation and planning

- [x] Inspect Agent-Reach repo and CLI surface.
- [x] Document command mapping to ATLAS.
- [x] Reframe risks as implementation constraints, not adoption blockers.
- [ ] Add Agent-Reach to v1.1/v1.x backlog as `Reach capability layer`.
- [ ] Decide if first integration lives under `atlas reach` or as a Hermes/ATLAS skill.

### P1 — Spike

- [ ] Install Agent-Reach in isolated environment.
- [ ] Run `agent-reach doctor --json`.
- [ ] Test public channels:
  - [ ] web page read;
  - [ ] YouTube transcript;
  - [ ] RSS;
  - [ ] GitHub public repo;
  - [ ] search route.
- [ ] Test `transcribe` with a small public audio/video URL if key exists.
- [ ] Save readiness report without secrets.

### P2 — ATLAS wrapper

- [ ] Add `atlas reach doctor`.
- [ ] Add `atlas reach install --dry-run`.
- [ ] Add `atlas reach web <url>`.
- [ ] Add `atlas reach rss <url>`.
- [ ] Add `atlas reach transcribe <source>`.
- [ ] Add unit tests using mocked subprocess calls.
- [ ] Add redaction tests for JSON output.

### P3 — Native/TUI integration

- [ ] Add Reach readiness panel.
- [ ] Show backend selected per channel.
- [ ] Show missing setup actions.
- [ ] Add command launcher for setup/configure.
- [ ] Export channel readiness into ATLAS system context.

### P4 — Logged-in/social channels

- [ ] Add explicit operator flow for Twitter/X cookies.
- [ ] Add explicit operator flow for Reddit/browser route.
- [ ] Add explicit operator flow for LinkedIn route.
- [ ] Add explicit operator flow for XHS route.
- [ ] Add docs about local-only credential state.

## Placement in ATLAS roadmap

Recommended insertion:

- v1.1: document and expose as planned harness capability.
- v1.x: implement `atlas reach doctor` and public-channel wrappers.
- v2/Pulse: use for scheduled monitoring and source acquisition.

This should not distract from v1.1 P0s, but it belongs in the agent harness because a serious ATLAS operator shell needs internet capability readiness.

## Verdict

**Approved for full ATLAS planning.**

Agent-Reach is highly aligned with ATLAS as an agentic developer/operator environment. Use it as a sidecar first, then promote stable pieces into `atlas reach` and TUI readiness surfaces. The credential/login complexity is normal operational reality, not a reason to avoid the tool.
