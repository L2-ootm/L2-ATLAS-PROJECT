# Phase 9.5 — Manual Test Guide for Davi

**Purpose:** manual acceptance checklist for ATLAS v1.0 before milestone archive or public/open-source release.

This guide is intentionally operational. Mark each test as:

- `PASS` — works as expected.
- `PARTIAL` — useful but with named issue.
- `FAIL` — blocks acceptance.
- `NOT_RUN` — explain why.

Record observations directly under each test or in the final notes section.

## 0. Pre-test setup

### Required context

- Repo: `C:\Users\Davi\Desktop\Projects\L2-ATLAS-PROJECT`
- Branch: `main`
- Expected precondition: Phase 9.5 hardening branch/worktree is current and no unrelated dirty files exist.

### Commands

```bash
cd /c/Users/Davi/Desktop/Projects/L2-ATLAS-PROJECT
git status --short -uall
git branch --show-current
git log --oneline -5
```

Expected:

- branch is `main` or a clearly named Phase 9.5 branch;
- only intentional hardening files are dirty;
- no `.env`, DB, session, cache, Playwright logs, or private files are untracked.

Result:

```txt
Status: NOT_RUN
Notes:
```

---

## 1. Start backend gateway

Use the canonical command from `docs/operations/RUNNING.md` once Phase 9.5 creates it. If that file is not created yet, this test is blocked.

Expected:

- gateway starts without traceback;
- missing `ATLAS_CLI` / `ATLAS_WIKI_DIR` produces a clear fail-fast error, not a later hidden failure;
- health endpoint responds.

Health check:

```bash
curl http://127.0.0.1:8484/health
```

Expected: healthy JSON response.

Result:

```txt
Status: NOT_RUN
Notes:
```

---

## 2. Start web cockpit

Use the canonical command from `docs/operations/RUNNING.md`.

Expected:

- web UI starts without build/runtime error;
- URL is clear, usually `http://localhost:5173`;
- no Electron dependency or native shell required for v1.0.

Result:

```txt
Status: NOT_RUN
Notes:
```

---

## 3. Browser console baseline

Open the cockpit in browser.

Check:

- browser console has no red runtime errors on initial load;
- network panel shows gateway calls to `127.0.0.1:8484`;
- no request to private/local filesystem paths;
- no broken static assets.

Result:

```txt
Status: NOT_RUN
Notes:
```

---

## 4. Gateway offline behavior

Stop the gateway while the UI is open or open UI before gateway starts.

Expected:

- UI shows clear offline/degraded state;
- no infinite crash loop;
- no blank white screen;
- retry/recovery after gateway restarts works or is clearly documented.

Result:

```txt
Status: NOT_RUN
Notes:
```

---

## 5. Mission list and empty DB

Use a fresh or test DB if Phase 9.5 provides one.

Expected:

- mission page loads on empty DB;
- empty state is understandable;
- no FK errors;
- no console errors.

Result:

```txt
Status: NOT_RUN
Notes:
```

---

## 6. Create mission

Create a mission with normal input:

```txt
Title: Manual UAT Mission
Intent: Verify the ATLAS v1.0 cockpit loop manually.
```

Expected:

- modal/form submits;
- mission appears without full page reload;
- status badge is correct;
- mission detail opens;
- audit/event trail records creation if expected by runtime.

Result:

```txt
Status: NOT_RUN
Notes:
```

---

## 7. Long input edge case

Create or edit a mission with:

- very long title;
- multi-paragraph intent;
- punctuation/unicode: `ATLAS Δ — teste çãõ 🚀`.

Expected:

- UI does not break layout;
- text is truncated/wrapped safely;
- backend returns clear validation if input is too long;
- no corrupted characters.

Result:

```txt
Status: NOT_RUN
Notes:
```

---

## 8. Launch run

From mission detail, launch a new run.

Expected:

- run row is created;
- run page opens;
- initial events appear;
- timestamps/status are coherent;
- no duplicate run starts from one click.

Double-click test:

- click launch twice quickly if safe.

Expected:

- either one run starts or duplicate behavior is clearly controlled/documented.

Result:

```txt
Status: NOT_RUN
Notes:
```

---

## 9. SSE / live events

