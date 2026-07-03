# Sprint Plan — Finish Active Milestones by 2026-07-09

**Captured:** 2026-07-03  
**Deadline:** 2026-07-09  
**Mode:** documentation only; no implementation in this pass.

## Operator Direction

The next sprint is a finish-line pass, not a broad feature expansion. The goal is to close the
current milestone set with enough polish and stability that ATLAS feels coherent across the web
cockpit, terminal, cashflow module, provider/model control plane, CLI, and installer path.

## Current Visual Debt

- The cockpit layout still lacks polish in basic spacing: several surfaces have text too close to
  card edges, with near-zero margin/padding in places where the visual system should breathe.
- Layering needs cleanup. Some surfaces, rails, nav groups, backgrounds, and glass panels do not
  yet feel like one intentional depth stack.
- The Settings and System pages should not exist as two competing destinations. They should become
  one modular control page with tabs/sections and dynamic options.
- The model configuration UI must stop being a static page. It needs to be schema/registry-driven:
  providers, models, auth state, routing/fallbacks, probes, and effective config should render from
  the live configuration/model contracts.

## Milestones to Finish by 2026-07-09

### 1. Agent configuration polish — web and terminal

Unify how the operator sees and changes agent settings across cockpit and TUI:

- provider/model/auth state;
- permission mode;
- workspace/project selection;
- context/Brain retrieval controls;
- diagnostic status;
- restart-required vs hot-reloadable settings.

The cockpit page should be a single modular Settings/System surface. The terminal should expose the
same categories through polished commands and/or panels.

### 2. Cashflow integration stabilization

Cashflow must behave as a stable ATLAS module, not a pasted separate product:

- launch/handoff path is deterministic;
- module health is visible;
- route smoke remains green;
- dashboard spacing and panel padding are corrected;
- visual polish focuses on spacing/layers first, not a full redesign detour.

### 3. Modular dynamic model panel

The Models/configuration panel must be driven by the runtime contracts:

- provider registry;
- model registry;
- auth state;
- route/fallback policy;
- probe/health results;
- effective value + source + validation state.

No hardcoded “demo” provider cards should be treated as final behavior.

### 4. Installation package

Create the installation/distribution package path for local ATLAS:

- install;
- update;
- uninstall/rollback notes;
- doctor/health check;
- clean-machine instructions;
- versioned package artifact.

### 5. CLI command polish

The CLI should read as one coherent ATLAS command surface:

- consistent command naming;
- useful `--help`;
- status/doctor/config/model/cashflow commands discoverable;
- no duplicate legacy command paths unless intentionally retained as rollback;
- output is compact, branded, and script-safe where appropriate.

### 6. TUI refactor with MiMoCode as principal presentation donor

MiMoCode is the principal presentation donor for the next TUI refactor. The allowed direction is:

- copy/port/modify MIT-licensed MiMo presentation mechanics with notice retained;
- keep ATLAS runtime, providers, config, audit, policy, session, and storage as the authority;
- target visual fidelity first: gradient smoothness, animation cadence, composer geometry,
  command menu alignment, spacing, and transcript ergonomics;
- avoid importing MiMo’s backend/runtime as a second product.

## Acceptance Bar

By 2026-07-09, the sprint should be considered complete only if:

1. Settings/System are documented and implemented as one modular control page, or the remaining
   route compatibility shim is explicitly documented.
2. Model configuration works from live contracts rather than static page assumptions.
3. Cashflow integration has stable launch, health, and route checks.
4. Installer/package path exists with a verified local flow.
5. CLI command surface is coherent enough for daily use.
6. TUI refactor plan/implementation clearly uses MiMoCode as the presentation baseline while
   retaining ATLAS runtime authority.
7. Visual polish includes spacing/layer rules, not only color/token changes.

## Non-Goals

- Do not do another uncontrolled dashboard redesign pass.
- Do not split Settings and System further.
- Do not add a second runtime/backend from a donor project.
- Do not broaden this sprint into CRM/voice/overlay work.
