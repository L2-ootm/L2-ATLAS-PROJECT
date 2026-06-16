# ATLAS OAuth Callback Threat Model — DRAFT Gate Spec

**Status:** DRAFT — Gate specification only. No OAuth callback flow exists in ATLAS v1.1.

**Owns no v1 REQ-IDs; de-risks SEC-05 — future OAuth spike.**

**Authored:** 2026-06-16
**Phase:** 10.0 — Harness Architecture & Threat-Model Design
**Hand-off:** Any future OAuth callback implementation must satisfy every numbered gate below before it can ship. This document is the inheritance artifact for that work.

---

## 1. Scope and Deferred Status

ATLAS ships **no OAuth callback flow in v1.1.** The v1.1 scope is locked: Codex read-only detection, file-store-first credential management, no OpenAI/Codex OAuth-protocol reuse. SEC-05 is explicitly deferred.

This document records the hard requirements that any future ATLAS OAuth callback flow must satisfy. A later spike inherits these gates rather than a blank page.

---

## 2. Threat Surface Summary

An OAuth 2.0 loopback callback flow introduces two trust boundaries:

| Boundary | Threat Category |
|----------|-----------------|
| Authorization server → loopback redirect | Code interception by another local process (CSRF, state forgery) |
| Loopback listener → ATLAS process | State parameter replay, code reuse across sessions |
| ATLAS process → log/persistence layer | Token/code leakage in logs or persisted URLs |

---

## 3. Required Gates

Every gate below is a **hard requirement** (not a recommendation). A future OAuth implementation that omits or weakens any gate must be blocked at review.

### Gate 1 — PKCE with S256 (RFC 7636)

- PKCE is **mandatory** for all loopback OAuth flows (RFC 8252 §8.1).
- The code challenge method MUST be `S256` (SHA-256 of the code verifier, base64url-encoded without padding).
- `plain` is only acceptable when the authorization server explicitly does not support `S256` — document the justification if used.

**Basis:** RFC 7636 §4.2 — S256 is the only transform that provides real protection; `plain` is equivalent to no PKCE if the callback is intercepted.

### Gate 2 — High-Entropy One-Time `state` Parameter (RFC 8252 + RFC 6749)

- A cryptographically random `state` value MUST be generated for each authorization request (minimum 128 bits of entropy; use `secrets.token_urlsafe(32)` or equivalent).
- The `state` value issued at request time MUST be validated on callback before processing `code`.
- The `state` is a **one-time token** — it must be invalidated after the first callback regardless of outcome.

**Basis:** RFC 8252 — the `state` parameter is the primary CSRF defence for loopback flows.

### Gate 3 — HARD GATE: Constant-Time State Comparison (hmac.compare_digest)

**This is the single most common implementation mistake in loopback OAuth flows.**

The `state` comparison on callback MUST be performed using `hmac.compare_digest`, not the Python `==` operator or `!=`:

```python
import hmac

if not hmac.compare_digest(received_state, expected_state):
    # Reject the callback immediately — do NOT process code
    raise ValueError("state mismatch: possible CSRF or replay attack")
```

The listener MUST reject any callback whose `state` does not match the issued value **BEFORE processing `code`** or making any token exchange request. A naive `==` plus "first callback wins" is the classic loopback-hijack vector: a race-condition attacker can inject a callback with a forged `state`; if the comparison short-circuits on the first byte, the timing leaks whether the prefix matches.

