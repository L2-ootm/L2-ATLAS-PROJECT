# 10.0.3 — Channel Cockpit UI (System page expansion, messaging gateway control)

> Status: **planned** (in-flight; sequence item #3). **Depends on #2** (config-service).
> Owner concern: `native/atlas-core-rs` (new routes) + `services/agent-runtime` (CLI + gateway control)
> + `services/web-ui-react` (System Channels tab). No foundation edits (D-001) — the foundation owns the
> adapters; ATLAS only reads/writes channel config and starts/stops the messaging gateway.

## Intent

The foundation ships 22+ production messaging adapters (Discord 6.2k LOC + 32 tests, Telegram, Slack,
WhatsApp, Signal, Matrix, Email, …) with **zero cockpit exposure**. ATLAS can inspect channels read-only
(`atlas channels status`) but cannot enable/disable, configure, or start the messaging gateway from the
UI. This phase exposes channel management in the cockpit, built on the #2 config-service.

Full analysis: `.planning/phases/10.0.3-command-center/FOUNDATION-AND-CHANNELS-ANALYSIS.md` Parts 2–6.

## Scope

**In scope (the management floor — corresponds to WP-A/B/C/H + the Providers tab):**
- Gateway routes (Rust, read config.yaml + dispatch CLI for writes):
  - `GET /v1/channels` — all channels: enabled + credential-present + summary.
  - `GET /v1/channels/{name}` · `PUT /v1/channels/{name}` · `POST /v1/channels/{name}/toggle`.
  - `GET /v1/gateway/messaging/status` · `POST /v1/gateway/messaging/{start,stop}`.
- CLI: `atlas channels enable/disable <name>` (writes via config-service); keep `status`.
- Messaging gateway lifecycle helper (`gateway_control.py` extension) wrapping
  `atlas-agent gateway start/stop` with a PID file (`~/.atlas/gateway-messaging.pid`).
- React: System page **Channels** tab — list, enable/disable toggles, credential status, basic
  per-channel settings; **Providers** tab — current provider/model + masked key + model registry list.

**Out of scope (later — P2 Discord suite):**
- Discord guild/channel/role browser, per-channel skill bindings editor, bot activity dashboard.
- Voice session monitoring, cost analytics. (Tracked in the analysis doc WP-E/F/G.)

## Approach

1. Rust `GET /v1/channels` reading the config-service YAML (channels block) + credential-presence check;
   gateway tests (`tests/api.rs`).
2. `PUT`/`toggle` dispatch `atlas channels` CLI (write path stays in Python per D-022).
3. `atlas channels enable/disable` on the config-service; tests.
4. Messaging gateway start/stop/status with PID file; status returns running/stopped + pid.
5. SystemChannels.tsx + SystemProviders.tsx tabs; api.ts client functions; redacted display.

## Acceptance

- Cockpit Channels tab lists every configured channel with enabled + credential status; toggling
  persists to `~/.atlas/config.yaml` and survives reload.
- Messaging gateway can be started/stopped/queried from the cockpit; status reflects reality.
- Providers tab shows current provider/model with the key masked.
- `cargo test -p atlas-gateway` green; `agent-runtime` pytest green; web build green; Playwright smoke
  of the Channels tab toggle.

## Notes
- Two gateways stay distinct: Rust REST gateway (8484) ≠ Python messaging gateway. This phase lets the
  former control the latter's lifecycle but they remain separate processes.
- Writes go through the CLI/config-service (D-022 contract), never direct YAML writes from Rust.

## Delivered (2026-06-20) — management floor

- CLI: `atlas channels enable/disable/json` (foundation `~/.hermes/config.yaml` round-trip, preserves
  other keys; credential presence only, never values). `status` retained.
- Gateway: `GET /v1/channels` (dispatch `atlas channels json`), `POST /v1/channels/{name}/toggle`
  (dispatch enable/disable; user `name` passed after `--`).
- React: System page **CHANNELS** panel — per-channel enable/disable toggles + credential-set badge +
  empty state. (Stacked panel, consistent with the existing System layout; full tab-nav not needed.)
- Tests: channels CLI (json/enable/disable round-trip/create-missing) + 2 gateway tests; web build green.

**Deferred (remaining for this phase):** messaging-gateway *process* lifecycle (start/stop/status from
the cockpit, `~/.atlas/gateway-messaging.pid`), the Providers tab (provider data already shown in the
System RUNTIME CONFIG panel), and the P2 Discord guild/channel browser. The config-management floor —
the highest-value 80% — is live.
