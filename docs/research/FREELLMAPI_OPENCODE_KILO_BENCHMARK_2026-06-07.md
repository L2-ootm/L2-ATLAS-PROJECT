# FreeLLMAPI OpenCode Zen + Kilo Benchmark — 2026-06-07

## Context

Davi correctly pointed out that OpenCode Zen and Kilo include stronger candidate models than the earlier Groq/Llama-focused pass considered.

This benchmark specifically targeted:

### OpenCode Zen requested models

- `deepseek-v4-flash-free`
- `minimax-m3-free`
- `nemotron-3-ultra-free`
- `big-pickle`
- `nemotron-3-super-free`
- `mimo-v2.5-free`

### Kilo requested models

- `poolside/laguna-m.1:free`
- `poolside/laguna-xs.2:free`
- `nvidia/nemotron-3-super-120b-a12b:free`
- `stepfun/step-3.7-flash:free`

Script:

```text
scripts/freellmapi_opencode_kilo_benchmark.py
```

Raw result:

```text
docs/research/FREELLMAPI_OPENCODE_KILO_BENCHMARK_2026-06-07.json
```

## Important discovery

FreeLLMAPI currently has healthy keys configured for:

```text
Groq, Cerebras, Google, OpenRouter, Mistral, Cloudflare, HuggingFace
```

But **OpenCode Zen is not configured yet** in the local FreeLLMAPI database.

Detected API key rows:

```text
groq       healthy
cerebras   healthy
google     healthy
openrouter healthy
mistral    healthy
cloudflare healthy
huggingface healthy
kilo       keyless sentinel added locally during this pass
```

No `opencode` API key row exists yet.

Because of that, requested OpenCode model IDs were mostly routed to fallback providers such as Cerebras, Groq, Google, and HuggingFace. Therefore the OpenCode results below are **not proof of actual OpenCode Zen model quality yet**. They show FreeLLMAPI fallback behavior when OpenCode is absent.

## Kilo keyless setup

Kilo keyless sentinel was added locally so FreeLLMAPI can route anonymous Kilo calls. Actual Kilo routing was observed for:

```text
stepfun/step-3.7-flash:free
```

Other Kilo-looking model IDs sometimes routed through OpenRouter because FreeLLMAPI has those same free model IDs available there too.

## Benchmark results

### Actual Kilo observed

| Requested Model | Actual Route | Pass | Avg Latency | Notes |
|---|---|---:|---:|---|
| `stepfun/step-3.7-flash:free` | Kilo / `stepfun/step-3.7-flash:free` | 1/3 | 2208ms | Real Kilo route, but poor strict-instruction compliance; often emits reasoning/prose. |

### Requested OpenCode models — but fallback-routed

| Requested Model | Actual Routing | Pass | Avg Latency | Notes |
|---|---|---:|---:|---|
| `nemotron-3-ultra-free` | Groq/Cerebras fallback | 3/3 | 1688ms | Best result in this pass, but not actual OpenCode. |
| `mimo-v2.5-free` | Google/HF fallback | 2/3 | 1885ms | Not actual OpenCode. |
| `big-pickle` | Cerebras fallback | 2/3 | 5263ms | Not actual OpenCode. |
| `deepseek-v4-flash-free` | Cerebras fallback | 1/3 | 362ms | Not actual OpenCode. |
| `nemotron-3-super-free` | Cerebras/Groq/Kilo fallback | 1/3 | 3222ms | Not actual OpenCode. |
| `minimax-m3-free` | Cerebras/HF fallback | 1/3 | 5652ms | Not actual OpenCode. |

## Conclusion

Davi's correction is valid: OpenCode Zen and Kilo deserve a dedicated evaluation. The current pass proves:

1. Kilo keyless can be enabled and called.
2. `stepfun/step-3.7-flash:free` routes through Kilo.
3. OpenCode Zen was **not actually tested yet** because its API key is not configured in FreeLLMAPI.
4. FreeLLMAPI fallback routing can make a requested OpenCode/Kilo model appear to work while actually using another provider.

The earlier recommendation should be adjusted:

- `meta-llama/llama-4-scout-17b-16e-instruct` remains the best **confirmed configured-provider** model.
- OpenCode Zen cannot be ranked until an OpenCode key is configured.
- Kilo keyless is usable but current StepFun behavior is too verbose for strict structured output.

## Required next step

Configure OpenCode Zen in FreeLLMAPI:

```text
Provider: OpenCode Zen / opencode
Key source: https://opencode.ai/auth
```

Then rerun:

```bash
python scripts/freellmapi_opencode_kilo_benchmark.py
```

Only consider OpenCode results valid when `routed_via.platform` equals:

```text
opencode
```

## Operational recommendation after this pass

Until OpenCode is actually configured:

```text
Primary confirmed: meta-llama/llama-4-scout-17b-16e-instruct via Groq
Fast confirmed:    llama-3.3-70b-versatile via Groq
Stable fallback:   gemini-2.5-flash-lite via Google
Free fallback:     openai/gpt-oss-120b:free via OpenRouter
Kilo smoke only:   stepfun/step-3.7-flash:free via Kilo
```
