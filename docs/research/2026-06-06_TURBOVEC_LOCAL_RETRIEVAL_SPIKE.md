# turbovec Local Retrieval Spike — ATLAS Research Note

Date: 2026-06-06  
Source repo: https://github.com/RyanCodrai/turbovec  
Local audit clone: `_EXTERNAL_REPOS/turbovec`  
Inspected snapshot: `efe29a1` — `2026-05-30 Release: turbovec 0.7.0 (Python) + 0.8.0 (Rust crate) (#84)`

## Decision posture

`turbovec` is approved for a **controlled ATLAS retrieval spike**, not core adoption.

It should be evaluated as an optional compressed local vector index for ATLAS knowledge/runtime retrieval. The first integration must stay behind an adapter so ATLAS can fall back to SQLite FTS, file search, or another vector backend if needed.

## What turbovec is

`turbovec` is a Rust vector-search index with Python bindings built around TurboQuant-style vector quantization.

Relevant repository facts from the inspected snapshot:

- License: MIT.
- Python package: `turbovec`.
- Python package version: `0.7.0`.
- Rust crate version: `0.8.0` per release commit.
- Python requirement: `>=3.9`.
- Python dependency: `numpy>=1.20`.
- Build backend: `maturin`.
- Development classifier: `Alpha`.
- Index types:
  - `TurboQuantIndex` — positional IDs.
  - `IdMapIndex` — stable external `uint64` IDs.
- Persistence formats:
  - `.tv` for positional index.
  - `.tvim` for stable-ID index.
- Optional framework integrations:
  - LangChain.
  - LlamaIndex.
  - Haystack.
  - Agno.

## Why it is relevant to L2 ATLAS

ATLAS needs a local knowledge runtime that compounds context without sending every lookup through a managed vector database.

`turbovec` may help with:

1. compressed semantic search over Obsidian-derived knowledge;
2. project documentation retrieval;
3. mission/run/audit artifact search;
4. local client/site research archives;
5. portable ATLAS capsule indexes;
6. filtered retrieval by project, client, mission, date, or access scope.

The high-value feature is **filtered dense search**. ATLAS can use SQLite/FTS/policy rules to produce an allowlist, then ask `turbovec` to retrieve semantic nearest neighbors inside that allowed set.

## Recommended ATLAS design

Use `turbovec` only for vector search. Keep all metadata and document text in SQLite.

```txt
ATLAS query
  -> policy/scope resolution
  -> SQLite filters and/or FTS candidate set
  -> turbovec IdMapIndex.search(query_vector, k, allowlist=candidate_ids)
  -> SQLite metadata/text fetch
  -> source-cited response or mission context packet
```

Recommended storage shape:

```txt
.atlas_state/
  retrieval/
    atlas_context.sqlite
    atlas_context.tvim
    manifest.json
```

SQLite owns:

- source path;
- source kind;
- project/client/mission scope;
- chunk text;
- chunk hash;
- file modified time;
- line offsets when available;
- embedding model;
- embedding dimension;
- tags.

`turbovec` owns:

- compressed embedding vectors;
- stable numeric IDs only.

## Preferred API surface

ATLAS code should not import `turbovec` throughout the runtime. Put it behind a retrieval adapter.

```python
class LocalSemanticIndex:
    def build(self, source_roots: list[str]) -> None: ...
    def update_changed(self, source_roots: list[str]) -> None: ...
    def search(self, query: str, *, filters: dict, k: int = 10) -> list[SearchHit]: ...
    def doctor(self) -> RetrievalHealth: ...
```

Preferred `turbovec` primitive:

```python
import numpy as np
from turbovec import IdMapIndex

index = IdMapIndex(dim=embedding_dim, bit_width=4)
index.add_with_ids(vectors, np.array(chunk_ids, dtype=np.uint64))
scores, ids = index.search(query_vectors, k=10, allowlist=allowed_ids)
index.write(".atlas_state/retrieval/atlas_context.tvim")
```

## Spike plan

### Phase A — install and smoke-test

- Install `turbovec` in an isolated project environment.
- Verify Windows wheel/import.
- Build a small synthetic index.
- Validate `IdMapIndex.add_with_ids`, `search`, `allowlist`, `remove`, `write`, and `load`.

### Phase B — index real but limited ATLAS data

Initial sources:

```txt
docs/
wiki/
.planning/
```

Do not index secrets, `.env`, raw session DBs, auth files, or `_EXTERNAL_REPOS`.

### Phase C — benchmark retrieval quality

Compare:

1. plain file search;
2. SQLite FTS/BM25;
3. `turbovec` semantic search;
4. hybrid FTS/filter + `turbovec` rerank.

Test queries:

- `Hermes foundation adapter`
- `LLM Wiki runtime schema`
- `audit artifact capture`
- `mission control state machine`
- `SQLite WAL FTS5 sqlite-vec datastore`
- `Rust native overlay decision`
- `web UI framework spike`
- `CRM pulse channels research`

### Phase D — adoption decision

Promote only if results are materially better than FTS alone and the implementation remains small.

## Adoption gates

Do not adopt into the main runtime until all are true:

- install works reliably on Davi's Windows environment;
- index build is deterministic and reproducible;
- changed/deleted files update safely;
- index and metadata can be rebuilt from source files;
- retrieval results include source citations;
- policy filters are applied before retrieval output is shown;
- missing/corrupt index falls back safely;
- no secrets or raw personal data are indexed;
- performance and index size are acceptable for a portable ATLAS profile;
- dependency remains optional until production confidence exists.

## Risks

- Alpha maturity: treat as experimental.
- Quantized vectors are approximate; do not use as the only source of truth.
- `IdMapIndex` has stable IDs but no metadata store; SQLite is mandatory.
- Empty or unknown allowlists can error; adapter must normalize this to safe empty results.
- Embedding model changes require full rebuild or strict manifest validation.
- Raw embeddings are not recoverable from compressed storage; if reranking needs raw embeddings, store them separately only after explicit justification.

## Integration recommendation

Create an ATLAS retrieval spike under a future implementation task, likely attached to the LLM Wiki runtime workstream.

Proposed artifact names:

```txt
packages/atlas-core/atlas_core/retrieval/local_semantic.py
packages/atlas-core/atlas_core/retrieval/sqlite_store.py
packages/atlas-core/tests/test_local_semantic_index.py
```

Keep it optional and adapter-bound.

## Current conclusion

`turbovec` is a credible candidate for ATLAS local semantic memory. It matches the product direction: local-first, auditable, compressed, policy-filterable, and portable. It should be researched through a spike, not merged directly into the core runtime today.
