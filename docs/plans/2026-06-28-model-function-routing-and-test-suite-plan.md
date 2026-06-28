# ATLAS Model/Function Routing, Config UX & Provider/Model Test Suite — Plan

**Date:** 2026-06-28
**Status:** Forward-scope design (documentation; not yet planned into a milestone)
**Owner directive (2026-06-28):** After the provider mesh substrate (P1–P5 + P3) landed, capture
the larger surface we still owe: a full **Models page suite** in the WebUI, a **full interactive
setup + config UX** in the CLI, **modular per-function model routing** (starting from the Hermes
base functions), **test suites for models and providers**, **direct interactive testing**, and the
**planned UX** across all three surfaces (CLI / TUI / WebUI).

This is the management/observability layer on top of the now-working four-mode provider mesh
(`api_key` / `oauth_import` / `claude_code` / `freellmapi`). The mesh answers *"how do I wire a
provider?"*; this plan answers *"which model runs each function, and how do I prove it works?"*

---

## 1. Core concept — modular function → model routing

Today a run resolves ONE provider/model for the whole agent (`config_service.resolve_provider`
+ `Focus.framework` model override). The foundation already separates work across distinct
**functions** that each *could* run on a different model:

| Function (Hermes base) | Source | Today's model | Why it could differ |
|---|---|---|---|
| **main agent** | `run_agent.AIAgent` (via `NativeAtlasAgent`) | provider/model from config + Focus | the reasoning workhorse — strongest model |
| **curator** | `foundation/atlas-hermes/agent/curator.py` | foundation default | background skill consolidation — cheaper/async model is fine |
| **auxiliary** | `foundation/atlas-hermes/agent/auxiliary_client.py` | foundation default | sub-tasks (session search, quick lookups) — small/fast model |
| **background review** | `foundation/atlas-hermes/agent/background_review.py` | foundation default | batched consolidation — cost-optimized model |
| **(future ATLAS functions)** | golden workflows, context/brain retrieval rerank, etc. | n/a | extensible registry |

**Goal:** a **function registry** where each function binds to a **provider profile** (mode +
provider + model), with a sane default (the main provider) and per-function overrides. Functions
are **modular** — the registry ships with the Hermes base set and is extensible without code
changes to consumers. Setting "which model runs the curator" should be a one-line config edit or a
single click/keystroke, not a foundation patch.

### 1.1 Proposed config shape (additive, back-compat)

```yaml
provider:            # the existing single active profile (default for every function)
  auth_mode: api_key
  name: openrouter
  model: anthropic/claude-sonnet-4
  base_url: ""

functions:           # NEW — optional per-function overrides; absent ⇒ inherit provider above
  curator:
    profile: cheap-openrouter      # references a named profile in `profiles:`
  auxiliary:
    model: anthropic/claude-haiku-4-5   # inline model override on the default profile

profiles:            # NEW — named provider profiles the functions/TUI can reference
  cheap-openrouter:
    auth_mode: api_key
    name: openrouter
    model: anthropic/claude-haiku-4-5
```

Resolution precedence (extends A4): explicit call override → `functions.<fn>` → active `provider`
→ foundation default. Every binding is **immutable per run** (the run-contract snapshot already
records the resolved runtime/mode/model; extend it to record the *per-function* resolution too, so
audits show exactly which model served curator vs. main).

> **Constraint:** the foundation is used, not edited (D-001). Per-function model selection must be
> threaded through the existing foundation entry points (env/kwargs the harness already accepts),
> NOT by forking curator/auxiliary. De-risk spike required to confirm each Hermes function exposes
> a model/provider seam before committing (mirror the P2/P4 spike discipline).

---

## 2. WebUI — full Models page suite

Current state: `services/web-ui-react/src/routes/Models.tsx` + `/v1/models` (list) + the
provider/auth control-plane routes. Target: a complete management surface, not a single list.

