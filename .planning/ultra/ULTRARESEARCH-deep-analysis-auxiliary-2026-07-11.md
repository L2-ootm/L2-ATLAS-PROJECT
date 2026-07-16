# Deep Analysis: Ada-SI + meetily + reverse-skill + proxifly + emilkowalski/skills

**Date:** 2026-07-11  
**Purpose:** Rigorous technical analysis for ATLAS integration

---

## 1. nazirlouis/Ada-SI — Self-Improving AI Assistant (67 stars)

### Architecture
- **Backend:** Python 3.12 (FastAPI + Uvicorn + httpx)
- **Frontend:** React 19 + TypeScript + Vite 8
- **LLM routing:** LiteLLM proxy (multi-provider: OpenAI, Anthropic, Gemini, Groq)
- **Tool execution:** Separate FastAPI service + isolated Python venv
- **UI:** Three.js + Framer Motion + Zustand + react-markdown
- **Persistence:** File-based (staging/) + browser localStorage (no DB)

### Key Systems
- **Skill Forge:** Scout proposes tool plan → plan approval → code generation → sandbox test → contract test → UI preview → pip review → install. Human-in-the-loop gates at pip approval and UI preview.
- **Batch Forge:** 2-10 independent tools forged in parallel via `propose_tool_batch`.
- **Gamification:** XP system (levels 1-50), rank titles, level-up effects, 3D avatar visualizer.
- **Persona:** OpenClaw-style markdown files (SOUL, IDENTITY, MEMORY) shape Scout behavior. Bootstrap ritual for identity setup. Heartbeat timer for background LLM calls.
- **Voice:** Browser Web Speech API for input, ElevenLabs TTS for read-aloud.
- **Security:** No auth, no sandboxing (Python venv only), secrets in .env + staging/secrets.json. Explicitly warns: "single user, localhost, trusted machine only."

### Quality
- 38 commits, 23 forks, no releases
- No tests visible
- Docker Compose available
- Windows native install scripts (PowerShell)

### ATLAS Fit
- **What to take:** Skill forge pipeline pattern (plan → test → install with approval gates). Gamification UX patterns (XP, levels). Persona system (SOUL/IDENTITY/MARK markdown files).
- **What NOT to take:** Security model (no auth, no sandboxing). LiteLLM dependency (ATLAS has own provider mesh). React frontend (ATLAS uses React but different architecture).
- **Integration:** Reference only. Do not vendor. Study skill forge pipeline for ATLAS v1.3 self-evolution.
- **License:** MIT

### Risk
- Very young project (67 stars, no releases) — HIGH maintenance risk
- Security model is weak — must not influence ATLAS security architecture
- Python venv isolation is not real sandboxing

---

## 2. Zackriya-Solutions/meetily — Meeting Assistant (23.1k stars)

### Architecture
- **Backend:** Rust (46.2%) — core transcription + audio processing
- **Frontend:** TypeScript (29.7%) — Next.js
- **Desktop shell:** Tauri (macOS + Windows)
- **C++ (9.9%):** GPU acceleration bindings
- **AI providers:** Ollama (local), Claude, Groq, OpenRouter, OpenAI-compatible
- **Transcription:** Parakeet (NVIDIA) or Whisper (OpenAI), ONNX runtime
- **GPU:** Apple Metal + CoreML (macOS), CUDA (NVIDIA), Vulkan (AMD/Intel)

### Key Systems
- **Live transcription:** 4x faster Parakeet/Whisper. Real-time speaker diarization (PRO).
- **Audio mixing:** Microphone + system audio simultaneously. Intelligent ducking, clipping prevention.
- **Summarization:** Ollama (local recommended), Claude, Groq, OpenRouter, OpenAI.
- **Import/Enhance:** Re-transcribe audio files with different models or languages.
- **Export:** PDF, DOCX, Markdown (PRO).
- **Privacy:** All processing local. No cloud required.

### Quality
- 556 commits, 2.4k forks, 23.1k stars — very active
- Rust backend = aligns with ATLAS D-022
- Tauri shell = aligns with ATLAS no-bloat doctrine
- 11 releases, latest v0.4.0 (June 2026)
- MIT license

### ATLAS Fit
- **Gap addressed:** Phase 13 Voice Integration (STT/TTS). ATLAS has zero voice capability.
- **Integration options:**
  - (a) Ship as ATLAS module (like Cashflow)
  - (b) Use transcription Rust crate as library
  - (c) Reference architecture for ATLAS voice module
