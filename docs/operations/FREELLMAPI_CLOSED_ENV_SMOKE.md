# FreeLLMAPI Closed-Environment Smoke Test

This folder contains a safe local smoke test for FreeLLMAPI that uses **no real provider keys** and makes **no external LLM calls**.

## Files

- `freellmapi_closed_env_smoke.py` — starts a mock OpenAI-compatible provider, starts FreeLLMAPI, registers the mock as a custom provider, and sends a `/v1/chat/completions` request with `model=auto`.
- `run_freellmapi_closed_env_smoke.bat` — Windows convenience launcher.

## Prerequisites

FreeLLMAPI must already be cloned and built. Current expected path:

```text
C:\Users\Davi\AppData\Local\Temp\freellmapi
```

Build commands used during intake:

```bash
cd C:/Users/Davi/AppData/Local/Temp/freellmapi
npm install --ignore-scripts
npm rebuild better-sqlite3
npm run build
```

## Run

From the ATLAS repo root:

```bash
python scripts/freellmapi_closed_env_smoke.py --freellmapi C:/Users/Davi/AppData/Local/Temp/freellmapi
```

Or double-click:

```text
scripts\run_freellmapi_closed_env_smoke.bat
```

## Expected PASS signal

```text
PASS: FreeLLMAPI routed model=auto through the local mock custom provider.
```

The response should include:

```json
"_routed_via": {
  "platform": "custom",
  "model": "mock-free-model"
}
```

## What this proves

- FreeLLMAPI server can boot locally.
- First-run dashboard auth setup works.
- Custom OpenAI-compatible provider registration works.
- `/v1/models` works with the unified API key.
- `/v1/chat/completions` with `model=auto` routes through a configured provider.
- The sidecar architecture is viable without using real upstream provider keys.

## What this does not prove

- Real free-tier provider availability.
- Provider ToS acceptability.
- Long-running quota behavior.
- Desktop Electron build quality on Windows.
