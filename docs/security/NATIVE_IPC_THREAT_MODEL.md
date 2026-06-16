# ATLAS Native-IPC Threat Model — DRAFT

**Status:** DRAFT — The Tauri 2 shell is built in Phase 10.5. This threat model is the specification that 10.5 builds against.

**Owns no v1 REQ-IDs; de-risks SEC-04, NAT-03 — owned by Phase 10.5.**

**Authored:** 2026-06-16
**Phase:** 10.0 — Harness Architecture & Threat-Model Design
**Hand-off:** The 10.5 native shell must implement every capability grant and hard gate in this document. Any IPC command not listed here requires a threat-model update before it can ship.

---

## 1. Scope

This document covers the Tauri 2 IPC surface of the ATLAS native operator shell (Phase 10.5). It enumerates:

- The security model (deny-by-default Tauri 2 capabilities)
- The planned IPC command inventory (one row per command)
- The PTY-as-byte-channel hard gate (LANDMINE 5)
- The cockpit ↔ gateway transport posture (loopback HTTP, not IPC)

**Not in scope:** the OAuth callback flow (see `OAUTH_CALLBACK_THREAT_MODEL.md`), the auth store file permissions (see `docs/architecture/AUTH_STORE_DESIGN.md`), or the fallback-cascade error classification (see `docs/architecture/ADAPTER_BOUNDARY.md`).

---

## 2. Platform Baseline

- **Runtime:** Tauri 2 (NOT Tauri 1). Tauri 2's security model is a deliberate inversion of Tauri 1's flat allowlist approach. Do not author against Tauri 1 documentation.
- **No Electron** (D-005, locked). Tauri uses the OS-native webview (WebView2 on Windows, WKWebView on macOS, WebKitGTK on Linux) with a Rust core. The trust boundary is the Tauri IPC bridge.
- **Webview is untrusted by default.** The SvelteKit cockpit webview is treated as an untrusted origin — it can only invoke IPC commands that have been explicitly granted via capability files.

---

## 3. Security Model: Deny-by-Default Capability-Scoped Allowlist

### 3.1 Tauri 2 Capabilities

Every IPC command — whether built-in, plugin-provided, or custom — must be **explicitly permitted** in a capability file under `src-tauri/capabilities/*.json`. Each capability file:

- Is scoped to specific windows/webviews (e.g. `"windows": ["main"]`).
- Grants specific permission identifiers (e.g. `"allow-get-readiness"`, `"allow-pty-open"`).
- Optionally attaches a `scope` object that further constrains permitted values (e.g. URL scheme allowlist for `open_external`).

A command that is not listed in any capability file is **inaccessible to the webview**. This is Tauri 2's deny-by-default posture: absence of a grant = denial.

### 3.2 Per-Command Permissions

Each custom ATLAS IPC command generates permission identifiers of the form `allow-<command>` and `deny-<command>`. The capability files MUST grant only the specific commands the cockpit window needs — no wildcard grants.

### 3.3 Scopes

The Tauri 2 `scope` mechanism further constrains a permitted command. For example, `open_external` is granted with a scope that restricts the URL scheme to an allowlist (see Gate 4 in the IPC inventory). Scopes are enforced in the Tauri 2 runtime before the command handler runs.

### 3.4 No Remote Origin in Production (NAT-01)

The cockpit is loaded from a **local static bundle** (`tauri://localhost`), not from a remote server. A remote origin in the webview would allow a compromised remote page to invoke any IPC command the capability file permits. In production:

- The cockpit webview MUST load from the local bundle.
- Remote content MUST NOT be loaded in the main cockpit window.
- If a remote URL must be opened, use `open_external` (subject to the scheme allowlist), which opens the OS default browser — not the Tauri webview.

---

## 4. Cockpit ↔ Gateway Transport: Loopback HTTP (NOT an IPC Surface)

The cockpit communicates with the ATLAS gateway via **loopback HTTP on `127.0.0.1`** — this is not an IPC surface and does not require a Tauri capability grant.

