# ATLAS AI Router Connector Strategy

**Date:** 2026-06-08
**Phase:** 4.5 — Native Cockpit Pillar Consolidation (extended)
**Status:** Accepted direction — implementation deferred to Phase 7 (API Gateway)
**Decision record:** `docs/decisions/D-017-ai-router-connector-strategy.md`

---

## Architecture

```
ATLAS model policy
      │
      ▼
atlas_core.model_router.select(task_class, budget_tier, policy_labels)
      │
      ├─► Hermes ProviderTransport (existing transports: anthropic, codex, bedrock, custom)
      │         │
      │         └─► Direct provider API
      │
      └─► FreeLLMAPI sidecar (http://127.0.0.1:PORT/v1)  [free-tier-ok tasks only]
                │
                └─► Provider catalog: Groq, Cerebras, Google, OpenRouter, Mistral, etc.
                                      Kilo keyless, OpenCode Zen (when configured)
```

ATLAS owns the routing decision. Hermes transports own the data path. FreeLLMAPI is a sidecar, not a core dependency.

---

## Model Registry (`atlas_core.model_registry`)

A queryable, structured registry of all available models. Populated from multiple discovery sources.

### Registry Entry Schema

```python
@dataclass
class ModelEntry:
    id: str                        # canonical model id, e.g. "meta-llama/llama-4-scout-17b-16e-instruct"
    display_name: str
    provider: str                  # "groq", "anthropic", "openai", "freellmapi", "local", etc.
    source: ModelSource            # CONFIG | DISCOVERED_FREELLMAPI | DISCOVERED_CODEX | DISCOVERED_KILO | LOCAL
    api_mode: str                  # "chat_completions" | "anthropic_messages" | "codex" | etc.
    base_url: str | None           # set for custom/sidecar providers
    policy_labels: list[PolicyLabel]  # see Policy Labels section
    context_length: int | None
    supports_tools: bool
    supports_vision: bool
    supports_streaming: bool
    verified_at: datetime | None   # last time this model was successfully used
    health: ModelHealth            # HEALTHY | DEGRADED | UNKNOWN | BLOCKED
```

### Discovery Sources

| Source | Population method | Trust level |
|--------|------------------|-------------|
| `CONFIG` | Statically configured in ATLAS config file | Trusted |
| `DISCOVERED_FREELLMAPI` | `/v1/models` from FreeLLMAPI sidecar on startup and refresh | Untrusted until policy-labeled |
| `DISCOVERED_CODEX` | Codex/OpenCode model catalog (if Codex OAuth present in credential pool) | Untrusted until policy-labeled |
| `DISCOVERED_KILO` | Kilo catalog (if Kilo key present; keyless for free-tier) | Untrusted until policy-labeled |
| `LOCAL` | Local models via Ollama or llama.cpp compatible endpoint | Trusted (local) |

Discovered models are treated as `health: UNKNOWN` and policy_labels `[experimental]` until manually promoted by the operator or validated by a benchmark run.

---

## `/v1/models` Discovery

### Startup refresh

On ATLAS runtime startup:
1. Check if FreeLLMAPI sidecar is reachable (`GET /v1/models` with timeout 2s).
2. If reachable: fetch model list, merge into registry as `DISCOVERED_FREELLMAPI`.
3. For each configured authenticated provider (from credential pool): query catalog if API supports it.
4. Write merged registry to `~/.hermes/profiles/<workspace>/atlas_model_registry.json` (local cache).
5. Emit AuditEvent of kind `model_registry_refresh` with count and source summary.

### Periodic refresh

Default: every 6 hours during active ATLAS runtime session.

Configurable: `model_registry.refresh_interval_seconds`.

### Manual refresh command

```text
atlas models refresh
```

Triggers immediate re-discovery from all sources. Emits AuditEvent.

### Cache behavior

If discovery fails (sidecar down, no network), the registry falls back to the local cache. Cached entries are served with `health: UNKNOWN` if not validated recently. CONFIG entries are always served regardless of sidecar state.

---

## `/v1/chat/completions` Routing

### Task class routing

ATLAS routes by task class, not by hardcoded model name. Task classes are defined per mission/run type.

| Task class | Default policy | Allowed providers | Forbidden |
|-----------|---------------|------------------|----------|
| `classification` | free-tier-ok | FreeLLMAPI, any | — |
| `summarization` | free-tier-ok | FreeLLMAPI, any | — |
| `draft_generation` | free-tier-ok | FreeLLMAPI, any | — |
| `background_exploration` | free-tier-ok | FreeLLMAPI, any | — |
| `embeddings_experiment` | free-tier-ok | FreeLLMAPI, any | — |
| `wiki_lint` | paid-ok | Configured providers | no-sensitive-data (check content) |
| `mission_planning` | paid-ok, trusted-provider | Configured trusted providers | keyless, experimental |
| `code_generation` | paid-ok, trusted-provider | Configured trusted providers | keyless, experimental |
| `security_analysis` | trusted-provider, no-sensitive-data guard | Configured trusted providers | freellmapi, keyless, local-only |
| `subagent_low` | free-tier-ok | FreeLLMAPI, any | — |
| `subagent_high` | paid-ok, trusted-provider | Configured trusted providers | keyless, experimental |

