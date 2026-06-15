# ATLAS v1.0 — Public Release Hardening

Evidence and decisions from the Phase 9.5 hardening gate. Read together with
`docs/imports/SKILL_INVENTORY.md` (classification), `foundation/atlas-hermes/DIVERGENCE_LOG.md`
(vendored-foundation changes), and `.planning/phases/09.5-public-hardening/09.5-VERIFICATION.md`
(test/edge/idempotency evidence).

**Date:** 2026-06-15 · **Scope:** hardening only, no product features.

---

## 1. Unsafe skill quarantine (blockers B1 / B4) — RESOLVED

Two model-safety-circumvention skills shipped in the vendored **default** skill
tree and would load on a clean install. Both were moved out of the load path:

| Skill | From | To | Blocker |
|---|---|---|---|
| `godmode` (LLM jailbreak) | `foundation/atlas-hermes/skills/red-teaming/godmode` | `foundation/atlas-hermes/quarantined-skills/godmode` | B1 |
| `obliteratus` (abliterate refusals) | `foundation/atlas-hermes/skills/mlops/inference/obliteratus` | `foundation/atlas-hermes/quarantined-skills/obliteratus` | B4 |

- `quarantined-skills/` is not a load path and carries a README forbidding manifest
  references and default loading.
- The now-empty `skills/red-teaming/` directory was removed; `skills/mlops/inference/`
  keeps its legitimate siblings (`llama-cpp`, `vllm`).
- Recorded in `DIVERGENCE_LOG.md` D-LOG-001. Upstream attribution/history preserved
  (move via `git mv`, no history rewrite).

`vault-scan` (B5): **not physically present** in the repo — reference-only in the
inventory. Nothing to move; it stays excluded from every manifest.

Dual-use offensive skills (B2) under `foundation/atlas-hermes/optional-skills/security/`
and `.../research/` remain **opt-in only** and must never enter a Core/Operator
manifest. Adding an authorization-acknowledgement gate before load is carried as a
follow-up (does not block v1.0 because none are default-loaded).

---

## 2. Imported skill naming plan (SG-3 / SG-4) — success criterion 2 & 9

**Rule:** a public pack name describes the *capability and pack placement*, never the
import origin or a legacy/internal brand.

**v1.0 status — no rename required to ship:**

- The **ATLAS Core Pack** (the only default-installed v1.0 pack) is composed entirely
  of **SG-1 Hermes-native** skills (e.g. `writing-plans`, `requesting-code-review`,
  `systematic-debugging`, `ocr-and-documents`). None carry import-origin branding.
- **GSD (SG-3)** is intentionally **not shipped** — it is ATLAS's own build framework,
  not operator-facing content.
- **SG-4** skills (the `ultra*` / Claude-skills family) are **not** in the Core or
  Operator packs; per the §8 dedup, their functions are covered by the SG-1 canonical
  picks, so the SG-4 duplicates are `external-reference` / dropped.

Therefore the v1.0 public surface exposes **no import-origin-branded skill names**.
Success criteria 2 and 9 are met for v1.0 by *exclusion*, not by renaming shipped skills.

**Forward-looking naming table** (applies only if/when these candidate skills are
promoted into a future public pack — none ship in v1.0):

| Current name | Source | Proposed ATLAS public name | Reason | Rename required before ship? |
|---|---|---|---|---|
| `ultradesign` / `frontend-design` / `ui-ux-pro-max` | SG-4 | `atlas-interface-design-review` | Capability-named; drops `ultra`/import branding. | Yes — before any design pack ships |
| `ultrareview` | SG-4 | `atlas-extra-marathon-review` | Only after L2-specific content is removed and it is verified public-safe. | Yes |
| `ultraplan` | SG-4 | (do not ship) | Planning is covered by `writing-plans` (Core). | N/A — not shipped |
| `gsd-*` (SG-3) | SG-3 | (do not ship) | Build framework, not product content. | N/A — not shipped |
| `L2-Systems-Design-System` | SG-6 | (internal only) | L2 brand IP; `public_safe: false`. | N/A — never public |

---

## 3. Secret / artifact scan — success criterion 3 & 4

