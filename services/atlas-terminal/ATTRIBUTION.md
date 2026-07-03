# atlas-terminal Attribution

This package is the staged home of the ATLAS terminal surface built on the
MiMo-Code MIT presentation donor (the same move MiMo-Code made on opencode).

- Donor: XiaomiMiMo/MiMo-Code `v0.1.2`, commit
  `86d95a79bf0879bcb442ffe6b12914f6d8e68a4e` (MIT — Copyright (c) 2026 MiMo
  Code, Xiaomi Corporation; Copyright (c) 2025 opencode). Full notice:
  `docs/third-party/ATLAS_TUI_UPSTREAM_NOTICE.md`.
- STAGE 0 contains no copied donor source yet — only the ATLAS-authored
  fetch-adapter seam and boot shell. Donor TUI source is copied (with the MIT
  notice retained and identity scrubbed) from STAGE 2 onward per
  `docs/plans/2026-07-03-mimo-donor-tui-refactor-plan.md`.
- The MiMo-Code agent/runtime, server, storage, provider authority, telemetry,
  updater, and account flows are excluded. ATLAS keeps runtime, provider mesh,
  config, audit, policy, session, and storage authority.
