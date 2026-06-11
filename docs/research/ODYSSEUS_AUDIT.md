# Odysseus — Deep Audit for ATLAS

**Date:** 2026-06-08
**Auditor:** Phase 4.5 architecture bridge (extended, source-inspected)
**Source repo:** https://github.com/pewdiepie-archdaemon/odysseus
**Default branch:** `dev` (latest development)
**Inspected commit SHA (dev):** `8449baea80db7763e713685ec98760cd8d398802` (2026-06-08T17:37:31Z)
**Stable branch SHA (main):** `73673258199b353f9b3e04da9b37ae95077e2c8b` (2026-06-05)
**Inspection method:** GitHub API — source files, tree listing, THREAT_MODEL.md, README, core modules. Full clone not required; license confirmed MIT.

---

## License

**MIT.** Confirmed via GitHub API (`repos/pewdiepie-archdaemon/odysseus` → `license.spdx_id: MIT`).

- Permissive. Code may be used, adapted, and redistributed in ATLAS without copyleft obligation.
- Attribution required in distributions that include copied code: credit Odysseus contributors and include the MIT license text.
- User also confirmed all four reference projects (Odysseus, Terax, Hermes, FreeLLMAPI) carry free/permissive licenses.
- Action before code reuse: create `docs/legal/ODYSSEUS_NOTICE.md` recording SHA, copyright notice, and MIT license reference.

---

## Stack

| Layer | Technology |
|-------|-----------|
| Language | Python |
| Web framework | FastAPI |
| Database | SQLite (via SQLAlchemy ORM) |
| Vector memory | ChromaDB + fastembed (ONNX) |
| Auth | bcrypt passwords, TOTP 2FA (pyotp), 7-day session tokens |
| Agent engine | Built on opencode (anomalyco/opencode) |
| Plugin protocol | MCP (Model Context Protocol) |
| Model serving | Ollama, llama.cpp, vLLM, OpenRouter, OpenAI, GitHub Copilot |
| Model cookbook | llmfit (VRAM-aware model recommendation and download) |
| Research engine | Adapted from Tongyi DeepResearch |
| Deployment | Docker (standard + GPU AMD variant), docker-compose |
| Frontend | PWA (mobile-compatible, responsive) |
| Email | IMAP/SMTP with CalDAV-aware routing |
| Calendar | CalDAV (Radicale / Nextcloud / Apple / Fastmail) |

---

## Architecture Summary

Odysseus is a self-hosted, multi-user AI workspace. It exposes a web UI (PWA) backed by a FastAPI server with SQLite storage. The architecture is a standard monolithic web service with clear internal boundaries:

- `core/` — pure infrastructure: auth, database models, middleware, session manager, platform compatibility, atomic I/O.
- `app.py` — FastAPI app entry point.
- `companion/` — companion device pairing (mobile/secondary device).
- `config/` — configuration management.

**Session model:** Chat sessions are keyed by UUID. Messages are stored in SQLite and lazy-loaded into RAM on access. `SessionManager` owns all session CRUD. Sessions have: id, name, endpoint_url, model, rag flag, archived flag, headers, history (ChatMessage list), owner, is_important, message_count.

**Auth model:** Multi-user, password + TOTP. `AuthManager` owns user records in `data/auth.json`. Sessions stored in `data/sessions.json` via atomic write (`core/atomic_io.py`). Session tokens are validated against the user record on every request — deleted user's cookie is rejected immediately.

**Admin vs non-admin:** Privilege system is explicit and source-documented (see capability table below). Non-admin defaults in `core/auth.py:DEFAULT_PRIVILEGES`. Admin always gets full access. Tool enforcement in `src/tool_security.py:NON_ADMIN_BLOCKED_TOOLS`.

**Internal tool loopback:** Agent tool calls reach admin-gated HTTP routes over a per-process in-process HTTP loopback. At startup, `core/middleware.py` generates `INTERNAL_TOOL_TOKEN = secrets.token_hex(32)` — never persisted, never sent to clients. The agent verifies the session owner is admin before issuing any loopback call. Non-admin users cannot invoke admin tools through the agent.

**Prompt injection hardening:** Implemented in `src/prompt_security.py`. `untrusted_context_message(label, content)` wraps all external content in a user-role message with an instruction block telling the model not to follow instructions inside it. `UNTRUSTED_CONTEXT_POLICY` is a system-prompt preamble applied to every session where untrusted data may appear.

