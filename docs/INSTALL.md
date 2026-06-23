# Installing ATLAS

This guide gets you from a fresh `git clone` to a running ATLAS gateway +
cockpit, with zero prior knowledge of the codebase. The native path below is
primary; Docker Compose is an optional secondary path for operators who would
rather containerize everything than install Rust/Python/Node locally.

## Quickstart

1. **Clone the repo and enter it.**

   ```bash
   git clone <your-fork-url> atlas
   cd atlas
   ```

2. **Copy the environment template.**

   ```bash
   cp .env.example .env
   ```

   Open `.env` and fill in a provider API key if you have one. If you skip
   this step, ATLAS runs in **Mock Mode** (see below) — no credentials are
   required to try the product end-to-end.

3. **Run the setup script for your platform.**

   - Windows (PowerShell): `./scripts/install-atlas-cli.ps1`
   - macOS / Linux (bash): `./scripts/setup.sh`

   This creates a dedicated Python virtual environment at `.venv` (never the
   ambient `python` on your PATH — see Troubleshooting below), editable-installs
   the ATLAS packages into it, builds the terminal UI bundle, builds the Rust
   gateway binary, builds the React cockpit bundle, and applies all pending
   database migrations. Each build step is skipped gracefully (with a clear
   message) if its toolchain (cargo / npm) is not installed — the rest of the
   install still completes.

4. **Seed a demo mission (optional, recommended for first run).**

   ```bash
   ./atlas db init --demo
   ```

   This populates the cockpit immediately with a sample mission, run, audit
   trail, and wiki entry — so the UI is not empty on first launch. Safe to
   re-run (idempotent, no-op if already seeded).

5. **Boot the gateway and cockpit together.**

   ```bash
   ./atlas up
   ```

6. **Confirm everything is healthy.**

   ```bash
   ./atlas doctor
   ```

   `atlas doctor` aggregates five independent checks — database migrations,
   config validity, gateway health, cockpit health, and provider
   configuration — and prints one line per check. Exit code `0` means every
   check passed.

7. Open the cockpit at `http://127.0.0.1:5173` in your browser.

## Docker Compose (optional, secondary path)

If you would rather not install Rust/Python/Node locally, a root
`docker-compose.yml` builds the gateway, agent-runtime, and cockpit from
source inside official base images:

```bash
cp .env.example .env   # fill in real values; never commit .env
docker compose up --build
```

Compose reads the same `.env` file you created for the native path (via
`env_file: .env` on each service) — `.env.example` itself never holds a real
secret. This path is optional and not required to reach a working install;
the native Quickstart above is the primary, fully-verified path.

## Mock Mode

ATLAS never requires a configured LLM provider to demonstrate its full run
pipeline. If `atlas doctor`'s provider check reports `provider: mock` (no
`ATLAS_PROVIDER_API_KEY`-style credential resolved), every mission run still
executes end-to-end through a deterministic, canned response and the
cockpit displays a **"MOCK MODE — no live model"** banner so it is always
obvious which mode you are in. `atlas db init --demo` uses this same mock
path to seed its sample mission/run/wiki entry — you can explore the entire
audit trail, wiki, and run lifecycle without ever setting a key.

## Troubleshooting

**`pip install` fails inside the setup script / "no module named pip".**
The ambient `python` on your system `PATH` may be a pip-less environment
(for example, a vendored runtime that ships without `pip`). This is exactly
why the setup scripts create and use a dedicated `.venv` at the repo root
instead of the ambient interpreter — always invoke ATLAS through
`./atlas` (which is generated to point at `.venv`), not a bare `atlas` /
`python -m atlas_runtime...` that might resolve to the wrong interpreter.

**A terminal window flashes open and closes when running `atlas up` on
Windows.** This is already handled automatically — the gateway and cockpit
are spawned as detached background processes with the appropriate Windows
process-creation flags (`DETACHED_PROCESS` / `CREATE_NO_WINDOW`). You should
not need to do anything; if you do see a flashing console, it is worth
filing as a bug rather than an expected operator step.

**I changed a port in `~/.atlas/config.yaml` and it had no effect.**
`config.yaml`'s `gateway.rust_port` / `cockpit.port` fields are
informational only today — `atlas up` does not read them. The
**environment variables are authoritative**: set `ATLAS_GATEWAY_PORT`,
`ATLAS_GATEWAY_URL`, and/or `ATLAS_COCKPIT_URL` in your `.env` (or shell
environment) instead. See `.env.example` for the full set and a longer
explanation of this precedence.

**`atlas doctor` reports `gateway: down`.** The gateway binary may not have
been built (cargo was missing during setup) or is not yet running. Re-run
the setup script after installing Rust, or run `./atlas gateway start`
directly to see the failure reason.

**`atlas doctor` reports `cockpit: down`.** Same idea — the cockpit bundle
may not have been built (npm was missing during setup), or `npm run preview`
has not started yet. Re-run the setup script after installing Node, or run
the cockpit dev server manually (`cd services/web-ui-react && npm run dev`)
to confirm it serves locally.

**Dispatch endpoints return 500 when running the gateway binary directly.**
The Rust gateway dispatches CLI commands (missions, runs, tools, channels,
etc.) by shelling out to the `atlas` CLI. It locates the CLI through the
`ATLAS_CLI` environment variable, which `atlas up` and `gateway_control`
inject automatically. If you start the gateway binary without going through
`atlas up` (e.g. `./native/atlas-core-rs/target/release/atlas-gateway`),
every dispatch endpoint will 500 because `ATLAS_CLI` is unset. Fix: set
`ATLAS_CLI` in your shell to the full invocation command — typically
`<path-to-.venv>/Scripts/python.exe -m atlas_runtime.cli.main` on Windows
or `<path-to-.venv>/bin/python -m atlas_runtime.cli.main` on macOS/Linux.
`atlas up` handles this for you; direct binary launch requires the variable.
