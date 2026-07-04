#!/usr/bin/env bash
# Install the ATLAS `atlas` CLI into a dedicated repo venv and bootstrap the DB.
# POSIX bash twin of scripts/install-atlas-cli.ps1 — keep both in sync.
#
# After this runs:
#   - `./atlas` is a wrapper script at the repo root that runs the `atlas`
#     console script from the dedicated venv (so the gateway/cockpit can
#     dispatch writes and `atlas db init` / `atlas gateway start` work).
#   - ~/.atlas/atlas.db has every migration applied (idempotent, non-destructive).
#
# Usage (from repo root): ./scripts/setup.sh
# Optional Claude runtime: ./scripts/setup.sh --claude
set -euo pipefail

CLAUDE=0
for arg in "$@"; do
  case "$arg" in
    --claude) CLAUDE=1 ;;
    *) echo "Unknown argument: $arg" >&2; exit 1 ;;
  esac
done

root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

# Target a dedicated repo venv, never the ambient `python` on PATH — on a
# foundation-only machine that PATH python may be a pip-less venv that cannot
# pip-install. Create the venv if missing.
venv="$root/.venv"
venv_py="$venv/bin/python"
if [ ! -x "$venv_py" ]; then
  echo "Creating venv at $venv"
  if command -v python3 >/dev/null 2>&1; then
    python3 -m venv "$venv"
  else
    python -m venv "$venv"
  fi
fi
"$venv_py" -m pip install --upgrade pip >/dev/null
echo "Repo:   $root"
echo "Python: $venv_py"

# Editable installs (order matters: core is a dependency of the runtimes).
"$venv_py" -m pip install -e "$root/packages/atlas-core"
if [ "$CLAUDE" -eq 1 ]; then
  runtime_spec="$root/services/agent-runtime[claude]"
else
  runtime_spec="$root/services/agent-runtime"
fi
"$venv_py" -m pip install -e "$runtime_spec"
"$venv_py" -m pip install -e "$root/services/wiki-runtime"

# Regenerate the portable `atlas` shim at repo root, pointing at THIS repo's
# venv (so `./atlas ...` works from the repo without touching PATH). The
# gateway self-resolves its own ATLAS_CLI from the venv interpreter
# (gateway_control).
atlas_exe="$venv/bin/atlas"
atlas_shim="$root/atlas"
{
  echo '#!/usr/bin/env bash'
  echo "exec \"$venv_py\" -m atlas_runtime.cli.main \"\$@\""
} > "$atlas_shim"
chmod +x "$atlas_shim"

# Build the Go/BubbleTea sidecar into the ATLAS-owned binary directory used by
# the Python launcher. No shell or foundation npm bundle participates in P8.
atlas_home="${ATLAS_HOME:-$HOME/.atlas}"
tui="$root/services/atlas-tui"
if command -v go >/dev/null 2>&1; then
  mkdir -p "$atlas_home/bin"
  echo "Building atlas-tui -> $atlas_home/bin/atlas-tui"
  (cd "$tui" && go build -trimpath -ldflags='-s -w' -o "$atlas_home/bin/atlas-tui" .)
else
  echo "Skipping atlas-tui build: Go not found. Install Go 1.26+ and rerun, or set ATLAS_TUI_BIN to a prebuilt binary."
fi

# Build the Rust gateway binary (release). Skipped gracefully when cargo is
# absent — `atlas up` will report "gateway: down" via `atlas doctor` until a
# binary is built, but the rest of the install still completes.
if command -v cargo >/dev/null 2>&1; then
  echo "Building atlas-gateway (cargo build --release)"
  (cd "$root/native/atlas-core-rs" && cargo build --release -p atlas-gateway)
else
  echo "Skipping gateway build (cargo not found); install Rust or set up the gateway manually."
fi

# Build the React cockpit (production bundle consumed by `npm run preview` /
# cockpit_control.start()). Skipped gracefully when npm is absent.
cockpit="$root/services/web-ui-react"
if command -v npm >/dev/null 2>&1 && [ -d "$cockpit" ]; then
  echo "Building the cockpit ($cockpit)"
  (cd "$cockpit" && npm install && npm run build)
else
  echo "Skipping cockpit build (npm not found)."
fi

# Install + typecheck atlas-terminal (donor-based TUI surface, not yet the
# default `atlas tui` entry — see STAGE 3 retirement gate). Skipped gracefully
# when bun is absent, same as the go/cargo/npm steps above; like those steps,
# a typecheck failure here aborts the rest of install (set -e).
atlas_terminal="$root/services/atlas-terminal"
if command -v bun >/dev/null 2>&1 && [ -d "$atlas_terminal" ]; then
  echo "Installing + typechecking atlas-terminal ($atlas_terminal)"
  (cd "$atlas_terminal" && bun install && bun run typecheck)
else
  echo "Skipping atlas-terminal build (bun not found)."
fi

# Bootstrap / migrate the DB (idempotent, non-destructive).
"$atlas_exe" db init

# Verify the console script resolved inside the venv.
"$atlas_exe" --help | head -n 1
echo ""
echo "Done. The 'atlas' console script lives at $atlas_exe."
echo "Use './atlas <cmd>' from the repo root, or add '$venv/bin' to PATH for a bare 'atlas'."
