# ATLAS Limitations

ATLAS is an AI operator cockpit and agent harness in active development.
This document describes known scope boundaries and current limitations.

## What ATLAS Is Not

- **Not a production-grade multi-user system.** ATLAS is designed for a single
  operator. There is no user authentication, authorization, or tenant isolation.
- **Not a replacement for your AI provider.** ATLAS orchestrates calls to LLM
  providers (OpenRouter, Anthropic, etc.) but does not run models itself.
- **Not a sandbox.** Agent runs inherit the operator's filesystem permissions.
  The workspace boundary check is advisory, not a security boundary.
- **Not a finished product.** ATLAS is an open research preview (v0.1). APIs,
  schemas, and behavior may change between versions.

## Current Limitations

### Runtime

- Single-operator concurrency only (one `threading.Lock` + SQLite WAL).
- CLI-dispatched writes have ~50-100ms overhead per subprocess spawn.
- The native agent runtime executes Python subprocesses; there is no in-process
  execution mode yet.
- Claude Code agent runtime requires `claude-agent-sdk` to be installed separately.

### Gateway

- The Rust gateway binds to `127.0.0.1:8484` (loopback only). No external
  network exposure.
- No authentication on the HTTP API. Access control relies on loopback binding.
- SSE streaming is per-run, not per-session.

### Discord

- The vendored L2-BOT sidecar and the foundation messaging gateway cannot run
  on the same bot token simultaneously.
- Discord write operations require approval through the two-phase pipeline
  (propose → approve → execute). There is no "execute immediately" mode.
- The sidecar runs on its own Python venv, separate from the ATLAS runtime.

### Cockpit

- The React cockpit is the primary UI. The Hermes Ink TUI exists but has no
  ATLAS-specific views (mission dashboard, goal tree).
- No offline mode. The cockpit requires the Rust gateway to be running.
- The knowledge graph is a static snapshot. Runtime entity hooks are not wired.

### Data

- SQLite is the sole datastore. No replication, no backup automation.
- Semantic search (embeddings) requires `sqlite-vec` and `fastembed` to be
  installed. Without them, search degrades to FTS5 keyword matching.
- Wiki embeddings are computed on write. There is no background reindex job.
