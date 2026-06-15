# L2 ATLAS Deep Research Backlog

Date: 2026-06-04

## Purpose

This backlog defines the research needed before L2 ATLAS becomes a serious product, not a pile of copied ideas.

## Research Rule

Every research item must produce:

1. summary;
2. reusable patterns;
3. risks/licensing concerns;
4. what to copy, wrap, fork, or ignore;
5. decision recommendation.

Save outputs under:

`docs/research/YYYY-MM-DD_<topic>.md`

---

## R0 — Local L2 source audit

### R0.1 L2-Atlas deep audit

Questions:
- Which code modules are mature enough to port?
- How do mission parser, policy engine, executor, heartbeat, shell, skills registry work?
- What tests already define behavior?
- What is Windows-specific vs product-general?

Output:
- `docs/research/L2_ATLAS_SOURCE_AUDIT.md`
- extraction candidate list;
- risk list;
- code import plan.

### R0.2 L2-atlas-hermes audit

Questions:
- What recovery/snapshot rules should become product features?
- How should ATLAS wrap Hermes profiles/config/memory safely?
- Which redaction/secret-scan rules become built-in?

### R0.3 L2-BOT audit

Questions:
- Which Discord/channel management patterns are reusable?
- What should become integration runtime vs external harness?

### R0.4 L2-KNOWLEDGE-ROUTER audit

Questions:
- Does it contain useful RAG/routing/search patterns?
- Can it inform LLM Wiki + retrieval hybrid?

### R0.5 l2-agent-skills audit

Questions:
- Which skills/runbooks should ship as default ATLAS procedures?
- What skill schema should ATLAS use?

---

## R1 — Hermes foundation research

Questions:
- Best way to run Hermes as service/library/subprocess?
- How to capture sessions, tool calls, outputs, costs, memory changes?
- How to expose Hermes profiles in ATLAS UI?
- What Hermes features should be product-surfaced first: tools, skills, cron, MCP, gateway, memory, sessions?
- What Hermes lacks that GSD/imported workflow patterns fix?

Output:
- `docs/architecture/HERMES_ADAPTER.md`
- adapter API proposal;
- limitations list;
- fork/no-fork decision gate.

---

## R2 — GSD / imported workflow research

Questions:
- Which planning/execution/review patterns are superior to Hermes defaults?
- Which skills should become ATLAS mission templates?
- How to implement phase plans, UAT, audits, reviews, workstreams?

Output:
- `docs/research/OPENCLAW_GSD_WORKFLOW_AUDIT.md`
- ATLAS mission template model.

---

## R3 — LLM Wiki / knowledge runtime research

Sources:
- attached LLM Wiki pattern;
- current Obsidian vault;
- Command Center / Personal Data KB split;
- qmd / markdown search tooling.

Questions:
- How to combine raw sources, LLM Wiki, RAG, memory graph, session search?
- How to prevent wiki decay?
- How to file query answers back into wiki?
- What should be visible in cockpit?

Additional retrieval spike:
- Evaluate `turbovec` as an optional compressed local semantic index behind SQLite metadata and ATLAS policy filters.
- Output: `docs/research/2026-06-06_TURBOVEC_LOCAL_RETRIEVAL_SPIKE.md`.

Output:
- `docs/architecture/KNOWLEDGE_RUNTIME.md`;
- `wiki/SCHEMA.md` v1;
- ingest/lint/query runbooks.

---

## R4 — gbrain research

Questions:
- What is gbrain’s memory model?
- Does it use graph, embeddings, markdown, agents, or dashboards?
- What can be adapted to ATLAS memory?
- Does it solve personal/company brain better than Hermes memory?

Output:
- `docs/research/GBRAIN_AUDIT.md`

---

## R5 — pulse-ai research

Questions:
- How does pulse-ai model monitoring, alerts, briefs, and event intelligence?
- What should ATLAS Pulse monitor?
- How should pulse events become missions/tasks/wiki updates?

Output:
- `docs/architecture/PULSE_RUNTIME.md`

---

## R6 — Twenty CRM research

Questions:
- What data model should ATLAS copy/adapt: people, companies, opportunities, tasks, notes?
- Should ATLAS integrate with Twenty, fork it, or build smaller CRM primitives?
- How do CRM records connect to wiki/missions/channels?

Recommendation bias:
- Do **not** fork Twenty first.
- Start with minimal AI-native CRM primitives.

Output:
- `docs/architecture/CRM_RUNTIME.md`

---

## R7 — WhatsApp/channel research

Sources:
- Hermes gateway;
- L2-BOT;
- imported channel/gateway patterns;
- OpenWA;
- Baileys / official Meta API options.

Questions:
- Which path is stable enough for product use?
- What is allowed by ToS and acceptable risk?
- How should approvals work for outbound messages?
- How to log and summarize conversations without privacy violation?

Output:
- `docs/architecture/CHANNEL_RUNTIME.md`
- WhatsApp adapter decision matrix.

---

## R8 — Rust native client / overlay / real-time STT research

Questions:
- What is the best Rust-first desktop architecture: egui, iced, Slint, custom wgpu, or thin Tauri shell?
- How do we avoid Electron-class bloat while keeping a perfect operator UX?
- How to support real-time STT?
- How to show seamless command overlays?
- How to capture active context safely?
- How to integrate voice with Hermes/ATLAS STT/TTS providers?
- What native concepts from Odysseus should influence ATLAS?

Candidate stack:
- Rust-native desktop app first;
- Tauri only if it remains a thin, fast shell;
- Electron is a negative baseline, not default;
- Whisper/faster-whisper/Parakeet/ONNX for STT;
- WebSocket/SSE or local IPC for runtime events;
- global hotkey + command palette;
- optional Linux/Hyprland integrations later.

Output:
- `docs/architecture/NATIVE_OVERLAY_AND_VOICE.md`
- `docs/research/ODYSSEUS_AUDIT.md`

---

## R9 — Token/context optimization research

Questions:
- How does ATLAS decide what context to load?
- How to classify source types: codebase, chat, wiki, CRM, email, repo state?
- How to choose summarize vs retrieve vs load raw?
- How to measure token efficiency?

Output:
- `docs/architecture/CONTEXT_ENGINE.md`

---

## R10 — Market and wedge research

Questions:
- Who buys first: technical founders, agencies, small teams, AI operators, internal ops teams?
- What pain is most acute?
- What is the smallest demo that makes people say “I want this”?
- What competitors exist: Lindy, Relevance, Gumloop, n8n AI agents, OpenWebUI, Dify, CrewAI, LangGraph Studio, Twenty, Notion AI, NotebookLM?

Output:
- `docs/research/MARKET_WEDGE.md`

---

## Recommended research order

1. R0.1 L2-Atlas audit.
2. R1 ATLAS/Hermes runtime research.
3. R3 Knowledge Runtime / LLM Wiki.
4. R8 Native overlay/STT as differentiator track.
5. R5 Pulse Runtime.
6. R6 CRM.
7. R7 WhatsApp.
8. R10 Market wedge.

## What not to research yet

- Billing.
- Multi-cloud enterprise deployment.
- Full CRM clone.
- MCP marketplace UI.
- Advanced self-modification.

These matter later, not for the first ship.
