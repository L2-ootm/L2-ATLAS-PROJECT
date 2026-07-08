# Contributing to ATLAS

Thank you for your interest in contributing to ATLAS.

## License & Contributor License Agreement (CLA)

ATLAS is licensed under the MIT License. Every contribution is subject to the
CLA in [`CLA.md`](CLA.md): opening a pull request constitutes agreement to its
terms. A CLA check (CLA Assistant, `.github/workflows/cla.yml`) runs on every
pull request and verifies the signer has agreed.

> **Maintainer note — CLA signature persistence.** The CLA workflow needs a
> `PERSONAL_ACCESS_TOKEN` repository secret (fine-grained PAT, `contents:write`)
> so the bot can commit signatures to `cla-signatures.json`. Until that secret
> exists, only the `GITHUB_TOKEN` fallback runs and signatures cannot be
> persisted. If you maintain this repo, add the secret or the CLA status will
> not record agreements.

## Development Setup

1. Clone the repository: `git clone https://github.com/L2-ootm/L2-ATLAS-PROJECT.git && cd L2-ATLAS-PROJECT`
2. Set up the Python environment and CLI shim:
   - Windows: `.\scripts\install-atlas-cli.ps1`
   - POSIX: `./scripts/setup.sh`
3. Install runtime dev dependencies: `pip install -e "services/agent-runtime[dev]"`
4. (Web cockpit) `cd services/web-ui-react && npm install`
5. (Terminal) `cd services/atlas-terminal && bun install`

## Test & Build Matrix

Run these before opening a pull request:

| Layer | Command | From |
|---|---|---|
| Python runtime | `python -m pytest services/agent-runtime/tests/ -q` | repo root (`.venv`) |
| Schemas | `python -m pytest packages/atlas-core/tests/ -q` | repo root (`.venv`) |
| Rust gateway | `cargo test -p atlas-gateway` | `native/atlas-core-rs/` |
| Web cockpit | `npm run lint && npm run build` | `services/web-ui-react/` |
| Terminal | `bun test && bunx tsc --noEmit` | `services/atlas-terminal/` |
| CLI installer | `cd packages/atlas-cli && npm test` | `packages/atlas-cli/` |

> **Known CI gap:** the `atlas-cli` installer test currently fails on Windows
> because its tar extraction shells out to the system `tar` with native paths.
> See `.debug/` for the defect report. Do not assume `npm test` is green there
> until that is fixed; the non-manifest install path passes.

## Architecture

ATLAS evolves the MIT-licensed Hermes Agent foundation (vendored at
`foundation/atlas-hermes/`) into an ATLAS-branded harness and layers mission
control, audit, policy, wiki, memory, router, gateway, and cockpit around it.

- **Foundation** (`foundation/atlas-hermes/`) — vendored Hermes; not modified directly (D-001)
- **Runtime** (`services/agent-runtime/`) — ATLAS agent, CLI, services, policies
- **Gateway** (`native/atlas-core-rs/`) — Rust REST gateway (read-only; writes dispatch via the `atlas` CLI)
- **Cockpit** (`services/web-ui-react/`) — React operator dashboard
- **Schemas** (`packages/atlas-core/`) — Pydantic v2 frozen domain models (contract source of truth)
- **Terminal** (`services/atlas-terminal/`) — Atlas-native terminal surface (ATLAS authority; donor presentation only)

See `ARCHITECTURE.md` for the full system overview and `ATTRIBUTION.md` /
`THIRD_PARTY_LICENSES.md` for provenance.

## Key Decisions

- **D-001:** No foundation edits. Extensions through plugins, CLI dispatch, or sidecars.
- **D-022:** Rust-first for new infrastructure; Python for adapters only.
- **D-012 / D-013:** Pydantic v2 models are frozen and JSON-serializable; the schema is the contract.
- **Audit-first:** every mutation flows through one CLI contract and emits an `audit_event`.

## Pull Requests

1. Fork the repository and create a feature branch off `main`.
2. Make your change with tests that cover the new behavior.
3. Ensure the relevant rows of the Test & Build Matrix pass.
4. Keep changes focused; one logical change per PR.
5. Submit the PR with a clear description (what / why / verification).
6. The CLA check must pass (sign via the PR comment prompt if asked).

## Code Style

- Python: type hints, `pathlib` over `os.path`, follow existing patterns; `ruff` is the linter.
- Rust: follow existing patterns in `atlas-gateway`; `cargo fmt` + `cargo clippy` clean.
- TypeScript / React: follow `services/web-ui-react/` and `services/atlas-terminal/`; ESLint zero-warning.
- No comments unless asked; no emojis in code.

## Good First Issues

New here? Look for issues labeled
[`good first issue`](https://github.com/L2-ootm/L2-ATLAS-PROJECT/labels/good%20first%20issue).
The label scheme lives in `.github/labels.yml` (maintainers sync it with a label-sync tool).

## Reporting Security Issues

Do **not** open a public issue for security vulnerabilities. See `SECURITY.md`
for the disclosure process.