**Panels:**
1. **Provider mesh board** — the four wiring modes with live availability + remediation (reuse
   `provider_service.modes_status`). Each mode has a **"Wire"** action (api_key entry hidden;
   `codex import`; `claude_code` doctor; `freellmapi` base_url + **privacy warning**) and a
   **"Test"** action (§4).
2. **Model catalog** — browsable list from `/v1/models` (provider's available models), with
   filter/search, capability tags, and "set as default" / "assign to function".
3. **Function → model matrix** — a row per registered function (main, curator, auxiliary,
   background-review, …), each showing its resolved profile/model and a picker to override. The
   headline deliverable: *"setting the models for functions becomes easy."*
4. **Test results** — last probe per provider/function: status (live/mock/failed), latency,
   token/cost estimate, and the streamed sample output. Re-run inline.
5. **Active resolution summary** — the operator's "what will actually run" view (mock-vs-live
   verdict per function), mirroring `atlas provider status` but matrixed.

**Contract:** all reads/writes go through the Rust gateway (dispatch-only, D-022) — extend
`/v1/provider/*` / `/v1/config` with function-routing and a `POST /v1/provider/test` probe; never
echo secrets. The page is a thin client; Python owns resolution.

---

## 3. CLI — full interactive setup + config UX

Current state: `atlas setup` (basic wizard), `atlas config get/set/json`, `atlas auth …`,
`atlas provider status/modes/test`, `atlas models`, `atlas doctor`. Target: a guided, interactive
end-to-end flow plus granular non-interactive commands.

**Interactive wizard (`atlas setup`, expanded):**
1. Pick **auth mode** (api_key / codex import / claude_code / freellmapi) — with the per-mode
   availability + privacy notes inline (freellmapi warning surfaced before selection).
2. Enter/resolve **credentials** for the chosen mode (hidden input; or `import-codex`; or
   claude_code `doctor`; or freellmapi `base_url`).
3. Pick the **default model** (from `/v1/models` / provider catalog).
4. **Per-function assignment** — walk the function registry (main → curator → auxiliary → …),
   offering "inherit default" or an override; explain each function's role in one line.
5. **Test** each wired provider/function (§4) and show a pass/fail board before saving.
6. Atomically write config (re-validates; inline secret rejected, env:VAR only).

**Granular commands (non-interactive, scriptable):**
- `atlas models list [--provider]` / `atlas models set <function> --model <m> [--profile <p>]`
- `atlas models show` — the function→model matrix (table + `--json`).
- `atlas provider test [--mode <m>]` / `atlas models test <function>` — direct probe (§4).
- `atlas profiles add|list|rm` — named profiles for reuse across functions.
- `atlas doctor` already reports `claude_code:` + `provider: live/mock`; extend with a
  per-function resolution line when `functions:` is configured.

Windows ASCII-safety enforced (the CliRunner-hidden-glyph lesson from the CLI-surface work).

---

## 4. Provider & model test suites + direct interactive test

The "wire any provider and **test**" north star. Three tiers, shared across CLI/TUI/WebUI:

1. **Connectivity probe** (fast, per provider/mode): a one-shot real run through the live
   substrate that streams audit frames and reports live-vs-mock + latency + a sample response.
   This is P7's "test-probe" generalized; back it with `POST /v1/provider/test` (gateway dispatch
   → a real `mission run --execute` on a throwaway/ephemeral mission, archived after) so all three
   surfaces share one implementation.
2. **Per-function smoke**: run each function's model on a tiny canonical task (e.g. curator on a
   2-item consolidation, auxiliary on a lookup) and assert a well-formed, non-mock result. Surfaces
   "the curator model you picked actually works."
3. **Model conformance / regression**: reuse the existing 10.2 **30-scenario evaluation dataset +
   deterministic promotion gate** to score a candidate model before it's set as a function's
   default. Paid/network probes are **opt-in and budgeted** (per the v1.2 constraint).