### Routing algorithm

```python
def select(task_class: str, budget_tier: str, required_labels: list[PolicyLabel]) -> ModelEntry:
    candidates = registry.query(
        policy_labels_include_all=required_labels,
        health=HEALTHY,
    )
    if not candidates:
        candidates = registry.query(policy_labels_include_all=required_labels, health=[HEALTHY, UNKNOWN])
    if not candidates:
        raise NoEligibleModelError(task_class, required_labels)
    # Prefer: CONFIG > DISCOVERED (validated) > DISCOVERED (unvalidated)
    # Within same trust: prefer lower latency (verified_at benchmark result)
    return rank_and_select(candidates, budget_tier)
```

---

## Provider Health Checks

### Liveness probe

Before routing to any provider endpoint, the router checks liveness:

- FreeLLMAPI sidecar: `GET /v1/models` (loopback, 2s timeout).
- Custom endpoints: `GET /v1/models` or a cheap test call (configurable).
- Known direct providers (Anthropic, OpenAI): assumed healthy if credential present; verified on first real call.

### Health tracking

After each routed call:
- Success → `health: HEALTHY`, update `verified_at`.
- 429 (rate limit) → `health: DEGRADED`, exponential backoff.
- 5xx / timeout → `health: DEGRADED` for 60s, then retry.
- 401/403 → `health: BLOCKED`, emit alert AuditEvent, remove from routing until credential is refreshed.

---

## Provider Capability Tags

Tags attached to each `ModelEntry` from discovery metadata and manual classification.

| Tag | Meaning |
|-----|---------|
| `free-tier-ok` | Safe to use for non-sensitive, low-stakes tasks. Cost is zero or negligible. |
| `paid-ok` | Requires payment; operator has configured billing credentials. |
| `local-only` | Model runs locally (Ollama, llama.cpp). No data leaves the machine. |
| `trusted-provider` | Provider has enterprise ToS; data is not used for training by default. |
| `experimental` | Model is newly discovered or not benchmarked. Use with caution. |
| `no-sensitive-data` | Operator-configured restriction: do not route sensitive content here. |
| `vision` | Model supports image input. |
| `tools` | Model reliably supports tool calling. |
| `high-context` | Model supports ≥ 128K context. |

---

## Local Model Catalog Cache

Path: `~/.hermes/profiles/<workspace>/atlas_model_registry.json`

Format: JSON array of `ModelEntry` objects.

Cache is written after every successful discovery refresh. On startup, the cache is loaded before discovery runs so the cockpit can show models immediately.

Cache TTL: 24 hours. Entries older than TTL are shown as `health: UNKNOWN` until refreshed.

---

## Refresh Triggers

| Event | Action |
|-------|--------|
| ATLAS runtime startup | Full discovery refresh |
| `atlas models refresh` command | Full discovery refresh |
| `atlas provider-gateway start` | FreeLLMAPI discovery refresh |
| Provider credential added/removed | Partial refresh for that provider |
| Periodic (every 6h by default) | Full discovery refresh |
| Model returns 401/403 | Mark `health: BLOCKED`, emit AuditEvent |

---

## Model Provenance

Each `ModelEntry` records its discovery provenance:

```json
{
  "id": "meta-llama/llama-4-scout-17b-16e-instruct",
  "provider": "groq",
  "source": "DISCOVERED_FREELLMAPI",
  "discovered_at": "2026-06-08T00:00:00Z",
  "discovered_from": "http://127.0.0.1:3001/v1/models",
  "promoted_at": null,
  "promoted_by": null
}
```

Provenance is included in AuditEvents for every routed call. This allows the operator to trace: "run X used model Y, which was discovered from FreeLLMAPI sidecar on date Z."

---

## Policy Labels in Routing

Policy labels are enforced before any model is selected. The check sequence:

1. Task class → determine `required_labels` (from task class routing table).
2. Fetch candidates with all `required_labels` present.
3. Apply operator allow/deny list (see section below).
4. Apply content policy if `no-sensitive-data` label is present (detect PII/secrets in prompt before sending).
5. Select from remaining candidates.

If no candidates pass, routing fails with a typed error: `NoEligibleModelError(task_class, labels, reason)`. The mission/run is not started.

---

## Routing by Task Class, Not Hardcoded Model Names

ATLAS configuration does not hardcode model names in mission definitions. Missions declare task classes:

```python
@dataclass
class MissionPlan:
    planning_task_class: str = "mission_planning"  # policy: paid-ok, trusted-provider
    execution_task_class: str = "code_generation"  # policy: paid-ok, trusted-provider
    review_task_class: str = "summarization"        # policy: free-tier-ok
    embedding_task_class: str = "embeddings_experiment"  # policy: free-tier-ok
```

The router selects the best available model for each class at execution time. When a new model is discovered and promoted, it can automatically be used without changing mission definitions.

---

## Provider and Model Allow/Deny Controls

