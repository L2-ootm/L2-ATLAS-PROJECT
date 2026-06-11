# Foundation Divergence Log

Every change to `foundation/atlas-hermes/` relative to upstream SHA
`e8b9369a9d2df36139a5055cae3ed3c15691e03e` MUST be recorded here
(D-018 non-negotiable; D-021 §9). Format per entry:

- **What** changed (paths)
- **Why** upstream behavior is insufficient
- **Classification:** upstream-candidate | ATLAS-plugin | ATLAS-only
- **Migration impact** on future upstream syncs

---

## DIV-F-001 — Initial vendor with exclusions (2026-06-10)

- **What:** Vendored upstream at pinned SHA into `foundation/atlas-hermes/`,
  excluding: `.git/`, `website/` (19.6 MB marketing site, not runtime code),
  `node_modules/`, `__pycache__/`, `.pytest_cache/`, `.coverage`.
- **Why:** Foundation evolution must be version-controlled in this repo
  (`_EXTERNAL_REPOS/` is gitignored and cannot carry divergences). The
  excluded paths are not part of the agent runtime.
- **Classification:** ATLAS-only (packaging decision, no code change).
- **Migration impact:** None — upstream syncs diff against the pinned SHA;
  excluded paths stay excluded.

## DIV-F-002 — atlas_audit registered as bundled foundation plugin (2026-06-10)

- **What:** Added `foundation/atlas-hermes/plugins/atlas_audit/`
  (`plugin.yaml` + `__init__.py` shim delegating to the canonical
  `atlas_audit` package in `services/agent-runtime/`).
- **Why:** D-002 (audit-first runtime) requires every foundation action to
  emit AuditEvents without per-machine setup. Bundling makes the audit bus
  load on every foundation boot; the project-plugins path
  (`./.hermes/plugins/`) would require `HERMES_ENABLE_PROJECT_PLUGINS` per
  environment.
- **Classification:** ATLAS-plugin (uses the upstream plugin surface as
  designed; no core files edited — D-001 preserved).
- **Migration impact:** None on sync — new directory, no upstream files
  touched. If upstream ships a plugin named `atlas_audit` (unlikely),
  collision resolution favors later sources per plugin loader docs.

## DIV-F-003 — Built-in `atlas` skin, set as fork default (2026-06-10)

- **What:** `hermes_cli/skin_engine.py` — added an `atlas` entry to
  `_BUILTIN_SKINS` (L2 dark-prism/cyan palette, ATLAS banner logo, L2 hero
  art, `branding.agent_name = "L2 ATLAS"`, new `branding.vendor_name` key)
  and changed `_active_skin_name` default from `"default"` to `"atlas"`.
  Docstring built-in list updated.
- **Why:** Operator-facing rebrand (D-021 §8/§9 staged-rebrand policy) using
  the foundation's own skin surface instead of string edits scattered through
  cli.py. `/skin default` or `display.skin: default` restores the upstream
  Hermes look — useful for upstream-diff debugging.
- **Classification:** ATLAS-only (the skin entry); the default-name flip is
  ATLAS-only by definition.
- **Migration impact:** Trivial — additive dict entry plus a one-line default
  change; rebase conflicts only if upstream rewrites `_BUILTIN_SKINS`
  wholesale.

## DIV-F-004 — Banner brand strings made skin-aware (2026-06-10)

- **What:** `hermes_cli/banner.py` — `format_banner_version_label()` now
  reads `branding.agent_name` from the active skin (was hardcoded
  `"Hermes Agent v…"`); the model line vendor suffix now reads
  `branding.vendor_name` (was hardcoded `"Nous Research"`). Both keep the
  upstream strings as fallbacks.
- **Why:** The skin engine documents `branding.agent_name` as the banner
  title control, but the banner hardcoded both strings — skins (including
  upstream's own `ares`) could never fully rebrand. Required for the `atlas`
  skin to take effect.
- **Classification:** upstream-candidate (fixes the skin engine's own
  contract; behavior unchanged for the `default` skin).
- **Migration impact:** Two small hunks in `banner.py`; low conflict risk.

## DIV-F-005 — Branded CLI entry-point aliases (2026-06-10)

- **What:** `pyproject.toml [project.scripts]` — added `atlas-agent`
  (= `hermes_cli.main:main`) and `atlas-harness` (= `run_agent:main`).
  Upstream `hermes` / `hermes-agent` / `hermes-acp` names retained.
- **Why:** Operator-facing branding (D-021 §8): the branded launch commands
  exist without removing upstream names that scripts/docs may reference.
- **Classification:** ATLAS-only.
- **Migration impact:** Additive lines in `[project.scripts]`; negligible.

## DIV-F-006 — `atlas` skin retokened to canonical L2 design system (2026-06-11)

- **What:** `hermes_cli/skin_engine.py` — the `atlas` built-in skin colors,
  banners, and branding strings replaced with canonical L2 Systems Dark Prism
  tokens: Electric Violet `#7F00FF` (brand/borders/response box), Cyber Blue
  `#00F0FF` (labels/telemetry/live data), Titanium White `#E0E0E0` (body —
  pure white forbidden), Status Green `#00FF94`, Signal Amber `#FFD600`,
  Crimson `#FF0055`/`#FF003C` (error/critical), void backgrounds `#0A0A0A`.
  Banner logo upgraded to a full-width two-tone wordmark — `L2` block in
  Cyber Blue + `ATLAS` in a violet prism ramp — with a contour-strata
  separator and an integrated HUD status line
  (`:: ATLAS · OPERATOR HARNESS · PROTOCOL: ONLINE`). Hero keeps the violet
  `L2` mark with the `L2 // SYSTEMS` wordmark + `>> ATLAS HARNESS` footer.
  Voice normalized to HUD discipline (statements, `::` prefixes, no
  exclamation marks).
- **Why:** DIV-F-003 used an ad-hoc cyan/slate palette; the L2 brand
  guidelines define exact signal tokens and voice. CLI must match the
  cockpit and marketing surfaces (one brand system across layers).
- **Classification:** ATLAS-only (edits only the `atlas` skin dict added in
  DIV-F-003).
- **Migration impact:** Same as DIV-F-003 — additive dict entry; no upstream
  lines touched beyond the docstring built-in list.