**Direct interactive test UX** (all three surfaces): pick provider + model (or a function) → type a
prompt → stream the result with live metrics (tokens, latency, cost estimate, mock/live badge) →
optionally "promote this model to <function>". In the **TUI** this is the P7 provider/settings pane
(`/provider`); in the **CLI** it's `atlas provider test`/`atlas models test`; in the **WebUI** it's
the Models page "Test" action.

---

## 5. Planned UX (per surface)

- **CLI:** linear wizard with clear stage headers + a final pass/fail board; granular subcommands
  for power users; `--json` everywhere; ASCII-safe.
- **TUI (P7):** a provider/settings pane — left: mode + function list; right: credential entry +
  model picker + a live test-probe stream. One keystroke to wire, one to test, one to assign.
- **WebUI:** the Models page suite (§2) — provider board, catalog, function matrix, test results,
  resolution summary; L2 glass/topo language; graceful offline/empty/mock states.

All three render the **same** substrate (`provider_service` + the function registry + the test
endpoints). No surface owns business logic (D-022); Python resolves and tests, surfaces render.

---

## 6. Roadmap placement & dependencies

- Slots **after** the current Go-TUI line (P6 panes → **P7 in-TUI provider/settings test-probe**,
  which is the TUI slice of §4) and pulls the rest forward into the **v1.2 Provider Mesh** milestone
  (`.planning/milestones/v1.2-ROADMAP-DRAFT.md`).
- **Substrate already in place:** four-mode mesh + native routing for all modes (P1–P5, P3),
  `provider_service` status/modes board, `atlas doctor` visibility, the run-contract snapshot, the
  10.2 eval dataset/gate, `/v1/models` + `/v1/provider/*` + `/v1/config`.
- **New work this plan implies (proposed phases):**
  1. **Function registry + per-function resolution** (config schema, resolution precedence,
     run-contract per-function record) — spike each Hermes function's model seam first (D-001).
  2. **Test substrate** — `POST /v1/provider/test` + per-function smoke + eval-gate hook (shared by
     all surfaces; ephemeral/throwaway mission discipline; budgeted network probes).
  3. **CLI interactive setup + config UX** — expanded `atlas setup`, `atlas models`, `atlas profiles`.
  4. **TUI provider/settings + test-probe pane** (= P7).
  5. **WebUI Models page suite** — provider board, catalog, function matrix, test results.

## 7. Open questions / risks

- **Foundation model seams (highest risk):** do `curator.py` / `auxiliary_client.py` /
  `background_review.py` each accept a model/provider override without editing the foundation? Spike
  before committing; fall back to "main model only, per-function deferred" if a seam is missing.
- **Cost/safety of test probes:** real probes spend tokens. Default to mock/dry-run; gate live
  probes behind explicit opt-in + a budget (reuse `SECRET_PATTERNS` stop so a test prompt can't leak
  secrets; freellmapi privacy warning applies).
- **Catalog freshness:** `/v1/models` depends on provider support; some modes (claude_code,
  freellmapi) may not enumerate models — show a manual-entry fallback.
- **Immutability:** per-function bindings must snapshot per run (audit can't be ambiguous about
  which model served which function).

---

## Provenance / references
- Substrate: `docs/plans/2026-06-28-atlas-go-tui-and-provider-mesh-design.md` (P1–P8),
  `services/agent-runtime/atlas_runtime/provider_service.py`, `…/agents/native.py`,
  `…/config_service.py`, `…/cli/doctor.py`.
- Hermes base functions: `foundation/atlas-hermes/agent/{curator,auxiliary_client,background_review,
  skill_commands,codex_runtime}.py` (used, not edited — D-001).
- Surfaces to extend: `services/web-ui-react/src/routes/Models.tsx`, gateway `/v1/models`,
  `/v1/provider/*`, `/v1/config`; CLI `atlas setup|config|auth|provider|models|doctor`.
- Eval reuse: the 10.2 30-scenario dataset + deterministic promotion gate.
