# L2 ATLAS PROJECT

> **ATLAS v0.1 — Open Research Preview**

ATLAS v0.1 is an open research preview of an **auditable AI agent cockpit** for
developers and power users. It demonstrates mission control, runtime execution, live
audit streams, artifact persistence, LLM Wiki filing, integrations, and an extensible
harness built from an evolved Hermes foundation.

ATLAS is an L2-owned operator cockpit/runtime built by evolving the Hermes Agent foundation into an ATLAS-branded harness, then adding mission, audit, policy, wiki, memory, router, gateway, and cockpit layers around that evolved foundation.

**What it is not** (yet): production-ready, enterprise-ready, fully autonomous,
self-improving, secure for sensitive data, or a replacement for developers. It is an
early, honest research preview — see [`docs/known-failures.md`](docs/known-failures.md)
for documented limitations.

## Quickstart

```bash
git clone <your-fork-url> atlas && cd atlas
cp .env.example .env
./scripts/setup.sh          # or .\scripts\install-atlas-cli.ps1 on Windows
./atlas db init --demo      # optional: seed a demo mission so the cockpit isn't empty
./atlas up
./atlas doctor              # confirm db/config/gateway/cockpit/provider are all healthy
```

No provider API key required to try it — ATLAS runs in Mock Mode end-to-end
with zero credentials configured. Full walkthrough, troubleshooting, and the
optional Docker Compose path: see [`docs/INSTALL.md`](docs/INSTALL.md).

## What v0.1 ships

The full v1.0 cockpit + runtime, hardened into the v1.0.5 mass-adoption wedge:

- **Mission control & runtime** — create missions, run them through the ATLAS runtime
  (native or the operator's local Claude Code session), live SSE audit streams.
- **Audit-first** — every action is an `audit_event`; the cockpit Ledger is a cross-run
  forensic explorer.
- **Persistent knowledge** — artifacts + an LLM Wiki (Codex) with provenance and FTS5 search.
- **Extensible harness** — developer **Tool Manifest v0**: adding an integration is a YAML
  manifest + a Python adapter, gated through one policy chokepoint
  ([`docs/tools.md`](docs/tools.md)). Read-only by default; writes are approval-gated.
- **Golden workflows** — Repo Triage, Research Brief, and an approval-gated Self-Review
  ([`docs/golden-workflows.md`](docs/golden-workflows.md)), demo-stable and reproducible.
- **Cockpit** — Observatory, Missions, Runs, Ledger, Codex, Models, Integrations, System,
  built in the celestial-heraldic ATLAS design language.

Live project state: [`.planning/STATE.md`](.planning/STATE.md). Release artifacts:
[`docs/release/`](docs/release/).

## Try it (no credentials)

1. Create a mission.
2. Run it through the ATLAS runtime (Mock Mode needs zero credentials).
3. Persist run/audit/artifacts; file valuable output into the LLM Wiki.
4. Watch it stream live in the cockpit.

## Orientation

- `docs/README.md` — documentation authority order
- `docs/architecture/OVERVIEW.md` — one-page architecture
- `docs/decisions/INDEX.md` — ADR index (D-001…D-022)
- [`docs/tools.md`](docs/tools.md) — developer integrations + Tool Manifest v0 (adding a tool = manifest + adapter)
- `foundation/README.md` — vendored Hermes-derived foundation, attribution, divergences

Optional retrieval research now tracked:

- `docs/research/2026-06-06_TURBOVEC_LOCAL_RETRIEVAL_SPIKE.md` — evaluates `turbovec` as a compressed local semantic index behind SQLite metadata and ATLAS policy filters.

## Rules

- Use Hermes as the foundation codebase, vendored at `foundation/atlas-hermes/` and evolved in place (D-018). ATLAS is never a thin wrapper around, or a route through, stock Hermes.
- Raw sources are immutable.
- Every autonomous action is auditable.
- LLM Wiki compounds knowledge; RAG alone is not enough.
- Existing L2 repos are source assets, not blindly merged code.

## License

ATLAS is licensed under the [MIT License](LICENSE). Third-party dependency
licenses and required attributions are tracked in
[`THIRD_PARTY_LICENSES.md`](THIRD_PARTY_LICENSES.md); vendored/derived-code
provenance is tracked in [`ATTRIBUTION.md`](ATTRIBUTION.md).

Contributions require signing the [Contributor License Agreement](CLA.md) —
opening a pull request constitutes agreement to its terms.
