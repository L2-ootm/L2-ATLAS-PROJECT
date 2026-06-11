# ATLAS Channels — L2 BOT Harness Setup

Status: active runbook (2026-06-11)
Owner surface: vendored foundation gateway (`foundation/atlas-hermes/gateway/`)

The L2 BOT harness is the foundation's multi-platform gateway daemon running
under ATLAS branding. One daemon, 20+ channel adapters, each toggled in config.
ATLAS adds inspection (`atlas channels status`) and the audit plugin; the
adapter code is upstream foundation code (no divergence required).

## Command surface

| Action | Command |
|---|---|
| Onboarding wizard | `atlas-agent setup` |
| Inspect channels (read-only, secret-safe) | `atlas channels status` |
| Enable a channel | `atlas-agent config set gateway.platforms.<name>.enabled true` |
| Set a credential | edit `~/.hermes/config.yaml` or the foundation `.env` (`atlas-agent config env-path`) |
| Start the BOT harness daemon | `atlas-agent gateway` |
| Config file location | `atlas-agent config path` |

`atlas channels status` never prints credential values — only presence.

## Supported channels (foundation adapters, `gateway/platforms/`)

Telegram, Discord, WhatsApp (Node bridge), Slack, Signal (HTTP bridge),
Matrix, Email (IMAP/SMTP), SMS (Twilio), DingTalk, Feishu/Lark, WeCom,
WeChat Official, BlueBubbles (iMessage), QQ Bot, Home Assistant, generic
webhook, MS Graph webhook, HTTP API server, local (dev).

## Config structure (`<HERMES_HOME>/config.yaml`)

```yaml
gateway:
  platforms:
    telegram:
      enabled: true
      token: "${TELEGRAM_BOT_TOKEN}"   # env reference preferred over inline
      home_channel:
        chat_id: "<chat id>"
    discord:
      enabled: false
```

Common credential env vars: `TELEGRAM_BOT_TOKEN`, `DISCORD_BOT_TOKEN`,
`SLACK_BOT_TOKEN` + `SLACK_SIGNING_SECRET`, `SIGNAL_HTTP_URL` +
`SIGNAL_ACCOUNT`, `TWILIO_ACCOUNT_SID` + `TWILIO_AUTH_TOKEN`,
`EMAIL_ADDRESS` + `EMAIL_IMAP_HOST` + `EMAIL_SMTP_HOST`.

## Message flow (audit-wired)

```
channel adapter → GatewayRunner._handle_message → session cache → AIAgent.turn()
                                                        │
                                  atlas_audit plugin hooks (D-002, DIV-F-002)
                                                        ▼
                                          ~/.atlas/atlas.db audit_events
```

The bundled `atlas_audit` plugin loads on every foundation boot, so gateway
sessions emit AuditEvents like any other run. The Rust `atlas-gateway`
(`native/atlas-core-rs`) serves cockpit reads over the same SQLite (D-022).

## Hard rules

- Credentials live in `<HERMES_HOME>` config/.env only — never in this repo.
- Bot harness binds outbound to platform APIs; the local HTTP API server and
  webhook listeners stay loopback-only unless a tunnel is explicitly set up.
- New channel adapters belong upstream or in `plugins/` (PlatformRegistry
  supports plugin registration) — do not edit `gateway/platforms/` without a
  DIVERGENCE_LOG entry.
