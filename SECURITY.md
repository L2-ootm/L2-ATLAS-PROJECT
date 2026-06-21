# Security Policy

## Reporting a Vulnerability

If you discover a security vulnerability within ATLAS, please send an email to
the project maintainers. All security vulnerabilities will be promptly addressed.

**Please do not report security vulnerabilities through public GitHub issues.**

## Scope

ATLAS is an AI operator cockpit and agent harness. Security-relevant areas include:

- **Credential handling:** API keys, bot tokens, and secrets must never be logged,
  persisted in audit trails, or exposed through the cockpit. ATLAS stores credentials
  as `env:VAR` references only — inline secrets are rejected at config validation.
- **Agent execution:** The native agent runtime executes with the operator's
  permissions. Workspace boundary enforcement prevents path traversal. Destructive
  actions require explicit approval.
- **Discord integration:** Write operations are approval-gated and audited. The
  sidecar bot token is never logged (SHA-256 fingerprint used for coexistence checks).
- **Gateway:** The Rust gateway binds to `127.0.0.1:8484` (loopback only). No
  external network exposure by default.

## Known Limitations

- ATLAS is a single-operator system. There is no multi-user authentication or
  authorization layer.
- The gateway HTTP API has no authentication. It relies on loopback binding for
  access control.
- Agent runs inherit the operator's filesystem permissions. The workspace boundary
  check is advisory, not a security sandbox.

## Dependency Security

ATLAS vendored the Hermes Agent foundation (MIT, Nous Research) at a pinned SHA.
Divergences are tracked in `foundation/DIVERGENCE_LOG.md`. The foundation's own
security policy is at `foundation/atlas-hermes/SECURITY.md`.

## Updates

Security fixes will be released as patch versions. The SECURITY.md file in the
repository root is always the authoritative source.
