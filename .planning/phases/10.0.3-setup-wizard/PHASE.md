# 10.0.3 — Setup Wizard & Config Service (`atlas setup`, `~/.atlas/config.yaml`)

> Status: **planned** (in-flight; sequence item #2). Substrate for #3 channel-cockpit.
> Owner concern: `services/agent-runtime` (config service + CLI) + `native/atlas-core-rs` (read-only
> config endpoint) + `services/web-ui-react` (System Overview tab). No foundation edits (D-001).

## Intent

ATLAS has no first-run experience and no owned config space. Hermes has `hermes setup` (3.4k LOC) writing
`~/.hermes/config.yaml`; ATLAS must own `~/.atlas/config.yaml` and an `atlas setup` wizard so a new user
can configure provider, runtime, gateway, channels, and cockpit without hand-editing files. This phase
also introduces the **config-service** that later phases (channels) read and write.

Config schema and wizard flow are already drafted in
`.planning/phases/10.0.3-command-center/FOUNDATION-AND-CHANNELS-ANALYSIS.md` Parts 4 — adopt it.

## Scope

**In scope:**
- `config_service.py` — load/save `~/.atlas/config.yaml` (atomic write), with a Pydantic config schema
  (`AtlasConfig`: provider, runtime, gateway, channels, cockpit, modules). Secret values stored as
  `env:VAR_NAME` references, never inline plaintext.
- `atlas setup` — interactive Typer wizard (provider+model+key-ref, runtime+iteration budget, db path +
  `atlas db init`, gateway ports, optional channel tokens, cockpit port). Idempotent: re-running edits.
- `atlas config get/set/show` — non-interactive config access.
- Gateway: `GET /v1/config` — returns the config **masked** (secret refs shown, no values).
- React: System page **Overview** tab — gateway/db/runtime/messaging status + system info, reading
  `/v1/config` + `/health`. (Other System tabs land in #3.)

**Out of scope (deferred):**
- `auth.json` encryption / cross-process lock — that is the paused 10.1 auth store; here secrets are
  `env:` references only.
- Channel deep-config editing and Discord browser — phase #3.
- Config import/export — later polish.

## Approach (TDD)

1. Pydantic `AtlasConfig` schema in `atlas-core` (mirror the drafted YAML); tests for round-trip +
   secret-ref validation (reject inline `sk-`/`Bearer ` values).
2. `config_service` load/save with atomic write + default-on-missing; tests.
3. `atlas config` CLI (thin handlers → service); `atlas setup` wizard built on it.
4. Gateway `GET /v1/config` masked read (reads the YAML; no CLI dispatch needed for read).
5. System Overview tab consuming `/v1/config` + `/health`.

## Acceptance

- `atlas setup` produces a valid `~/.atlas/config.yaml`; re-running edits without clobbering.
- `config_service` round-trips; inline secrets rejected (must be `env:` refs).
- `GET /v1/config` returns masked config (no secret values); System Overview renders live status.
- `agent-runtime` + `atlas-core` pytest green; `cargo test -p atlas-gateway` green; web build green.

## Notes
- Path resolution behind one function (`~/.atlas/` base) — consistent with the 10.0 auth-store decision
  ("path resolution behind one function for future profiles").
- This deliberately predates the foundation de-brand (#6); `~/.atlas/` is ATLAS-owned and independent of
  the foundation's `~/.hermes/`.
