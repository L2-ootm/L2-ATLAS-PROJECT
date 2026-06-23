# TUI ATLAS Branding Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use compose:subagent (recommended) or compose:execute to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Rebrand the Hermes TUI to ATLAS — name, icon, taglines, env vars, config paths, package names.

**Architecture:** Mechanical rename across `foundation/atlas-hermes/ui-tui/` + `cli/tui.py` + TUI-relevant parts of `hermes_cli/main.py`. Six waves, each atomic-committed. No behavioral changes.

**Tech Stack:** TypeScript (Ink/React TUI), Python (launcher), npm (build)

---

## Task 1: Package Identity (Wave 1)

**Covers:** [S3 Wave 1]

**Files:**
- Modify: `foundation/atlas-hermes/ui-tui/package.json`
- Modify: `foundation/atlas-hermes/ui-tui/packages/hermes-ink/package.json`
- Modify: `foundation/atlas-hermes/ui-tui/src/types/hermes-ink.d.ts`
- Modify: All `src/` files importing `@hermes/ink`

- [ ] **Step 1: Rename package.json names**

In `foundation/atlas-hermes/ui-tui/package.json`, change:
```json
"name": "hermes-tui"
```
to:
```json
"name": "atlas-tui"
```

In `foundation/atlas-hermes/ui-tui/packages/hermes-ink/package.json`, change:
```json
"name": "@hermes/ink"
```
to:
```json
"name": "@atlas/ink"
```

- [ ] **Step 2: Update type declaration**

In `foundation/atlas-hermes/ui-tui/src/types/hermes-ink.d.ts`, change:
```typescript
declare module '@hermes/ink' {
```
to:
```typescript
declare module '@atlas/ink' {
```

- [ ] **Step 3: Update all @hermes/ink imports**

Run from `foundation/atlas-hermes/ui-tui/`:
```bash
grep -rl "@hermes/ink" src/ | head -30
```

For every file returned, replace `@hermes/ink` with `@atlas/ink`. Expected files include (but verify with the grep):
- `src/entry.tsx`
- `src/app.tsx`
- `src/components/*.tsx`
- `src/hooks/*.ts`
- `src/lib/*.ts`
- `src/app/*.tsx`

Use `replaceAll` edit on each file: `@hermes/ink` → `@atlas/ink`.

- [ ] **Step 4: Verify build**

```bash
cd foundation/atlas-hermes/ui-tui && npm run check
cd foundation/atlas-hermes/ui-tui && npm run build
```

Expected: both green, no unresolved module errors.

- [ ] **Step 5: Commit**

```bash
git add foundation/atlas-hermes/ui-tui/
git commit -m "feat(tui): rename packages hermes-tui → atlas-tui, @hermes/ink → @atlas/ink"
```

---

## Task 2: Brand Strings (Wave 2)

**Covers:** [S3 Wave 2]

**Files:**
- Modify: `foundation/atlas-hermes/ui-tui/src/theme.ts`
- Modify: `foundation/atlas-hermes/ui-tui/src/banner.ts`
- Modify: `foundation/atlas-hermes/ui-tui/src/components/branding.tsx`
- Modify: `foundation/atlas-hermes/ui-tui/src/components/helpHint.tsx`
- Modify: `foundation/atlas-hermes/ui-tui/src/components/modelPicker.tsx`
- Modify: `foundation/atlas-hermes/ui-tui/src/components/appChrome.tsx`
- Modify: `foundation/atlas-hermes/ui-tui/src/app/slash/commands/core.ts`
- Modify: `foundation/atlas-hermes/ui-tui/src/app/useMainApp.ts`
- Modify: `foundation/atlas-hermes/ui-tui/src/content/setup.ts`
- Modify: `foundation/atlas-hermes/ui-tui/src/lib/terminalParity.ts`

- [ ] **Step 1: theme.ts — brand name + icon**

In `src/theme.ts`, find the `BRAND` default object (around line 240). Change:
```typescript
name: 'Hermes Agent',
icon: '⚕',
```
to:
```typescript
name: 'ATLAS',
icon: '◆',
```

Also change the goodbye message:
```typescript
goodbye: 'Goodbye! ⚕'
```
to:
```typescript
goodbye: 'Goodbye! ◆'
```

- [ ] **Step 2: banner.ts — ASCII logo + art**

