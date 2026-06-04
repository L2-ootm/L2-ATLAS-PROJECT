# Synthesized Constraints (ingest-docs merge — 2026-06-04)

Sources: AGENTS.md (SPEC), RISKS.md (DOC), HERMES_FOUNDATION_PIN.md (ADR)

---

## Hard constraints (from AGENTS.md non-negotiables)

C-01  Do NOT copy secrets or raw personal data into this repo (ever).
C-02  Do NOT destructively reorganize existing source repos (L2-Atlas, L2-atlas-hermes, L2-BOT, etc.).
C-03  Do NOT use Electron as the default desktop stack.
C-04  Do NOT build CRM before mission/run/audit/wiki/cockpit loop is working.
C-05  Do NOT build WhatsApp production integration in MVP.
C-06  Do NOT build native overlay before runtime loop exists.
C-07  Keep all autonomous actions auditable: reason + input + tool/action + output + verification.
C-08  Do NOT vendor C:/Users/Davi/AppData/Local/hermes/hermes-agent — it contains secrets/state (R2).

## Risk mitigations (from RISKS.md + implementation plan)

R-01  Scope explosion — ship Operator Cockpit MVP first; CRM/overlay/billing are Milestone 2+.
R-02  Forking Hermes too early — plugin/hook-first divergence policy; in-core edits documented.
R-03  Copying old code without review — classify repos before importing; extraction plan required.
R-04  Building UI before runtime — runtime + schemas first; cockpit after MVP loop works.
R-05  Mixing personal KB into product repo — Personal_Data_KB stays separate always.
R-06  Hermes monolithic core (R1) — cli.py ~685KB; plugin-first to avoid drift.
R-07  Hermes install contains secrets (R2) — always clone fresh from upstream; secret-scan gate.
