# D-014 — Optional Local Semantic Retrieval Spike with turbovec

Date: 2026-06-06

## Status

Accepted for spike. Not accepted for core adoption yet.

## Context

L2 ATLAS needs a local knowledge runtime that can retrieve relevant project, mission, wiki, and audit context without depending on a managed vector database. The current direction already favors SQLite/WAL/FTS5/sqlite-vec for MVP storage, and the LLM Wiki is first-class. Dense retrieval may still be valuable if it stays local, auditable, compressed, and policy-filterable.

`turbovec` is a MIT-licensed Rust/Python vector index that offers compressed local vector search, stable external IDs through `IdMapIndex`, persistence through `.tvim`, and allowlist-filtered search.

## Decision

Evaluate `turbovec` as an optional compressed vector index behind an ATLAS retrieval adapter.

The first spike must use:

- SQLite for metadata, chunk text, filters, and source citations;
- `turbovec.IdMapIndex` only for compressed vector search;
- manifest validation for embedding model, dimension, bit width, and source roots;
- safe fallback to SQLite FTS/file search when the vector index is missing, stale, or corrupt.

## Consequences

- ATLAS may gain a compact local semantic memory layer.
- ATLAS must not spread direct `turbovec` imports across runtime code.
- The dependency remains optional until benchmarked against real ATLAS data.
- The retrieval layer must enforce policy filters before returning results.

## Non-goals

- Do not replace LLM Wiki with RAG.
- Do not replace SQLite metadata with a vector-only store.
- Do not index secrets, raw auth files, session DBs, or `_EXTERNAL_REPOS`.
- Do not core-adopt while the package is still only spike-validated.

## Reference

See `docs/research/2026-06-06_TURBOVEC_LOCAL_RETRIEVAL_SPIKE.md`.