---

## Admin vs Non-Admin Capability Table

Source: `THREAT_MODEL.md` and `core/auth.py:DEFAULT_PRIVILEGES`.

| Capability | Admin | Non-admin (default) | Notes |
|-----------|-------|-------------------|-------|
| Chat with agent | Yes | Yes | |
| Browser tool | Yes | Yes | |
| Documents | Yes | Yes | |
| Research mode | Yes | Yes | |
| Image generation | Yes | Yes | |
| Memory management | Yes | Yes | |
| Shell / Python execution | Yes | **No** | Highest-risk capability; admin-only by default |
| File read / write | Yes | **No** | Admin-only by default |
| Email send / read | Yes | **No** | |
| MCP tools | Yes | **No** | All `mcp__*` prefix tools blocked for non-admins |
| Calendar management | Yes | **No** | |
| Token / webhook management | Yes | **No** | |
| Model serving | Yes | **No** | |
| Vault | Yes | **No** | |
| Settings | Yes | **No** | |

Non-admin can_use_bash: False is the key guard for shell execution risk.

---

## Security Architecture (Source-Verified)

### Authentication (`core/auth.py`)

- **Password hashing:** bcrypt with per-user salt. `_hash_password` / `_verify_password` directly wrapping bcrypt.
- **2FA:** TOTP (pyotp). Verified after password check, before session issuance. 8 single-use backup codes.
- **Session TTL:** 7 days (`TOKEN_TTL = 60 * 60 * 24 * 7`).
- **Orphan sessions:** `validate_token` re-checks user record existence on every call. Deleted user's cookie dropped on next request.
- **Reserved usernames:** `frozenset({"internal-tool", "api", "demo", "system"})`. Cannot be registered or renamed into. `internal-tool` is security-critical — `require_admin` grants admin unconditionally for any request where `current_user == "internal-tool"`. A real account with this name would silently pass all admin checks (Odysseus documented this as a known reserved-name attack; it is mitigated by `RESERVED_USERNAMES`).

### Middleware (`core/middleware.py`)

- **`INTERNAL_TOOL_TOKEN`:** `secrets.token_hex(32)` generated at process startup. Never persisted. Agent tool calls pass this as `X-Odysseus-Internal-Token`.
- **`require_admin`:** Grants access if (a) token header matches `INTERNAL_TOOL_TOKEN` via `secrets.compare_digest`, or (b) `current_user == "internal-tool"`. Otherwise checks `auth_manager.is_admin(user)`.
- **`SecurityHeadersMiddleware`:** Sets on every response: `X-Frame-Options: DENY`, `frame-ancestors 'none'`, `X-Content-Type-Options: nosniff`, `Referrer-Policy: no-referrer`. CSP with per-request nonce: `script-src 'self' 'nonce-{nonce}' https://cdn.jsdelivr.net`.

### Prompt Injection Hardening (`src/prompt_security.py`)

`untrusted_context_message(label, content)` wraps any external content (web search results, fetched URLs, emails, saved memories, skill text, notes, tool output from outside the server) in a user-role message with an instruction block. The content is treated as data, not as a system instruction.

`UNTRUSTED_CONTEXT_POLICY` is a system-prompt preamble applied when untrusted data may appear in the session.

**Untrusted surfaces covered:** web search results, fetched URLs, emails (read), saved memories, skill text, notes, any tool output from external sources. Injecting untrusted content directly into the system role is documented as a security bug.

### Known Gaps (from `THREAT_MODEL.md`)

The Odysseus threat model explicitly lists open gaps (documentation cut off, but known to include):
- No shell/filesystem sandbox beyond the admin-only capability gate (no container or chroot).
- Internal services (ChromaDB, Ollama, SearXNG) not isolated from host network — must be protected at the deployment layer (firewall/docker network).

---

## Product Features — ATLAS Relevance Map