Replace the `LOGO_ART` constant (the 6-line "HERMES" block art around line 46-53) with an ATLAS block art. Example (adjust to match the existing style):

```typescript
export const LOGO_ART = `
 █████╗ ██████╗ ████████╗    ███████╗ █████╗ ███████╗██╗  ██╗
██╔══██╗██╔══██╗╚══██╔══╝    ██╔════╝██╔══██╗██╔════╝██║  ██║
███████║██████╔╝   ██║       █████╗  ███████║███████╗███████║
██╔══██║██╔══██╗   ██║       ██╔══╝  ██╔══██║╚════██║██╔══██║
██║  ██║██║  ██║   ██║       ██║     ██║  ██║███████║██║  ██║
╚═╝  ╚═╝╚═╝  ╚═╝   ╚═╝       ╚═╝     ╚═╝  ╚═╝╚══════╝╚═╝  ╚═╝`.trim();
```

Replace the `CADUCEUS_ART` constant (around line 55-71) with an ATLAS-appropriate mark — a simple compass star or abstract geometric art:

```typescript
export const CADUCEUS_ART = `
        ◆
       ╱ ╲
      ╱   ╲
     ╱  ◆  ╲
    ╱   │   ╲
   ◆────┼────◆
    ╲   │   ╱
     ╲  ◆  ╱
      ╲   ╱
       ╲ ╱
        ◆`.trim();
```

- [ ] **Step 3: branding.tsx — taglines + session panel**

In `src/components/branding.tsx`:

Change tagline constants (around line 47-49):
```typescript
TAG_FULL = 'Nous Research · Messenger of the Digital Gods'
TAG_MID = 'Messenger of the Digital Gods'
TAG_TINY = 'Nous Research'
```
to:
```typescript
TAG_FULL = 'ATLAS · AI Operating System'
TAG_MID = 'AI Operating System'
TAG_TINY = 'ATLAS'
```

Find all instances of `' · Nous Research'` (around lines 289, 320) and replace with `' · ATLAS'`.

Find the update command fallback (around line 405):
```typescript
info.update_command || 'hermes update'
```
replace with:
```typescript
info.update_command || 'atlas update'
```

- [ ] **Step 4: helpHint.tsx — exit command**

In `src/components/helpHint.tsx`, find:
```typescript
['/quit', 'exit hermes']
```
replace with:
```typescript
['/quit', 'exit atlas']
```

- [ ] **Step 5: core.ts — slash commands**

In `src/app/slash/commands/core.ts`:

Find the `/quit` help text (around line 114):
```typescript
help: 'exit hermes'
```
replace with:
```typescript
help: 'exit atlas'
```

Find the `/update` help text (around line 120):
```typescript
help: 'update Hermes Agent to the latest version (exits TUI)'
```
replace with:
```typescript
help: 'update ATLAS to the latest version (exits TUI)'
```