**Basis:** LANDMINE recorded in 10.0-RESEARCH.md Area 4a. `hmac.compare_digest` is the stdlib constant-time comparison function (Python 3.3+, docs.python.org/3/library/hmac.html#hmac.compare_digest).

### Gate 4 — Ephemeral Loopback Listener: `127.0.0.1`, OS-Assigned Port, One Shot

- The listener MUST bind exclusively to `127.0.0.1` (the IPv4 loopback address). It MUST NOT bind to `0.0.0.0` or any routable interface.
- The port MUST be OS-assigned (bind to port 0); the actual port is read from `server.server_address[1]` after binding. A fixed loopback port is a weaker alternative and requires the same port to be unoccupied.
- The listener MUST accept **exactly one** callback request and then shut down (`server.shutdown()` in a background thread immediately after the first request is received). It must not remain open waiting for additional requests.
- The listener MUST be opened **only during the OAuth flow** and closed as soon as the callback is received or the timeout expires. It must not be a long-lived daemon.

**Basis:** RFC 8252 §7.3 — "open the port only when starting the request and close once the response is returned; listen on loopback only."

**Implementation hint (stdlib, no third-party dependency):**

```python
from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse, parse_qs
import threading

class _CallbackHandler(BaseHTTPRequestHandler):
    code = None
    state = None

    def do_GET(self):
        params = parse_qs(urlparse(self.path).query)
        _CallbackHandler.code = params.get("code", [None])[0]
        _CallbackHandler.state = params.get("state", [None])[0]
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"Auth complete. You may close this tab.")
        # Schedule shutdown AFTER response is sent
        threading.Thread(target=self.server.shutdown, daemon=True).start()

    def log_message(self, *_):
        pass  # Suppress access logs

server = HTTPServer(("127.0.0.1", 0), _CallbackHandler)
chosen_port = server.server_address[1]
# Build redirect URI using chosen_port, then open browser, then:
server.serve_forever()  # Blocks until shutdown() is called
code, state = _CallbackHandler.code, _CallbackHandler.state
```

### Gate 5 — Exact Redirect-URI Match

- The redirect URI submitted to the authorization server and the redirect URI in the token exchange request MUST be identical (exact string match).
- The redirect URI format is `http://127.0.0.1:<chosen-port>/callback`.
- **Precondition:** the authorization server must support loopback port flexibility (RFC 8252 §7.3 — the AS must tolerate any port on `127.0.0.1`, not a fixed registered port). Not all providers honor this. List "provider supports loopback port flexibility" as a precondition in the provider integration notes before implementing.

**Basis:** RFC 8252 §7.3 — "exact URI matching is required"; the only carve-out is port variability for loopback (`127.0.0.1`).

### Gate 6 — No Token or Authorization Code in Any Log or Persisted URL (SEC-01)

- The authorization `code`, access token, refresh token, and PKCE code verifier MUST NEVER appear in:
  - any log file (application logs, access logs, debug logs)
  - any SQLite row or audit JSONL record
  - any URL that is persisted or shared (browser history, server-side logs)
  - any CLI output displayed to the user (redact to a `redacted_hint` if display is needed)
- The redaction filter (`atlas_core.schemas.core.SECRET_PATTERNS`, SEC-01) MUST be applied to all transcript content before persistence (AGNT-06).
- The listener's access log MUST be suppressed (override `log_message` in the handler).

**Basis:** RFC 8252 §8.x — "authorization codes must not be included in response URIs or transmitted to third parties." ATLAS SEC-01 extends this to all log/audit surfaces.

### Gate 7 — Short Overall Timeout

- The entire OAuth flow (from browser-open to callback receipt) MUST have a bounded timeout (recommended: 120 seconds).
- If the timeout expires before a callback is received, the listener MUST be shut down, any partial state MUST be discarded, and the user MUST be informed.
- The `state` token MUST be invalidated at timeout regardless.

### Gate 8 — Loopback HTTP (No TLS) is Acceptable

Loopback `http://` (not HTTPS) is acceptable for the redirect URI because:
- The OAuth callback request never leaves the local device.
- RFC 8252 §7.3 explicitly permits `http://127.0.0.1`.

Do not implement self-signed TLS for the loopback listener — it adds complexity with no security benefit for local-only traffic.

### Gate 9 — Manual-Paste Fallback for SSH/Headless Environments

- A `--no-browser` or equivalent mode MUST be provided for SSH, CI, and headless environments.
- In this mode, ATLAS prints the authorization URL for the user to open manually, and prompts for the callback URL or authorization code via stdin.
- The same `state` validation and `hmac.compare_digest` requirement applies to the pasted callback URL.

**Basis:** RFC 8252 device-flow alternative; Hermes reference implementation (`hermes_cli/auth.py`) implements this pattern.

---

## 4. STRIDE Threat Register (OAuth Surface)

| Threat | STRIDE | Mitigation Gate |
|--------|--------|-----------------|
| Loopback code interception by another local process | Spoofing | Gate 1 (PKCE-S256), Gate 3 (constant-time state), Gate 4 (one-shot listener) |
| CSRF — forged callback with attacker's authorization code | Tampering | Gate 2 (state parameter), Gate 3 (constant-time state before code) |
| State replay across sessions | Tampering | Gate 2 (one-time token), Gate 7 (timeout + invalidation) |
| Token leakage to logs or persistence | Information Disclosure | Gate 6 (no-secret-in-logs, SEC-01 redaction) |
| Port squatting on a fixed loopback port | Denial of Service | Gate 4 (OS-assigned port 0) |
| Redirect URI mismatch allows attacker-controlled redirect | Elevation of Privilege | Gate 5 (exact redirect match) |

---

## 5. Non-Requirements (Explicitly Out of Scope for v1.1)

The following are **not** required by this gate spec and are NOT part of the deferred OAuth scope:

- OAuth 2.0 Device Authorization Grant (RFC 8628) — a separate flow, not covered here.
- OpenID Connect (OIDC) `id_token` validation — out of scope for ATLAS v1.1.
- PKCE-S256 for non-loopback (mobile, web) redirect flows — this spec covers the loopback/native-app case only (RFC 8252).
- Token refresh rotation — deferred; the gate spec for refresh tokens is a separate work item.
- OpenAI/Codex OAuth-protocol reuse — explicitly excluded from ATLAS v1.1 scope (file-store-first, SEC-05 deferred).

---

## 6. Hand-Off Contract

A future OAuth spike that references this document must:

1. Satisfy all 9 gates above before any code is merged.
2. Verify provider-level loopback port flexibility (Gate 5 precondition) and document the result.
3. Add `test_oauth_callback.py` covering: PKCE generation, `state` generation entropy, constant-time comparison rejection of mismatched state, one-shot listener (second callback is rejected), timeout expiry behavior, no-token-in-log assertion.
4. Update `docs/security/OAUTH_CALLBACK_THREAT_MODEL.md` status from DRAFT to APPROVED once all gates pass review.

**SEC-05** is the REQ-ID tracking this deferral. This document is the gate spec that resolves SEC-05 when a future OAuth implementation satisfies all gates.

---

*This document was produced in Phase 10.0 as a threat-model draft. It owns no v1 REQ-IDs. It de-risks SEC-05, which is owned by the future phase that implements the OAuth callback flow.*