Operator-controlled via ATLAS config:

```toml
[model_registry]
allow_providers = ["anthropic", "openai", "groq", "freellmapi"]
deny_providers = []
deny_models = ["*:free"]       # deny all models with :free suffix (override with explicit allow)
allow_models = ["stepfun/step-3.7-flash:free"]  # explicit allow overrides deny pattern
experimental_allowed = false   # do not auto-select experimental models
```

Allow/deny rules are checked before routing. Denied models are not selected even if they match the task class.

---

## Audit-Event Metadata for Selected Provider/Model

Every routed call emits an AuditEvent of kind `llm_call` (existing Phase 4 kind) with extended payload:

```json
{
  "kind": "llm_call",
  "run_id": "...",
  "payload": {
    "model_id": "meta-llama/llama-4-scout-17b-16e-instruct",
    "provider": "groq",
    "source": "DISCOVERED_FREELLMAPI",
    "task_class": "summarization",
    "policy_labels": ["free-tier-ok"],
    "routed_via": "freellmapi_sidecar",
    "routed_via_metadata": {"platform": "groq", "model": "meta-llama/llama-4-scout-17b-16e-instruct"},
    "prompt_tokens": 245,
    "completion_tokens": 89,
    "latency_ms": 721,
    "health_at_call": "HEALTHY",
    "fallback_attempts": 0
  }
}
```

Fields `routed_via` and `routed_via_metadata` are populated from the `_routed_via` / `X-Routed-Via` metadata returned by FreeLLMAPI.

---

## Codex / OpenCode / OAuth Model Discovery

### Current state

Hermes supports Codex OAuth device_code flow (`agent/transports/codex.py`). When the operator runs `hermes auth add codex` (or ATLAS equivalent), a Codex credential is stored in the pool.

OpenCode Zen (the OpenCode Zen provider) is a known FreeLLMAPI provider but requires explicit API key configuration. As of 2026-06-07, OpenCode Zen was not configured in the local FreeLLMAPI instance.

Kilo keyless works: sentinel key added, `stepfun/step-3.7-flash:free` returned `ATLAS_REAL_SMOKE_OK`.

### Discovery capability

If Codex/OpenCode is authenticated, ATLAS can:
1. Query the authenticated provider's model list (if the API exposes `/v1/models` with the OAuth token).
2. Merge discovered models into the ATLAS registry with source `DISCOVERED_CODEX`.
3. Tag them as `trusted-provider` if ToS allows (Codex under Microsoft enterprise agreement) or `experimental` if keyless/free.

### Merged catalog flow

```
Credential pool load
    │
    ├─► CONFIG models (always present)
    ├─► FreeLLMAPI /v1/models (if sidecar running)
    ├─► Codex /v1/models (if codex OAuth present)
    ├─► Kilo /v1/models (if kilo key/sentinel present)
    └─► Ollama /api/tags → mapped to /v1/models format (if local endpoint configured)
         │
         ▼
    atlas_core.model_registry (merged, deduplicated, labeled)
```

Models discovered from multiple sources are merged by canonical ID. The highest-trust source wins on policy labels.

---

## Benchmark Results Reference

From `docs/research/FREELLMAPI_MODEL_BENCHMARK_2026-06-07.md` (as of 2026-06-07, local environment):

| Use case | Recommended model | Provider | Avg latency |
|----------|------------------|----------|------------|
| General free-tier (best quality) | `meta-llama/llama-4-scout-17b-16e-instruct` | Groq | ~721ms |
| General free-tier (fastest) | `llama-3.3-70b-versatile` | Groq | ~250ms |
| Stable free fallback | `gemini-2.5-flash-lite` | Google | ~650ms |
| Keyless external | `stepfun/step-3.7-flash:free` | Kilo | variable |

These benchmarks are environment-specific and time-sensitive. They inform initial model registry defaults, not permanent decisions. The router will update performance metadata from live call results.

---

## Implementation Phases

| Phase | Deliverable |
|-------|------------|
| Phase 4.5 (this doc) | Architecture strategy and decision record. No code. |
| Phase 5 adjunct (already accepted, D-015) | FreeLLMAPI sidecar health probe + ATLAS config fields + routing stub |
| Phase 6 | Wiki task classes use model registry for embedding/lint routing |
| Phase 7 | `GET /models` and `GET /providers/status` API endpoints. Registry exposed to cockpit. |
| Phase 8 | Cockpit provider/model settings surface. Manual refresh. Allow/deny controls. Audit visibility. |
| v2.0 | Benchmark-driven auto-promotion of experimental models. Multi-workspace model policies. |

---

## Non-Negotiables

- ATLAS owns routing decisions. FreeLLMAPI is a sidecar, not an authority.
- Credentials never appear in AuditEvent payloads. Log model and provider metadata only.
- Discovered models are `experimental` until the operator explicitly promotes them.
- Free-tier / keyless providers are `no-sensitive-data` by default.
- If the sidecar is down, ATLAS falls back to CONFIG models. Routing does not fail the runtime.
- Every routed LLM call emits an AuditEvent with full model/provider/task-class metadata.