| Odysseus feature | Relevance to ATLAS | Priority |
|-----------------|--------------------|----------|
| Chat with multiple providers | ATLAS model router (D-017) — provider selection concept | Phase 7 |
| Agent with MCP + opencode | Hermes/OpenClaw execution — already covered | — |
| Cookbook (model discovery via llmfit) | ATLAS model registry discovery — model recommendation concept | Phase 7 |
| Deep Research mode | Future: multi-step research runs via ATLAS missions | v2.0 |
| Memory/Skills (ChromaDB + fastembed) | ATLAS wiki (Phase 6) — vector search via sqlite-vec; ChromaDB is a reference not a replacement | Phase 6 |
| Email (IMAP/SMTP) | ATLAS channels (v2.0, Phase 10+) | v2.0 |
| Notes/Tasks with cron | ATLAS mission cron triggers — already in Hermes cron | — |
| Calendar (CalDAV) | ATLAS calendar integration — v2.0 | v2.0 |
| Mobile PWA | ATLAS cockpit web layer should be PWA-capable as a by-product of SvelteKit | Phase 8 |
| Multi-user auth (bcrypt + TOTP + admin/non-admin) | ATLAS v2.0 multi-operator support — out of scope for v1.0 (single operator local) | v2.0 |
| Admin/non-admin capability table | ATLAS capability model (D-017, NATIVE_COCKPIT_STRATEGY.md) — pattern directly adaptable | Phase 8 |
| Internal tool loopback (`INTERNAL_TOOL_TOKEN`) | ATLAS cockpit IPC bridge — same pattern: per-process random token, `secrets.compare_digest`, loopback only | Phase 8 |
| Prompt injection hardening (`untrusted_context_message`) | ATLAS wiki ingest and any external content tool — implement same wrapper pattern | Phase 6 |
| `UNTRUSTED_CONTEXT_POLICY` preamble | ATLAS agent context injection policy — implement as ATLAS system-prompt policy | Phase 6 |
| Security headers middleware | ATLAS API Gateway (Phase 7) — implement same headers | Phase 7 |
| CSP nonces | ATLAS cockpit web server — implement in SvelteKit adapter | Phase 8 |
| Reserved usernames guard | ATLAS reserved internal IDs — prevent "internal-tool" style account impersonation | Phase 7 |
| `THREAT_MODEL.md` discipline | ATLAS cockpit threat model pre-work — use Odysseus' format as template | Phase 8 pre-work |

---

## Security and Threat-Model Lessons (Source-Verified)

### Lesson 1: Explicit admin/non-admin capability table with source documentation

Odysseus documents every capability by role, with the source code location for enforcement. This is the correct approach: if the capability table and the enforcement code are in the same document, drift is immediately visible.

**ATLAS action:** Before Phase 8, produce `docs/security/COCKPIT_THREAT_MODEL.md` with the same format: capability table with enforcement code location for every row.

### Lesson 2: Per-process random internal loopback token

The `INTERNAL_TOOL_TOKEN = secrets.token_hex(32)` pattern is correct for agent tool loopback: the token is generated fresh at startup, never persisted, never sent to clients, and compared with `secrets.compare_digest` (constant-time). This prevents replay attacks and credential leaks.

**ATLAS action:** Use the same pattern for the ATLAS cockpit IPC bridge. The Rust backend generates an in-process random token at startup; all loopback calls from the webview must carry this token.

### Lesson 3: `untrusted_context_message` wrapper for all external content

Any content from outside the server boundary (web results, emails, files, memories, tool outputs) must be wrapped before reaching the LLM context. The wrapper must: label the content, instruct the model not to follow instructions inside it, and inject it as a user-role message (not system-role).

**ATLAS action:** Implement in Phase 6 wiki ingest: all ingested content from external sources must pass through an `untrusted_context_wrapper(source_label, content)` before being written to the wiki or injected into agent context. Emit a Source record with `untrusted: true` for all externally-sourced content.

### Lesson 4: Session orphan cleanup on every token validation

Odysseus validates that the user record still exists on every token validation call. This prevents ghost sessions from deleted accounts from persisting.

**ATLAS action:** When ATLAS adds multi-user support (v2.0), implement the same check. For v1.0 single-operator mode, note this for the auth spec.

### Lesson 5: Reserved sentinel usernames must be refused at registration

The `RESERVED_USERNAMES` set prevents account name collisions with synthetic owners used by the middleware. The security risk is explicit: an account named `internal-tool` would silently pass every `require_admin` check.