**Gateway posture (verified from codebase):**
- `atlas-gateway` binds exclusively to `127.0.0.1` (port 8484 by default, configurable via `ATLAS_GATEWAY_PORT`).
- CORS allows `tauri://localhost` (the cockpit's local bundle origin).
- The gateway is a read-only REST + SSE surface over the shared SQLite store; writes dispatch through the `atlas` CLI contract.

**Why this matters for the IPC threat model:** the cockpit ↔ gateway HTTP channel is NOT an IPC surface. Do not add a Tauri capability grant for gateway communication — doing so would conflate the low-privilege HTTP transport with the privileged IPC channel. Keep them separate:

| Channel | Transport | Trust Model |
|---------|-----------|-------------|
| Cockpit → gateway | Loopback HTTP (`127.0.0.1:8484`) | Unauthenticated loopback (v1.1); no IPC capability needed |
| Cockpit → Tauri IPC | Tauri 2 IPC bridge | Deny-by-default capability allowlist |

---

## 5. LANDMINE 5 — PTY-as-Byte-Channel HARD GATE (NAT-03)

**This is the single most important invariant in the entire native-IPC design.**

The PTY transports **keystrokes and raw bytes** to a pre-spawned `atlas tui` child process. It does **not** — and MUST NEVER — transport a command string or argv from the webview.

**The hard gate:**

> If any IPC command ever accepts a command string, shell command, or argv array from the webview (or from any untrusted caller), the entire deny-by-default model collapses into an **arbitrary-exec bridge**.

NAT-03 explicitly forbids this. The threat: a compromised cockpit page, an XSS payload, or a malicious extension that can invoke IPC could execute arbitrary system commands by passing them through the PTY channel. With a byte-channel design, the worst case is a corrupted keystroke stream to an already-running `atlas tui` process — which operates within its own sandboxed permission set, not a raw shell.

**Invariants that MUST hold in the 10.5 implementation:**

1. `pty_open` spawns a **fixed program** with **validated, enumerated arguments**: `atlas tui --profile <profile_id>`. No other program, no other argv construction.
2. `profile_id` is an **identifier** validated against the set of known ATLAS profiles (a lookup against the profile registry, not an arbitrary string, not a file path, not a command). The webview passes an enum-like value; the Tauri command handler resolves it to a fixed argv.
3. `pty_write` accepts **raw bytes** (keystrokes) and writes them to the already-running PTY stdin. The child process is `atlas tui` — it is never `bash`, `cmd.exe`, `powershell`, or any other shell. The bytes are interpreted by `atlas tui`, not by a shell.
4. No IPC command in any future version may accept a `command: String`, `args: Vec<String>`, or equivalent free-form parameter from the webview. Any proposed command that does so requires a full threat-model update and explicit security review.

---

## 6. IPC Command Inventory

The following table enumerates all planned Tauri 2 IPC commands for the ATLAS native shell. Each row is the design contract that Phase 10.5 implements against. No command not listed here may be added without updating this threat model.

| Command | Params | Caller | Privilege | Threat | Mitigation |
|---------|--------|--------|-----------|--------|------------|
| `get_readiness()` | — (none) | cockpit (main window) | Read-only status query | Info disclosure: returns provider/auth status visible to the webview | Capability grants `allow-get-readiness` scoped to main window only. Handler returns a **redacted** status object — no secrets, no raw API keys, no auth tokens. Only presence/absence of auth (`auth_status` enum) and model reachability. Ties to SEC-01 redaction and the credential boundary (secrets only in file store, never surfaced via IPC). |
| `pty_open(profile_id)` | `profile_id: String` — a validated profile identifier (e.g. `"default"`, `"work"`) | cockpit (PTY pane) | Spawns a child process (`atlas tui`) | **Arbitrary exec if the command accepted a command string or path.** A compromised webview could spawn any binary. | **LANDMINE 5 HARD GATE:** Handler validates `profile_id` against the known profile registry. On match, spawns the fixed argv `["atlas", "tui", "--profile", <resolved_profile_name>]` — no user-supplied command, no shell interpolation. Rejects unknown `profile_id` values. Capability grants `allow-pty-open` scoped to main window. |
| `pty_write(bytes)` | `bytes: Vec<u8>` — raw keystroke bytes | cockpit (PTY pane, keyboard input) | Writes to PTY stdin of the already-running `atlas tui` child | **Command injection if the child were a shell.** Keystroke bytes could form a shell command if the child process is `bash` or `cmd.exe`. | **LANDMINE 5:** The child is always `atlas tui`, never a shell. `atlas tui` interprets incoming bytes as TUI input (keypresses, escape sequences), not as shell commands. Capability grants `allow-pty-write` scoped to main window. Rate-limit or validate byte length to prevent DoS via large bursts. |
| `pty_resize(rows, cols)` | `rows: u16, cols: u16` | cockpit (PTY pane, resize event) | Sends SIGWINCH / resize to PTY | **DoS via extreme values** (e.g. rows=65535, cols=65535 could cause abnormal rendering or memory allocation in the child). | Handler **clamps** both values to a sane range (e.g. `rows ∈ [1, 500]`, `cols ∈ [1, 500]`) before forwarding the resize signal. Values outside the clamped range are silently truncated, not rejected (resize is non-security-critical). Capability grants `allow-pty-resize`. |
| `open_external(url)` | `url: String` — URL to open in OS browser | cockpit (link handler) | Invokes the OS default handler for the URL | **Arbitrary-scheme abuse:** a compromised page could pass `file:///etc/passwd`, `javascript:...`, a custom URI scheme registered by a malicious app, or a `data:` URI. | **Scheme allowlist via Tauri 2 scope:** capability grants `open_external` with a scope restricting `allowedUrls` to `https://**` and optionally `mailto:**`. All other schemes are rejected by the Tauri runtime before the handler is invoked. The ATLAS command handler performs a secondary scheme check in Rust as a defence-in-depth measure. |

---

## 7. PTY Plugin Selection (Deferred to Phase 10.5)

Tauri 2 has no first-party PTY plugin. Phase 10.5 must choose one of:

- A community `tauri-plugin-pty` (if one exists and passes legitimacy audit).
- A custom Tauri command backed by the `portable-pty` Rust crate.

**This choice is deferred to Phase 10.5** and carries its own package-legitimacy audit at that phase. The IPC command inventory above is defined independently of the plugin choice — the `pty_open`/`pty_write`/`pty_resize` command contracts hold regardless of the underlying PTY implementation.

Before installing any PTY-related crate or plugin at Phase 10.5, run the package-legitimacy gate (verify the crate on crates.io, review the source, confirm the maintainer).

---

## 8. STRIDE Threat Register (IPC Surface)

| Threat ID | Category | Component | Disposition | Mitigation |
|-----------|----------|-----------|-------------|------------|
| T-IPC-01 | Elevation of Privilege | `pty_open` with arbitrary command string | Mitigate | LANDMINE 5 HARD GATE: fixed `atlas tui` argv; `profile_id` validated against known profiles; no free-form command param (NAT-03) |
| T-IPC-02 | Elevation of Privilege | `pty_write` keystroke injection to a shell child | Mitigate | Child is `atlas tui`, never `bash`/`cmd`; bytes are TUI input, not shell commands (NAT-03) |
| T-IPC-03 | Elevation of Privilege | `open_external` opening a `file://` or custom-scheme URI | Mitigate | Tauri 2 scope scheme allowlist (`https` only); secondary Rust-side scheme check |
| T-IPC-04 | Elevation of Privilege | Compromised remote origin invoking permitted IPC commands | Mitigate | NAT-01: no remote origin in production; cockpit loaded from local bundle (`tauri://localhost`) |
| T-IPC-05 | Information Disclosure | `get_readiness` returning secrets or raw API keys | Mitigate | Handler returns redacted status only (auth_status enum, not raw credentials); SEC-01 credential boundary |
| T-IPC-06 | Denial of Service | `pty_resize` with extreme row/col values | Mitigate | Handler clamps both values to `[1, 500]` before forwarding resize |
| T-IPC-07 | Spoofing | XSS in cockpit webview invoking IPC on behalf of attacker | Mitigate | Tauri 2 capability scoping (commands scoped to main window); no remote content in the main window; CSP headers on the local bundle |
| T-IPC-08 | Denial of Service | `pty_write` flooding with large byte payloads | Mitigate | Rate-limit byte volume; capability scoped to main window only (no cross-window invocation) |

---

## 9. Capability File Shape (Reference for Phase 10.5)

Phase 10.5 must author a capability file at `src-tauri/capabilities/main.json` with approximately this structure:

```json
{
  "$schema": "https://schemas.tauri.app/config/capabilities.json",
  "identifier": "atlas-cockpit-main",
  "description": "ATLAS cockpit main window — deny-by-default IPC allowlist",
  "windows": ["main"],
  "permissions": [
    "allow-get-readiness",
    "allow-pty-open",
    "allow-pty-write",
    "allow-pty-resize",
    {
      "identifier": "shell:allow-open",
      "allow": [
        { "url": "https://**" },
        { "url": "mailto:**" }
      ]
    }
  ]
}
```

Every permission not listed here is **denied by default** by the Tauri 2 runtime. Do not use wildcard permission grants.

---

## 10. Hand-Off Contract

Phase 10.5 must:

1. Implement every IPC command in Section 6 according to its mitigation column.
2. Enforce the LANDMINE 5 hard gate (Section 5) without exception — `pty_open` uses fixed argv and validated `profile_id`.
3. Author `src-tauri/capabilities/main.json` with per-command grants scoped to the main window (no wildcards).
4. Apply the `open_external` scheme allowlist via Tauri 2 scope.
5. Add integration tests covering: `pty_open` rejects unknown `profile_id`; `pty_resize` clamps extreme values; `open_external` rejects non-`https`/`mailto` schemes; `get_readiness` returns no secret values.
6. Run the package-legitimacy audit on any PTY plugin before installing.
7. Update this document's status from DRAFT to APPROVED once all gates pass review.

**SEC-04** tracks the native-IPC security design. **NAT-03** tracks the PTY-as-byte-channel invariant. Both are de-risked by this document and owned for implementation by Phase 10.5.

---

*This document was produced in Phase 10.0 as a threat-model draft. It owns no v1 REQ-IDs. It de-risks SEC-04 and NAT-03, both owned by Phase 10.5.*
