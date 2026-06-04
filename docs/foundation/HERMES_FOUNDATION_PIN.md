# Hermes Foundation Pin

Date: 2026-06-04
Status: pinned (vendoring method deferred — see below).

## Pin (verified against the live local install 2026-06-04)

- Upstream: `https://github.com/NousResearch/hermes-agent.git`
- License: **MIT** (vendoring/forking permitted; retain `LICENSE` + attribution)
- Version: `0.14.0` (tag `v2026.5.16-1302-ge8b9369a9`)
- Pinned commit: `e8b9369a9d2df36139a5055cae3ed3c15691e03e`
- Language: Python-primary; TS/JS confined to TUI/web surfaces
- Shape risk (R1): monolithic core — `cli.py` ~685KB, `run_agent.py` ~202KB, `hermes_state.py` ~142KB

Verification command:
```bash
cd "C:/Users/Davi/AppData/Local/hermes/hermes-agent" && \
  git remote get-url origin && git rev-parse HEAD && git describe --tags && \
  head -1 LICENSE && grep -m1 '^version' pyproject.toml
```

## Critical: do NOT vendor the local install (R2)

`C:/Users/Davi/AppData/Local/hermes/hermes-agent` is the **runtime instance**. It contains
secrets and personal state: `auth.json`, `.env` (~23KB), `state.db` (~73MB), session DBs,
gateway state. Copying it would violate the non-negotiables (no secrets, no raw personal data).

The install is used only as a **read-only reference** to identify upstream + SHA. All vendoring
uses a **fresh clone from upstream at the pinned SHA** (Task 2), which ships `.env.example`
(not `.env`) and no state DB.

## Vendoring decision (deferred)

1. Clone fresh from upstream at the pinned SHA into `_EXTERNAL_REPOS/hermes-agent` (OUTSIDE
   this project's git tree) for inspection — Task 2.
2. Run the extension-point audit (Task 3) to measure how much in-core change ATLAS truly needs.
3. Only then choose the in-repo method (git submodule vs vendored subtree vs fork) and record
   it as a follow-up decision. Choosing now would be premature given R1.

## Divergence policy (binds all future Hermes changes)

Default order of preference:

```txt
plugin > tool > hook > skill > ATLAS-only override > in-core edit
```

Every in-core edit to the Hermes foundation requires a divergence decision record in
`docs/decisions/`, classified per `FOUNDATION_STRATEGY.md`:
`upstreamable | plugin/tool | ATLAS-only | experimental`.