Scan over **tracked** files (gitignored DBs/sessions/`.env`/`_EXTERNAL_REPOS` already
excluded). Patterns: GitHub/OpenAI/Slack token signatures, private-key blocks, and the
local home path `<USER_HOME>`.

| Finding | Verdict |
|---|---|
| Token-like strings (`ghp_xxxx`, `sk-xxxx`, `xoxb-…`) | **Benign.** All are `.env.example` placeholders, MCP doc examples, the `redact.py` module's own pattern comments, or test fixtures with fake values. No real secret. |
| Private-key blocks | **Benign.** Only `-----BEGIN … PRIVATE KEY-----` referenced inside the redaction module's documentation. |
| Local home path `<USER_HOME>` in **scripts** | **FIXED.** `scripts/freellmapi_model_benchmark.py` and `scripts/freellmapi_closed_env_smoke.py` no longer hardcode the personal path (now `FREELLMAPI_DIR` env + repo-relative defaults / placeholder). |
| Local home path `<USER_HOME>` in **docs** | **Bounded finding (cosmetic).** ~25 historical planning docs under `docs/plans/`, `docs/foundation/`, `docs/imports/`, `docs/research/`, `docs/architecture/` embed the absolute path. These leak the OS username only (no secret). See §4. |
| Runtime DBs / sessions / `.env` | **None tracked** — covered by `.gitignore`. |

No real secrets, no personal private data (admissions/scholarship/etc.), no runtime
DB or session logs are tracked.

---

## 4. Remaining public-release blockers / decisions

| # | Item | Severity | Bounded action | Owner |
|---|---|---|---|---|
| 1 | `<USER_HOME>` in ~25 historical docs | Low (username leak, cosmetic) | Decide release packaging: either exclude internal `docs/plans/` + `.planning/` from the public bundle, or run a one-pass path-scrub (`<USER_HOME>/...` → `<repo>` / `~`). Do **not** mass-edit historical records before the packaging decision. | Release packaging step (pre-publish) |
| 2 | `.planning/` is internal GSD state | Low | Confirm `.planning/` is excluded from the public bundle (it is build process, not product). | Release packaging step |
| 3 | No `atlas db init` bootstrap command | Low | Documented stand-in in `RUNNING.md` §1; create a real bootstrap command in a future phase. | Post-v1.0 |
| 4 | Offensive skills (B2) lack an authorization gate | Medium | Add an acknowledgement gate before load; never list in default manifests. | Post-v1.0 (not default-loaded, so not a v1.0 blocker) |
| 5 | `ATLAS_DB` honoured by gateway but not by `atlas` CLI | Low | Documented in `RUNNING.md`; make CLI DB path env-configurable in a future phase. | Post-v1.0 |
| 6 | ~~Cockpit `@import`s remote Google Fonts~~ | ~~Medium~~ | **RESOLVED 2026-06-15** — fonts self-hosted via `@fontsource/*` (Inter/JetBrains Mono/Orbitron); remote `@import` removed; build verified with zero CDN references. Found + fixed in 09.5 manual UAT (F1). | Done |
| 7 | Dynamic routes return HTTP 404 status under static hosting | Low | Configure the production static host's SPA fallback (serve index/`200.html` with 200). SPA still renders; cosmetic status only (09.5 UAT F2). | Release packaging step |
| 8 | Prebuilt `atlas-gateway.exe` can go stale vs source | Low | RUNNING.md §2 should instruct operators to `cargo build --release` rather than trust an existing binary; the 06-11 binary predated the CORS layer (09.5 UAT F3). Local-only. | Post-v1.0 |

Items 1–5 do not block a v1.0 archive. Item 6 (remote fonts) does not block the
internal archive but must be closed before the public/open-source publish. Items 1–2
and 6–7 must be honoured at the moment of actual public publish (a packaging step),
not by editing the working tree now.

---

## 5. Verdict

The repository is **ready for v1.0 archive**, and **ready for public release after the
packaging step honours blockers 1–2** (exclude internal docs/`.planning`, or scrub the
home path). All automated suites pass; the unsafe default skills are quarantined; no
real secrets are tracked. Manual operator UAT (`MANUAL_TEST_GUIDE.md`) is the remaining
human gate before declaring v1.0 accepted.