On an active or test run page:

Expected:

- live badge or connected status appears;
- new events append without refresh;
- finished run stops live state honestly;
- reconnect/reload does not duplicate events incorrectly;
- event order is stable.

Manual reconnect:

1. Open run page.
2. Refresh browser.
3. Confirm event history reloads.
4. If active, confirm stream resumes.

Result:

```txt
Status: NOT_RUN
Notes:
```

---

## 10. Export JSONL

Use the run detail export feature.

Expected:

- JSONL downloads;
- each line is valid JSON;
- includes run/event identifiers and timestamps;
- no secrets/local private paths in exported content for the test run.

Optional validation:

```bash
python - <<'PY'
import json, pathlib
p = pathlib.Path('PATH_TO_DOWNLOADED_JSONL')
for i, line in enumerate(p.read_text(encoding='utf-8').splitlines(), 1):
    json.loads(line)
print('valid jsonl')
PY
```

Result:

```txt
Status: NOT_RUN
Notes:
```

---

## 11. Wiki browse/search/create/update

Test:

1. Open Wiki page.
2. Search an existing term.
3. Search a term that should return no results.
4. Create or update a test page if UI supports it.
5. Search the new/updated content.

Edge slugs:

```txt
manual-uat
manual uat spaces
çãõ-unicode
```

Expected:

- no crash on empty results;
- slugs normalize consistently;
- update is idempotent/retry-safe;
- wiki log/index update if expected.

Result:

```txt
Status: NOT_RUN
Notes:
```

---

## 12. Model registry page

Open model/provider page.

Expected:

- page loads if registry table exists;
- empty table degrades to `[]` / empty state, not 500;
- no mutation controls in v1.0 if out of scope;
- no provider secrets displayed.

Result:

```txt
Status: NOT_RUN
Notes:
```

---

## 13. Direct route refresh

Open each route directly in a new tab and refresh:

- `/`
- `/missions`
- `/missions/<existing-id>`
- `/runs/<existing-id>`
- `/wiki`
- `/models`

Expected:

- adapter-static fallback works;
- no 404 on valid dynamic route;
- invalid ID gives controlled error state.

Result:

```txt
Status: NOT_RUN
Notes:
```

---

## 14. Visual/product sanity

Check:

- sidebar state/collapse persists correctly;
- L2/ATLAS branding looks intentional;
- no imported-source branding leaks into product UI;
- empty/error/loading states are readable;
- narrow viewport does not destroy layout;
- no remote Google Fonts if local-first/offline claim is being tested.

Result:

```txt
Status: NOT_RUN
Notes:
```

---

## 15. Security/public-readiness spot check

In the UI and generated artifacts, verify:

- no `C:\Users\Davi` path appears;
- no `.env` value appears;
- no token/API key appears;
- no personal admissions/scholarship material appears;
- no private L2 internal docs appear in public UI.

Result:

```txt
Status: NOT_RUN
Notes:
```

---

## 16. Acceptance decision

### Summary table

| Test | Status | Blocking issue? |
|---|---|---|
| 0. Pre-test setup | NOT_RUN | TBD |
| 1. Gateway start | NOT_RUN | TBD |
| 2. Web cockpit start | NOT_RUN | TBD |
| 3. Console baseline | NOT_RUN | TBD |
| 4. Gateway offline | NOT_RUN | TBD |
| 5. Mission list / empty DB | NOT_RUN | TBD |
| 6. Create mission | NOT_RUN | TBD |
| 7. Long input | NOT_RUN | TBD |
| 8. Launch run | NOT_RUN | TBD |
| 9. SSE/live events | NOT_RUN | TBD |
| 10. Export JSONL | NOT_RUN | TBD |
| 11. Wiki | NOT_RUN | TBD |
| 12. Model registry | NOT_RUN | TBD |
| 13. Direct route refresh | NOT_RUN | TBD |
| 14. Visual/product sanity | NOT_RUN | TBD |
| 15. Security/public-readiness | NOT_RUN | TBD |

### Final verdict

Choose one:

```txt
APPROVED_FOR_V1_ARCHIVE
APPROVED_AFTER_MINOR_FIXES
NOT_APPROVED
```

Notes:

```txt

```