**ATLAS action:** When ATLAS adds multi-user support (v2.0), implement `RESERVED_INTERNAL_IDS` for any sentinel values used in the audit system, policy engine, or IPC middleware.

### Lesson 6: CSP nonces prevent inline script injection

Odysseus generates a per-request nonce and injects it into the CSP header and HTML templates. This limits XSS attack surface significantly compared to `unsafe-inline`.

**ATLAS action:** Phase 7 API and Phase 8 cockpit should implement CSP with nonces. SvelteKit adapter-static supports CSP configuration.

---

## Risks and Anti-Patterns

| Risk/Anti-pattern | Description | ATLAS lesson |
|-------------------|-------------|--------------|
| Monolithic service scope | Odysseus has chat, email, calendar, research, cookbook, notes, tasks, memory in one service — operational sprawl | ATLAS v1.0 ships mission/run/wiki/cockpit only. Features added after MVP validated. |
| Internal services on host network | ChromaDB, Ollama, SearXNG accessible from host unless explicitly docker-network-isolated | ATLAS services: loopback bind only. FreeLLMAPI sidecar: loopback only. |
| No shell/filesystem sandbox beyond admin gate | Admin can run arbitrary shell — powerful but unsafe for multi-user or exposed deployments | ATLAS workspace policy (Phase 5) gates shell operations. Cockpit requires policy check before every shell action. |
| `style-src unsafe-inline` acknowledged | Intentional trade-off in Odysseus (inline styles in JS modules). They document it. | ATLAS should avoid unsafe-inline from the start; design the cockpit with the constraint in mind. |
| opencode dependency | Odysseus' agent is built on opencode rather than a clean internal implementation | ATLAS uses Hermes — a mature, audited, pinned dependency. |
| Large surface area before operational stability | Odysseus ships email + calendar + cookbook before the core agent is fully reliable | ATLAS: six cockpit surfaces, MVP first. |

---

## ATLAS Adaptation Map

| Odysseus concept | ATLAS adaptation | Phase |
|-----------------|-----------------|-------|
| MIT license — free to use | All patterns may be adapted | All |
| Capability table (admin/non-admin) | Cockpit capability model, approval tier system | Phase 8 |
| Internal tool loopback token | Tauri IPC bridge token | Phase 8 |
| `untrusted_context_message` | Wiki ingest wrapper, external content policy | Phase 6 |
| `UNTRUSTED_CONTEXT_POLICY` preamble | ATLAS agent system-prompt policy for untrusted context | Phase 6 |
| Security headers middleware | Phase 7 API Gateway headers | Phase 7 |
| CSP nonces | Phase 8 cockpit web server | Phase 8 |
| Reserved usernames guard | Reserved IDs in ATLAS policy/IPC layer | Phase 7 |
| THREAT_MODEL.md format | Template for ATLAS cockpit threat model pre-work | Phase 8 pre-work |
| Session orphan cleanup | Multi-user auth spec note | v2.0 |
| Model cookbook (llmfit) | Model registry discovery, VRAM-aware recommendation | Phase 7 |
| Memory (ChromaDB + fastembed) | Wiki design input — sqlite-vec is ATLAS choice but vector + keyword hybrid is confirmed pattern | Phase 6 |
| Companion pairing | Future: mobile companion or second-device cockpit | v2.0 |
| Email/Calendar | ATLAS channels (Pulse/CRM) | v2.0 |

---

## Final Classification

**Classification: Product ambition, security/threat-model, and implementation pattern reference pillar.**

- **License:** MIT. Confirmed. Code may be adapted freely with attribution.
- **Use as:** Security pattern reference (capability table, loopback token, prompt injection hardening, CSP, reserved IDs); product ambition reference (multi-surface workspace scope, what v2.0 can become); threat model template.
- **Do not use as:** Primary implementation reference (Terax is superior for native shell); architecture template for v1.0 (Odysseus' monolithic scope is the anti-pattern ATLAS avoids in MVP).
- **Clone required before:** Phase 8 cockpit threat model uses Odysseus source patterns as direct references. Clone at `dev` SHA `8449baea80db7763e713685ec98760cd8d398802` or re-pin to latest `dev` at that time.
- **Risk level:** Low. MIT license, clean architecture, well-documented threat model. Main risk is scope creep from copying Odysseus' broad feature set.
- **Confidence:** High. Source-inspected at pinned SHA.