- **Recommended:** Option (c) for now — reference architecture. Option (a) for v2.0.
- **Effort:** HIGH — different architecture, needs module adapter
- **License:** MIT

### Risk
- **Tauri dependency:** ATLAS doesn't use Tauri yet — would need to add
- **GPU requirements:** Not all ATLAS users have GPUs — needs CPU fallback
- **Maintenance:** Very active, well-funded — LOW risk

---

## 3. zhaoxuya520/reverse-skill — Security Skill Router (8.1k stars)

### Architecture
- **Languages:** PowerShell 32%, Java 30.2%, Shell 28.6%, JavaScript 4.8%, Python 3.6%
- **Routing:** RULES.md → Skill Router → Target Skill → Tool/MCP/Script → Report + experience沉淀
- **Tools:** jadx, Frida, IDA Pro, radare2, Ghidra, nmap, apktool
- **MCP:** Burp Suite MCP integration

### Skill Inventory
| Domain | Skills |
|--------|--------|
| APK Reverse | skills/apk-reverse/ |
| Binary RE | skills/ida-reverse/, skills/radare2/ |
| JS Reverse | skills/js-reverse/ |
| Pentest | skills/pentest-tools/ |
| Firmware/IoT | skills/firmware-pentest/ |
| Patch Diff | skills/patch-diff-exploit/ |
| Pwn | skills/pwn-chain/ |
| EDR Bypass | skills/edr-bypass-re/ |
| LLM Security | skills/llm-security/ |
| CTF | CTF-Sandbox-Orchestrator/ (40+ sub-skills, GPLv3) |
| Reports | skills/diagram-generator/, skills/docs-generator/ |

### Quality
- 71 commits, 1.3k forks
- Bilingual (Chinese + English)
- RULES.md + routing.md for AI agent guidance
- Tool-index.md auto-generated for local tools

### ATLAS Fit
- **Gap addressed:** No security/pentest skills in ATLAS
- **Integration:** Import MIT-licensed skills (apk-reverse, js-reverse, pentest-tools, etc.). Reference CTF patterns but do NOT vendor GPLv3 CTF-Sandbox-Orchestrator.
- **Effort:** LOW — copy skill files, adapt frontmatter
- **License:** MIT (main), GPLv3 (CTF — reference only)

### Risk
- **GPLv3 CTF module:** Must not vendor. Reference patterns only.
- **Tool dependencies:** jadx, Frida, IDA Pro require separate installation
- **Bilingual content:** Chinese-heavy README — may need translation for ATLAS docs

---

## 4. proxifly/free-proxy-list — Proxy Data (6.1k stars)

### Architecture
- **Data:** 2,564 proxies from 96 countries
- **Protocols:** HTTP (598), HTTPS (1,219), SOCKS4 (211), SOCKS5 (536)
- **Update:** Every 5 minutes via automated scraping
- **Formats:** JSON, TXT, CSV
- **NPM module:** `proxifly` package for programmatic access
- **CDN:** jsDelivr CDN for direct download

### Quality
- 59,989 commits (automated proxy updates)
- 710 forks, 6.1k stars
- Automated proxy validation
- No code to evaluate — pure data feed

### ATLAS Fit
- **Gap addressed:** ATLAS web_fetch could use proxy rotation for reliability
- **Integration:** Runtime data feed consumption only. Do NOT vendor.
- **License:** GPL-3.0 — **CANNOT vendor into MIT-licensed ATLAS**
- **Effort:** LOW — fetch CDN URLs at runtime

### Risk
- **GPL-3.0:** Cannot vendor. Data consumption only.
- **Free proxies:** Unreliable, potentially malicious. Must validate before use.
- **Privacy:** Free proxies may log traffic. Never use for sensitive operations.

---

## 5. emilkowalski/skills — Design Skills (NEW, details TBD from fetch)

### Expected Content
Based on the repo name and user's "perfect for design" comment:
- Design system skills for AI agents
- UI/UX component patterns
- Visual design workflows
- Likely SKILL.md format (compatible with ATLAS skill system)

### ATLAS Fit (Preliminary)
- **Gap addressed:** ATLAS has frontend-design skill but could benefit from more design patterns
- **Integration:** Import design skills into ATLAS skill directory
- **Effort:** LOW — copy SKILL.md files
- **License:** TBD from fetch

### Risk
- Unknown until full analysis
- May overlap with existing ATLAS design skills

---

*Analysis complete. 5 repos: Ada-SI (reference), meetily (future module), reverse-skill (security skills), proxifly (data feed, GPL restricted), emilkowalski/skills (design, pending full analysis).*
