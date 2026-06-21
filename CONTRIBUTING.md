# Contributing to ATLAS

Thank you for your interest in contributing to ATLAS.

## Development Setup

1. Clone the repository
2. Run `scripts/install-atlas-cli.ps1` (Windows) to set up the `.venv` and CLI shim
3. Install dependencies: `pip install -e "services/agent-runtime[dev]"`
4. Run tests: `python -m pytest services/agent-runtime/tests/ -q`

## Architecture

ATLAS is built on the Hermes Agent foundation (vendored at `foundation/atlas-hermes/`).
The architecture separates:

- **Foundation** (`foundation/atlas-hermes/`) — vendored Hermes code, not modified directly
- **Runtime** (`services/agent-runtime/`) — ATLAS agent, CLI, services, and policies
- **Gateway** (`native/atlas-core-rs/`) — Rust REST API gateway (read-only, CLI dispatch)
- **Cockpit** (`services/web-ui-react/`) — React operator dashboard
- **Schemas** (`packages/atlas-core/`) — Pydantic v2 domain models (source of truth)

See `ARCHITECTURE.md` for the full system overview.

## Key Decisions

- **D-001:** No foundation edits. Extensions through plugins, CLI dispatch, or sidecars.
- **D-022:** Rust-first for new infrastructure. Python for adapters only.
- **D-012:** Pydantic v2 models are the schema source of truth.
- **D-013:** All models are frozen. `model_dump()` produces JSON-safe output.

## Good First Issues

New here? Look for issues labeled
[`good first issue`](https://github.com/L2-ootm/L2-ATLAS-PROJECT/labels/good%20first%20issue) —
they are small, well-scoped, and a good entry point. The full label scheme lives in
`.github/labels.yml` (maintainers sync it with a label-sync tool).

## Pull Requests

1. Fork the repository and create a feature branch
2. Make your changes with tests
3. Ensure all tests pass: `python -m pytest services/agent-runtime/tests/ -q`
4. Ensure Rust tests pass: `cargo test -p atlas-gateway` (from `native/atlas-core-rs/`)
5. Ensure cockpit builds: `npm run build` (from `services/web-ui-react/`)
6. Submit a pull request with a clear description of the change

## Code Style

- Python: follow existing patterns, use type hints, prefer `pathlib` over `os.path`
- Rust: follow existing patterns in `atlas-gateway`
- TypeScript/React: follow existing patterns in `services/web-ui-react/`
- No comments unless asked
- No emojis in code

## License

By contributing, you agree that your contributions will be licensed under the
MIT License.
