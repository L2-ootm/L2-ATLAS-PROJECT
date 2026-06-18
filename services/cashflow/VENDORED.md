# Cashflow — vendored ATLAS module

This is **L2-Cashflow vendored into ATLAS** as an optional, activatable module
(Decision 3b — `.planning/prep/gateway-control-tauri-cashflow-decisions-2026-06-18.md`).

- **Origin:** `aDuque-L2/L2-Cashflow` (L2-owned, private). Imported 2026-06-18.
- **Detached:** the original `.git` history is intentionally NOT vendored — this tree
  lives in ATLAS's git history, not as a submodule or a clone. Changes happen here;
  back-porting to the origin repo (if ever needed) is a manual cherry-pick.
- **Stripped on import:** `node_modules/`, `.next/`, `.git/`, `.gemini/`, `*.log`,
  `dev.db*`, the `.docx` report, and scratch files (`test-db.js`, `test-prisma.js`,
  `test-phase2.ts`, `update-budget.ts`).

## Stack
Next.js 16 (App Router) + React 19 + Tailwind 4. DB backend is a **repository-toggle**:
`better-sqlite3` (local) ↔ `@supabase/supabase-js` (Supabase), env-gated via
`isSupabaseConfigured()` (`lib/supabase.ts`, `lib/repositories/`). Raw schema in
`supabase/schema.sql`. Also ships MCP (`lib/mcp`), webhooks (`lib/webhooks`), a FinOps
engine (`lib/engine`), and `@opengsd/gsd-core`.

## How it integrates with ATLAS
- **Activatable module:** off by default; toggled in the cockpit System page (persisted
  in the ATLAS `modules` table). When active it appears in the cockpit sidebar and its
  Next.js process is run; when inactive it is not built/run (keeps the default lean).
- **DB selection:** local SQLite or Supabase, chosen via setting (surfaced in the System
  page), with **non-destructive** initial migration (additive `CREATE TABLE IF NOT
  EXISTS` only — never drops/truncates on setup).
- **Agent actuation:** ATLAS's P4 `ClaudeCodeAgent` can drive cashflow via its MCP +
  webhook seams, audited through the AuditEvent bus and policy/approval gates.

## Local dev (standalone, until module wiring lands)
```
cd services/cashflow
npm install
npm run dev   # http://localhost:3000
```
