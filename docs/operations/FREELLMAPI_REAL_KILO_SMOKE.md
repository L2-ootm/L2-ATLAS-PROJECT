# FreeLLMAPI Real-Provider Smoke Test — Kilo Keyless

This test makes a **real external API call** through FreeLLMAPI using Kilo Gateway's anonymous/keyless free route. It does not use the operator's provider keys.

## Files

- `scripts/freellmapi_real_kilo_smoke.py`
- `scripts/run_freellmapi_real_kilo_smoke.bat`

## What it does

1. Starts FreeLLMAPI locally on `127.0.0.1:3018`.
2. Captures the generated `freellmapi-...` unified API key from server stdout.
3. Creates first-run dashboard auth through `/api/auth/setup`.
4. Adds the keyless Kilo provider through `/api/keys/`.
5. Calls `/v1/models`.
6. Calls `/v1/chat/completions` using:

```json
{
  "model": "stepfun/step-3.7-flash:free",
  "messages": [{"role": "user", "content": "Reply with exactly: ATLAS_REAL_SMOKE_OK"}],
  "max_tokens": 80
}
```

## Verified result

Observed successful real call:

```text
chat status: 200
content: ATLAS_REAL_SMOKE_OK
```

Response routing metadata:

```json
"_routed_via": {
  "platform": "kilo",
  "model": "stepfun/step-3.7-flash:free"
}
```

Usage reported:

```json
{
  "prompt_tokens": 25,
  "completion_tokens": 79,
  "total_tokens": 104
}
```

## Run

```bash
python scripts/freellmapi_real_kilo_smoke.py --freellmapi <USER_HOME>/AppData/Local/Temp/freellmapi
```

Or double-click:

```text
scripts\run_freellmapi_real_kilo_smoke.bat
```

## Interpretation

This proves FreeLLMAPI can route a real provider call through a free/keyless provider from a local sidecar without adding upstream provider credentials.

## Caveats

- Kilo's free route is external and can change or rate-limit.
- Kilo prompts/outputs may be logged/trained on per upstream docs; do not send private data.
- This is acceptable for non-sensitive smoke testing and low-risk tasks only.
