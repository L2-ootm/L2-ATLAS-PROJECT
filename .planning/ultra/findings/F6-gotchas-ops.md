# F6 — FreeLLMAPI Operational Gotchas and Lessons Learned

Collected from code comments, HANDOFF.md, STATE.md, D-015, and source.

---

## 1. NODE_ENV Gotcha

`freellmapi_control.start()` must **never** force `NODE_ENV=production`. When it does, the sidecar hard-requires an `ENCRYPTION_KEY` at boot and immediately exits.

**Fix location:** `freellmapi_control.py:121-123` — sets `HOST` and `PORT` but never touches `NODE_ENV`.

> Ref: freellmapi_control.py:121-123, HANDOFF.md:633-634

---

## 2. Cleartext API Key Exposure

`freellmapi status` returns the sidecar `api_key` in cleartext via `status()["api_key"]`, exposed through `atlas freellmapi status --json` and gateway `/v1/freellmapi/status`.

**Status:** Flagged for operator review (HANDOFF.md:621) and kept as documented local-only convenience. Diverges from the masked-secret contract enforced everywhere else.

> Ref: HANDOFF.md:621, freellmapi_control.py:73-86,96

---

## 3. Sidecar DB Key Resolution Path

When `auth_mode == "freellmapi"`, the provider resolver reads the API key from FreeLLMAPI's SQLite DB, not from an env var.

**Resolution chain (config_service.py:317-323):**
1. `provider.api_key` starts with `env:` → resolve from OS env
2. If still empty AND `auth_mode == "freellmapi"` → call `freellmapi_control.get_api_key()`
3. `get_api_key()` opens `<checkout>/server/data/freeapi.db` and reads `SELECT value FROM settings WHERE key = 'unified_api_key'`

**Why:** The OMNI surface wiring strategy forbids env-var side channels — the sidecar owns its unified key.

> Ref: config_service.py:315-323, freellmapi_control.py:73-86

---

## 4. Health Check Tolerance

`freellmapi_control.health_ok()` treats **any** HTTP response — including 401 — as proof the sidecar is listening. Only connection errors return `False`.

```python
# freellmapi_control.py:61-70
except urllib.error.HTTPError:
    return True  # 401/403/etc = sidecar is up, just auth-gated
```

**`atlas doctor` uses 0.5s timeout** vs default 1.0s for dedicated status commands (doctor.py:109).

> Ref: freellmapi_control.py:61-70, doctor.py:99-114

---

## 5. `atlas up` Non-Blocking Behavior

`atlas up` starts FreeLLMAPI only after gateway+cockpit are healthy, and **never fails** when the sidecar is absent.

```python
# cli/main.py:1034-1038
if gateway_ok and cockpit_ok:
    _, freellmapi_message = freellmapi_control.start()
    typer.echo(f"freellmapi: {freellmapi_message}")
```

The return value is ignored — only the message is printed.

> Ref: cli/main.py:1019-1044

---

## 6. `atlas down` Ordering

`atlas down` stops components in reverse-dependency order: freellmapi first, gateway last.

```python
# cli/main.py:1073-1079
stop_plan = (
    ("freellmapi", freellmapi_control.stop),   # 1st
    ("cashflow",   cashflow_control.stop),      # 2nd
    ("discord",    discord_control.stop),       # 3rd
    ("cockpit",    cockpit_control.stop),       # 4th
    ("gateway",    gateway_control.stop),       # 5th
)
```

**Gotcha:** `stop()` uses `taskkill /PID /T /F` on Windows (kills process tree) but only `SIGTERM` on Unix (does not kill child processes).

> Ref: cli/main.py:1061-1089, freellmapi_control.py:151-164

---

## 7. npm Audit Advisories

6 advisories found at intake: vitest (critical, dev-only), esbuild (moderate, dev-only), drizzle-orm (**high**, production ORM but ATLAS communicates via HTTP only — contained), plus 3 moderate.

**Net assessment:** No advisory creates a direct ATLAS security risk when running as loopback-only sidecar. Full remediation required before any distribution bundling.

> Ref: FREELLMAPI_INTEGRATION_SPIKE:158-176, D-015:115

---

## 8. Free-Tier Instability

- D-015:111: "Free-tier availability is unstable. Provider ToS varies; keyless/free routes may log prompts."
- HANDOFF.md:635: "free route currently lacks tool-calling (HTTP 429 exhausted)"
- Privacy warning emitted at every first run through a free route (native.py:240-250)

**Policy:** Only for non-sensitive summarization, classification, draft generation, low-risk exploration, synthetic tests, non-private embeddings. Never for secrets, client data, production material.

> Ref: D-015:111-134, HANDOFF.md:635, native.py:240-250

---

## 9. Port 3001 Collision

Both `model_registry.DEFAULT_GATEWAY_URL` and `freellmapi_control.BASE_URL` default to `http://127.0.0.1:3001/v1`. This is **by design** — model_registry queries FreeLLMAPI's `/models` endpoint. The naming `DEFAULT_GATEWAY_URL` is misleading (refers to sidecar, not ATLAS gateway on port 8484).

> Ref: model_registry.py:33, freellmapi_control.py:21-23

---

## 10. Lessons from HANDOFF/STATE

- **2026-07-03:** NODE_ENV fix + sidecar key autowire resolved in one session (HANDOFF.md:628-635)
- **2026-07-04:** `atlas doctor` extended with sidecar probes; `atlas up` boots freellmapi as optional (HANDOFF.md:419-428)
- **Free-route lacks tool-calling:** HTTP 429 exhaustion observed; tool-capable models required for real runs (STATE.md:293)
- **`atlas doctor --json` per-key schema:** Fixed to `{"status": str, "ok": bool}` for every key including sidecar offline paths (HANDOFF.md:520-526)

---

## Current Runtime Status (2026-07-10)

- **Sidecar:** Running at `http://127.0.0.1:3001` (401 = alive, auth-gated)
- **Database:** `C:\Users\Davi\Desktop\Projects\freellmapi\server\data\freeapi.db` — has `unified_api_key`, encryption key, catalog metadata
- **Checkout:** `C:\Users\Davi\Desktop\Projects\freellmapi\` (sibling to repo)
- **Node.js:** v24.15.0 available
- **State file:** `~/.atlas/freellmapi.json` records pid 16944 + dir