Find the history message tag (around line 477):
```typescript
`Hermes #${i + 1}`
```
replace with:
```typescript
`ATLAS #${i + 1}`
```

- [ ] **Step 6: modelPicker.tsx — provider config hints**

In `src/components/modelPicker.tsx`:

Find (around line 182):
```typescript
'run `hermes model` to configure'
```
replace with:
```typescript
'run `atlas model` to configure'
```

Find (around line 239, may be a comment):
```typescript
'run hermes model'
```
replace with:
```typescript
'run atlas model'
```

Find (around line 309):
```typescript
'Paste your API key below (saved to ~/.hermes/.env)'
```
replace with:
```typescript
'Paste your API key below (saved to ~/.atlas/.env)'
```

- [ ] **Step 7: setup.ts — setup panel**

In `src/content/setup.ts`:

Find (around line 7):
```typescript
'Hermes needs a model provider before the TUI can start a session.'
```
replace with:
```typescript
'ATLAS needs a model provider before the TUI can start a session.'
```

Find (around line 13):
```typescript
'exit and run `hermes setup` manually'
```
replace with:
```typescript
'exit and run `atlas setup` manually'
```

- [ ] **Step 8: useMainApp.ts — terminal tab title**

In `src/app/useMainApp.ts`, find (around line 532):
```typescript
'Hermes'
```
(the fallback terminal title when no model is set) replace with:
```typescript
'ATLAS'
```

- [ ] **Step 9: terminalParity.ts — SSH warning**

In `src/lib/terminalParity.ts`, find (around line 73):
```typescript
'depend on the machine running Hermes'
```
replace with:
```typescript
'depend on the machine running ATLAS'
```

- [ ] **Step 10: appChrome.tsx — emoji frames**

In `src/components/appChrome.tsx`, find (around line 30):
```typescript
EMOJI_FRAMES = ['⚕ ', '🌀', '🤔', '✨', '🍵', '🔮']
```
replace with:
```typescript
EMOJI_FRAMES = ['◆ ', '🌀', '🤔', '✨', '🍵', '🔮']
```

- [ ] **Step 11: Verify build**

```bash
cd foundation/atlas-hermes/ui-tui && npm run check
cd foundation/atlas-hermes/ui-tui && npm run build
```

Expected: green.

- [ ] **Step 12: Commit**

```bash
git add foundation/atlas-hermes/ui-tui/src/
git commit -m "feat(tui): rebrand user-visible strings Hermes → ATLAS"
```

---

## Task 3: Environment Variables (Wave 3)

**Covers:** [S3 Wave 3]

**Files:**
- Modify: `foundation/atlas-hermes/ui-tui/src/config/env.ts`
- Modify: `foundation/atlas-hermes/ui-tui/src/gatewayClient.ts`
- Modify: `foundation/atlas-hermes/ui-tui/src/entry.tsx`
- Modify: `foundation/atlas-hermes/ui-tui/src/lib/termux.ts`
- Modify: `foundation/atlas-hermes/ui-tui/src/lib/forceTruecolor.ts`
- Modify: `foundation/atlas-hermes/ui-tui/src/lib/memory.ts`
- Modify: `foundation/atlas-hermes/ui-tui/src/lib/perfPane.tsx`
- Modify: `foundation/atlas-hermes/ui-tui/src/lib/externalCli.ts`

- [ ] **Step 1: config/env.ts — all HERMES_TUI_* vars**

In `src/config/env.ts`, use `replaceAll` to change every occurrence of `HERMES_TUI` to `ATLAS_TUI`. Expected vars:
- `HERMES_TUI_RESUME` → `ATLAS_TUI_RESUME`
- `HERMES_TUI_QUERY` → `ATLAS_TUI_QUERY`
- `HERMES_TUI_IMAGE` → `ATLAS_TUI_IMAGE`
- `HERMES_TUI_MOUSE_TRACKING` → `ATLAS_TUI_MOUSE_TRACKING`
- `HERMES_TUI_DISABLE_MOUSE` → `ATLAS_TUI_DISABLE_MOUSE`
- `HERMES_TUI_NO_CONFIRM` → `ATLAS_TUI_NO_CONFIRM`
- `HERMES_TUI_INLINE` → `ATLAS_TUI_INLINE`
- `HERMES_TUI_FPS` → `ATLAS_TUI_FPS`

- [ ] **Step 2: gatewayClient.ts — timeout + URL vars**

In `src/gatewayClient.ts`, use `replaceAll` to change `HERMES_TUI` to `ATLAS_TUI` and `HERMES_PYTHON` to `ATLAS_PYTHON`. Expected vars:
- `HERMES_TUI_STARTUP_TIMEOUT_MS` → `ATLAS_TUI_STARTUP_TIMEOUT_MS`
- `HERMES_TUI_RPC_TIMEOUT_MS` → `ATLAS_TUI_RPC_TIMEOUT_MS`
- `HERMES_TUI_GATEWAY_URL` → `ATLAS_TUI_GATEWAY_URL`
- `HERMES_TUI_SIDECAR_URL` → `ATLAS_TUI_SIDECAR_URL`
- `HERMES_PYTHON` → `ATLAS_PYTHON`

- [ ] **Step 3: entry.tsx — heapdump + lifecycle vars**

In `src/entry.tsx`, use `replaceAll` to change `HERMES_TUI` to `ATLAS_TUI` and `HERMES_HEAPDUMP` to `ATLAS_HEAPDUMP`. Also change the stderr prefix strings:
- `hermes-tui:` → `atlas-tui:` (in all stderr output strings)

- [ ] **Step 4: lib/ files — remaining env vars**

In `src/lib/termux.ts`: `replaceAll` `HERMES_TUI` → `ATLAS_TUI`

In `src/lib/forceTruecolor.ts`: `replaceAll` `HERMES_TUI` → `ATLAS_TUI`

In `src/lib/memory.ts`: `replaceAll` `HERMES_HEAPDUMP` → `ATLAS_HEAPDUMP`

In `src/lib/perfPane.tsx`: `replaceAll` `HERMES_DEV_PERF` → `ATLAS_DEV_PERF`

In `src/lib/externalCli.ts`: find `'hermes'` (the default binary name fallback around line 8) and replace with `'atlas'`. Also rename the function `launchHermesCommand` → `launchAtlasCommand` if it exists, and update all callers.

- [ ] **Step 5: Grep for stragglers**

```bash
cd foundation/atlas-hermes/ui-tui && grep -rn "HERMES" src/ --include="*.ts" --include="*.tsx" | grep -v node_modules | grep -v __tests__
```

Any remaining `HERMES` references in non-test source files should be converted. Fix any found.

- [ ] **Step 6: Verify build**

```bash
cd foundation/atlas-hermes/ui-tui && npm run check
cd foundation/atlas-hermes/ui-tui && npm run build
```

Expected: green.

- [ ] **Step 7: Commit**

```bash
git add foundation/atlas-hermes/ui-tui/src/
git commit -m "feat(tui): rename env vars HERMES_TUI_* → ATLAS_TUI_*"
```

---

## Task 4: Config Paths (Wave 4)

**Covers:** [S3 Wave 4]

**Files:**
- Modify: `foundation/atlas-hermes/ui-tui/src/lib/history.ts`
- Modify: `foundation/atlas-hermes/ui-tui/src/lib/memory.ts`
- Modify: `foundation/atlas-hermes/ui-tui/src/lib/perfPane.tsx`
- Modify: `foundation/atlas-hermes/ui-tui/src/components/modelPicker.tsx`

- [ ] **Step 1: history.ts — home + history file**

In `src/lib/history.ts`, find (around line 6-7):
```typescript
const HISTORY_DIR = path.join(os.homedir(), '.hermes');
const HISTORY_FILE = path.join(HISTORY_DIR, '.hermes_history');
```
replace with:
```typescript
const HISTORY_DIR = path.join(os.homedir(), '.atlas');
const HISTORY_FILE = path.join(HISTORY_DIR, '.atlas_history');
```

- [ ] **Step 2: memory.ts — heapdump path**

In `src/lib/memory.ts`, find (around line 148):
```typescript
'~/.hermes/heapdumps'
```
or the code that constructs this path. Replace `'.hermes'` with `'.atlas'` and `'hermes-'` prefix with `'atlas-'` if present.

- [ ] **Step 3: perfPane.tsx — perf log path**

In `src/lib/perfPane.tsx`, find (around line 24):
```typescript
'~/.hermes/perf.log'
```
or the code that constructs this path. Replace `'.hermes'` with `'.atlas'`.

- [ ] **Step 4: modelPicker.tsx — .env path**

This was already changed in Task 2 Step 6. Verify:
```bash
grep -n "\.hermes" foundation/atlas-hermes/ui-tui/src/components/modelPicker.tsx
```
Expected: no matches (already changed to `.atlas`).

- [ ] **Step 5: Grep for stragglers**

```bash
cd foundation/atlas-hermes/ui-tui && grep -rn "\.hermes" src/ --include="*.ts" --include="*.tsx" | grep -v node_modules | grep -v __tests__
```

Any remaining `.hermes` path references should be converted to `.atlas`.

- [ ] **Step 6: Verify build**

```bash
cd foundation/atlas-hermes/ui-tui && npm run check
cd foundation/atlas-hermes/ui-tui && npm run build
```

Expected: green.

- [ ] **Step 7: Commit**

```bash
git add foundation/atlas-hermes/ui-tui/src/
git commit -m "feat(tui): rename config paths ~/.hermes/ → ~/.atlas/"
```

---

## Task 5: Python Launcher (Wave 5)

**Covers:** [S3 Wave 5]

**Files:**
- Modify: `foundation/atlas-hermes/hermes_cli/main.py` (TUI-related sections only)
- Verify: `services/agent-runtime/atlas_runtime/cli/tui.py`

- [ ] **Step 1: cli/tui.py — verify no HERMES refs**

```bash
grep -n "HERMES" services/agent-runtime/atlas_runtime/cli/tui.py
```

Expected: no matches. The launcher calls `_launch_tui()` which is in `hermes_cli/main.py`. The launcher itself doesn't reference HERMES env vars directly.

- [ ] **Step 2: hermes_cli/main.py — TUI trigger check**

Find the TUI trigger (around line 11178):
```python
if os.environ.get("HERMES_TUI") == "1" or "--tui" in argv:
```
replace with:
```python
if os.environ.get("ATLAS_TUI") == "1" or "--tui" in argv:
```

- [ ] **Step 3: hermes_cli/main.py — _launch_tui env var sets**

In the `_launch_tui()` function (around lines 1490-1611), find every `env["HERMES_TUI_..."]` or `os.environ["HERMES_TUI_..."]` set and rename to `ATLAS_TUI_*`. Also rename `HERMES_PYTHON` → `ATLAS_PYTHON`.

The key lines to change are where `_launch_tui()` constructs the `env` dict that it passes to `subprocess.call()`. Every `HERMES_*` key in that dict becomes `ATLAS_*`.

- [ ] **Step 4: hermes_cli/main.py — temp file prefix**

Find (around line 1514):
```python
prefix="hermes-tui-active-session-"
```
replace with:
```python
prefix="atlas-tui-active-session-"
```

- [ ] **Step 5: hermes_cli/main.py — HERMES_HOME resolution**

Find (around line 1298):
```python
HERMES_HOME = os.environ.get("HERMES_HOME") or str(Path.home() / ".hermes")
```

This is used by the entire CLI, not just TUI. For this phase, add an ATLAS_HOME fallback:
```python
HERMES_HOME = os.environ.get("ATLAS_HOME") or os.environ.get("HERMES_HOME") or str(Path.home() / ".hermes")
```

This makes the TUI work with `ATLAS_HOME` while not breaking the rest of the foundation CLI that still reads `HERMES_HOME`.

- [ ] **Step 6: Verify TUI launches**

```bash
cd services/agent-runtime && ../../.venv/Scripts/python.exe -m atlas_runtime.cli.tui
```

Expected: TUI boots, displays "ATLAS" branding, no errors. (May need to Ctrl+C to exit.)

- [ ] **Step 7: Commit**

```bash
git add services/agent-runtime/atlas_runtime/cli/tui.py foundation/atlas-hermes/hermes_cli/main.py
git commit -m "feat(tui): rename Python launcher env vars HERMES → ATLAS"
```

---

## Task 6: Tests + Final Verification (Wave 6)

**Covers:** [S6]

**Files:**
- Modify: `foundation/atlas-hermes/ui-tui/src/__tests__/` (test fixtures)

- [ ] **Step 1: Update test fixtures**

```bash
cd foundation/atlas-hermes/ui-tui && grep -rn "hermes\|Hermes\|HERMES" src/__tests__/ --include="*.ts" --include="*.tsx"
```

For each match in test files, update the expected strings to match the new ATLAS branding. Tests that assert `'Hermes Agent'` should assert `'ATLAS'`. Tests that assert `HERMES_TUI_*` should assert `ATLAS_TUI_*`.

- [ ] **Step 2: Run TUI test suite**

```bash
cd foundation/atlas-hermes/ui-tui && npm test
```

Expected: all tests pass (or only pre-existing failures unrelated to branding).

- [ ] **Step 3: Final grep audit**

```bash
cd foundation/atlas-hermes/ui-tui && grep -rn "hermes\|Hermes\|HERMES" src/ --include="*.ts" --include="*.tsx" | grep -v node_modules | grep -v __tests__ | grep -v "// " | grep -v "/* "
```

Remaining matches should be:
- Code comments (acceptable)
- Import paths that reference the foundation directory name (acceptable — that's the 10.0.7 full de-brand scope)

No user-facing strings, env vars, or config paths should reference hermes.

- [ ] **Step 4: Full build verification**

```bash
cd foundation/atlas-hermes/ui-tui && npm run check && npm run build
```

Expected: green.

- [ ] **Step 5: Commit**

```bash
git add foundation/atlas-hermes/ui-tui/
git commit -m "test(tui): update test fixtures for ATLAS branding"
```

- [ ] **Step 6: Push**

```bash
git push origin main
```
