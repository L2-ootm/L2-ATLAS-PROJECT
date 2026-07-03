# Attribution

## ATLAS

ATLAS is built by L2 Systems. Licensed under the MIT License (see `LICENSE`).

## Hermes Agent (Foundation)

ATLAS is built as an evolution of the Hermes Agent foundation:

- **Upstream:** https://github.com/NousResearch/hermes-agent
- **License:** MIT (preserved at `foundation/atlas-hermes/LICENSE`)
- **Copyright:** Nous Research and Hermes Agent contributors
- **Vendored at SHA:** `e8b9369a9d2df36139a5055cae3ed3c15691e03e` (v0.14.0)
- **Vendored on:** 2026-06-10

The vendored tree diverges from upstream only as recorded in
`foundation/DIVERGENCE_LOG.md`. The MIT license permits modification and
rebranding; upstream copyright notices and the LICENSE file are preserved.

## L2-BOT (Discord Sidecar)

The vendored Discord bot at `services/discord-bot/` is derived from L2-BOT:

- **License:** MIT
- **Vendored into ATLAS** as an ATLAS-controlled sidecar for Discord read/write
  operations. Secrets and state are gitignored.

## MiMo-Code Terminal UI Donor

The ATLAS terminal workbench derives presentation behavior and implementation
details from XiaomiMiMo/MiMo-Code while retaining the ATLAS Go client,
gateway contract, product identity, and agent runtime:

- **Upstream:** https://github.com/XiaomiMiMo/MiMo-Code
- **Release:** v0.1.2
- **Audited commit:** `86d95a79bf0879bcb442ffe6b12914f6d8e68a4e`
- **Audit date:** 2026-06-24
- **License:** MIT
- **Copyright:** © 2026 MiMo Code, Xiaomi Corporation; © 2025 opencode
- **Notice:** `docs/third-party/ATLAS_TUI_UPSTREAM_NOTICE.md`
- **Inventory:** `docs/imports/ATLAS_TUI_SOURCE_INVENTORY.csv`

MiMo-Code is MIT licensed. That license permits use, copying, modification,
merging, publication, distribution, sublicensing, and sale provided its notice
is retained. ATLAS retains the notice above and in the linked third-party
notice. It does not import MiMo-Code's agent/runtime, SDK, provider layer,
authentication, configuration, storage, memory, telemetry, updater, sharing,
plugin runtime, or hosted-service authority; those remain ATLAS-owned.

## Other Dependencies

ATLAS references these external projects (not vendored, used as architectural
references or optional integrations):

- **Odysseus** — MIT, reference for cockpit UX patterns
- **FreeLLMAPI** — MIT, reference for local LLM gateway patterns
- **Terax AI** — Apache-2.0, reference for native shell architecture
- **Twenty CRM** — AGPL-3.0 (sidecar-only, no copyleft obligation)
