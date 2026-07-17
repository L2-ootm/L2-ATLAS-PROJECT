<p align="center">
  <img src="brand/atlas/marks/emblem-full.png" width="180" alt="ATLAS emblem">
</p>

<h1 align="center">ATLAS</h1>

<p align="center">
  <strong>An auditable AI operator cockpit for developers and power users.</strong><br>
  One runtime for missions, agents, tools, knowledge, approvals, and operational state.
</p>

<p align="center">
  <a href="LICENSE">MIT License</a> ·
  <a href="docs/architecture/OVERVIEW.md">Architecture</a> ·
  <a href="docs/operations/INSTALL.md">Install</a> ·
  <a href="docs/known-failures.md">Known limitations</a> ·
  <a href="SECURITY.md">Security</a>
</p>

> **Private research preview.** The repository and npm package are not public yet.
> ATLAS is being hardened for its first public release; do not use the current build
> with sensitive production data.

## What ATLAS is

ATLAS turns an evolved Hermes foundation into an L2-owned operator runtime. It joins
agent execution with an audit ledger, mission and run state, approval-gated tools,
persistent knowledge, provider routing, and a WebUI cockpit. The product is designed
so every meaningful action can be traced from intent to tool call, output, and
verification.

- **Operator cockpit** — chat-first WebUI, mission control, runs, ledger, models,
  integrations, system health, and slash-command palette.
- **Auditable runtime** — structured missions/runs, tool approvals, artifacts, and
  append-oriented operational evidence.
- **Persistent knowledge** — wiki/codex ingestion, provenance, and local search.
- **Extensible modules** — bundled modules ship with releases; operator and agent
  modules live separately under `ATLAS_HOME/modules` and survive updates.
- **Native direction** — the gateway and new infrastructure are Rust-first; the
  Hermes plugin surface and LLM adapters remain Python where that boundary is useful.

## Installation

The public release will use one command:

```powershell
npm install --global @l2/atlas
```

The npm launcher installs a verified platform release, then delegates normal commands
to it. Application versions live outside the source repository and outside live
operator state. `atlas update` replaces the launcher/runtime version while preserving
the database, configuration, credentials, wiki, logs, and user modules.

The npm package is not published yet and the real platform bundle is still a release
gate. For private source testing on Windows, use the current bootstrap:

```powershell
irm https://raw.githubusercontent.com/L2-ootm/L2-ATLAS-PROJECT/main/install/install.ps1 | iex
```

Because the GitHub repository is private, that URL requires authenticated access until
the public flip. See [the installation guide](docs/operations/INSTALL.md) for source,
release, update, rollback, and clean-machine details.

## First run

```powershell
atlas doctor
atlas up
atlas
```

`atlas up` starts the local gateway and cockpit. `atlas` opens the terminal surface.
Mock Mode supports the core demo path without a provider API key.

## Update model

```text
npm launcher          npm global prefix
immutable releases    OS application-data/atlas/versions/<version>
active pointer        OS application-data/atlas/current
operator state        ~/.atlas (or ATLAS_HOME)
user modules          ~/.atlas/modules
```

Updates never target this development checkout. A failed download, checksum, or
entrypoint validation cannot activate the new version; the previous verified version
remains available to `atlas rollback`.

## Repository map

| Area | Purpose |
|---|---|
| `foundation/atlas-hermes/` | Hermes-derived ATLAS foundation and divergence record |
| `services/agent-runtime/` | Runtime orchestration and CLI |
| `native/atlas-core-rs/` | Rust gateway and native infrastructure |
| `services/web-ui-react/` | WebUI operator cockpit |
| `services/atlas-tui/` | Current Go terminal surface |
| `services/atlas-terminal/` | Next terminal surface under gated evaluation |
| `packages/atlas-cli/` | npm installer, updater, rollback, and runtime launcher |
| `modules/` | Modules bundled with ATLAS releases |
| `docs/` | Architecture, operations, decisions, verification, and release material |

## Trust and project status

ATLAS is intentionally honest about unfinished work. Public release remains blocked on
the production platform bundle, npm ownership/authentication, clean-machine
install/update/rollback UAT, and operator approval. Repository cleanup and the
configured full-history secret scan are complete. Release gates are tracked
in [`docs/release/RELEASE_CHECKLIST.md`](docs/release/RELEASE_CHECKLIST.md); internal
planning/session state is deliberately excluded from the public repository.

The foundation is vendored and evolved in place rather than treated as a black-box
dependency. Provenance and changes are documented in
[`foundation/ATTRIBUTION.md`](foundation/ATTRIBUTION.md) and
[`foundation/DIVERGENCE_LOG.md`](foundation/DIVERGENCE_LOG.md).

## Contributing

Read [CONTRIBUTING.md](CONTRIBUTING.md), the [Code of Conduct](CODE_OF_CONDUCT.md),
and [CLA.md](CLA.md) before opening a contribution. Security issues should follow the
private process in [SECURITY.md](SECURITY.md).

## License

ATLAS is available under the [MIT License](LICENSE). Third-party licenses and derived
code attribution are documented in [THIRD_PARTY_LICENSES.md](THIRD_PARTY_LICENSES.md)
and [ATTRIBUTION.md](ATTRIBUTION.md).
