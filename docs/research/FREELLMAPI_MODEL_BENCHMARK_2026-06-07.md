# FreeLLMAPI Model Benchmark — 2026-06-07

**Environment:** local FreeLLMAPI at `http://127.0.0.1:3001/v1`  
**Configured healthy providers detected:** Groq, Cerebras, Google, OpenRouter, Mistral, Cloudflare, HuggingFace  
**Secret handling:** unified API key was read locally from SQLite for testing but is not written here.

## Scripts

- Broad benchmark: `scripts/freellmapi_model_benchmark.py`
- Top-candidate benchmark: `scripts/freellmapi_top_model_benchmark.py`
- Raw broad results: `docs/research/FREELLMAPI_MODEL_BENCHMARK_2026-06-07.json`
- Raw top results: `docs/research/FREELLMAPI_TOP_MODEL_BENCHMARK_2026-06-07.json`

## Summary Verdict

Best model under current local conditions:

```text
meta-llama/llama-4-scout-17b-16e-instruct
platform: groq
```

Why:

- passed all 3 top-candidate tests;
- routed cleanly through Groq;
- average latency around `721ms`;
- obeyed strict exact output;
- returned valid compact JSON;
- handled the code-generation microtask.

Best fast/default general model:

```text
llama-3.3-70b-versatile
platform: groq
```

Why:

- passed broad benchmark perfectly;
- extremely fast: around `250ms` average in the broad test;
- strong for general short tasks;
- only lost points in the stricter top benchmark because it wrapped JSON/code in markdown fences, not because the semantic answer was wrong.

Best stable fallback:

```text
gemini-2.5-flash-lite
platform: google
```

Why:

- passed broad benchmark perfectly;
- stable routing directly to Google;
- around `650ms` broad average and `527ms` top average;
- good choice when Groq is rate-limited.

Best free/keyless/free-tier external fallback:

```text
openai/gpt-oss-120b:free
platform: openrouter
```

Why:

- passed all 3 stricter top-candidate tests;
- slower, around `1957ms` average;
- useful as a cost-free fallback but not the fastest lane.

## Broad Benchmark Top 10

| Rank | Requested Model | Routed Via | Pass | OK | Avg Latency |
|---:|---|---|---:|---:|---:|
| 1 | `llama-3.3-70b-versatile` | Groq / `llama-3.3-70b-versatile` | 2/2 | 2/2 | 250ms |
| 2 | `meta-llama/llama-4-scout-17b-16e-instruct` | Groq / `meta-llama/llama-4-scout-17b-16e-instruct` | 2/2 | 2/2 | 307ms |
| 3 | `codestral-latest` | Mistral / `codestral-latest` | 2/2 | 2/2 | 375ms |
| 4 | `mistral-medium-latest` | Mistral / `mistral-medium-latest` | 2/2 | 2/2 | 416ms |
| 5 | `@cf/meta/llama-3.3-70b-instruct-fp8-fast` | Cloudflare / same | 2/2 | 2/2 | 422ms |
| 6 | `mistral-large-latest` | Mistral / `mistral-large-latest` | 2/2 | 2/2 | 631ms |
| 7 | `gemini-2.5-flash-lite` | Google / `gemini-2.5-flash-lite` | 2/2 | 2/2 | 650ms |
| 8 | `Qwen/Qwen3-Coder-Next` | HuggingFace / `Qwen/Qwen3-Coder-Next` | 2/2 | 2/2 | 1169ms |
| 9 | `groq/compound-mini` | routed fallback mixed | 2/2 | 2/2 | 1680ms |
| 10 | `openai/gpt-oss-120b:free` | OpenRouter / same | 2/2 | 2/2 | 1958ms |

## Strict Top-Candidate Benchmark

Tests:

1. strict exact output;
2. compact JSON only;
3. Python function microtask.

| Rank | Requested Model | Routed Via | Pass | OK | Avg Latency | Notes |
|---:|---|---|---:|---:|---:|---|
| 1 | `meta-llama/llama-4-scout-17b-16e-instruct` | Groq | 3/3 | 3/3 | 721ms | Best overall current pick |
| 2 | `openai/gpt-oss-120b:free` | OpenRouter | 3/3 | 3/3 | 1957ms | Best free/fallback strict compliance |
| 3 | `llama-3.3-70b-versatile` | Groq | 2/3 | 3/3 | 303ms | Fastest strong general model; JSON wrapped in markdown fence |
| 4 | `gemini-2.5-flash-lite` | Google | 2/3 | 3/3 | 527ms | Stable, fast fallback; JSON wrapped in markdown fence |
| 5 | `@cf/meta/llama-3.3-70b-instruct-fp8-fast` | Cloudflare | 2/3 | 3/3 | 730ms | Useful Cloudflare fallback |
| 6 | `mistral-medium-latest` | Mistral/mixed fallback | 2/3 | 3/3 | 800ms | Good, but less strict-format reliable |
| 7 | `auto` | mixed Cerebras/HF | 2/3 | 3/3 | 1039ms | Works, but routed to models that sometimes expose reasoning/prose |
| 8 | `mistral-large-latest` | Mistral/mixed fallback | 2/3 | 3/3 | 1325ms | Solid but slower and mixed fallback |
| 9 | `codestral-latest` | Mistral/Cerebras fallback | 1/3 | 3/3 | 456ms | Good for code, but fallback routing caused instruction leakage/prose |

## Current Routing Recommendation

For Hermes/ATLAS testing, use explicit model routing instead of `auto` first:

```text
Primary:   meta-llama/llama-4-scout-17b-16e-instruct
Fast lane: llama-3.3-70b-versatile
Fallback:  gemini-2.5-flash-lite
Free lane: openai/gpt-oss-120b:free
```

Do not rely on `auto` for strict production-style output yet. In this benchmark `auto` routed into Cerebras/HuggingFace models that sometimes emitted reasoning/prose despite strict instructions.

## Practical Presets

### General assistant / ATLAS low-risk agent

```text
model: meta-llama/llama-4-scout-17b-16e-instruct
```

### Very fast classification/summarization

```text
model: llama-3.3-70b-versatile
```

### Budget/free fallback

```text
model: openai/gpt-oss-120b:free
```

### Stable Google fallback

```text
model: gemini-2.5-flash-lite
```

## Caveats

- These results are a snapshot of current rate limits, provider availability, and FreeLLMAPI routing behavior.
- Some requested models were routed to fallback models; the `routed_via` field is more authoritative than the requested model name.
- Some models produced semantically correct answers wrapped in markdown fences; this is acceptable for chat, bad for strict machine parsing.
- For private L2/client material, use trusted providers only. Do not send sensitive material through keyless/free routes.
