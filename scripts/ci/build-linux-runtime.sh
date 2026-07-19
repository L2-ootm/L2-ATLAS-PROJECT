#!/bin/sh
# Builds the self-contained Linux x64 ATLAS runtime bundle.
#
# Mirrors scripts/ci/build-windows-runtime.ps1 step-for-step (native build,
# Python bundling, runtime tree copy, manifest, import verification) adapted
# to POSIX tooling. Intended to run ON a Linux x64 runner in CI (not a
# cross-compile host) — see "assume each script runs ON its target OS"
# in the Phase 2 Track B1 brief.
#
# Linux aarch64 is explicitly deferred to v2 (see the arch guard below) —
# only x86_64 is built today.
#
# Usage:
#   scripts/ci/build-linux-runtime.sh [--version X.Y.Z] [--output-dir DIR]
#                                     [--skip-native-build] [--skip-web-build]

set -eu

# ---------------------------------------------------------------------------
# Argument parsing
# ---------------------------------------------------------------------------
VERSION="0.1.0"
OUTPUT_DIR=""
SKIP_NATIVE_BUILD=false
SKIP_WEB_BUILD=false

while [ $# -gt 0 ]; do
    case "$1" in
        --version) VERSION="$2"; shift 2 ;;
        --output-dir) OUTPUT_DIR="$2"; shift 2 ;;
        --skip-native-build) SKIP_NATIVE_BUILD=true; shift ;;
        --skip-web-build) SKIP_WEB_BUILD=true; shift ;;
        *) echo "unknown argument: $1" >&2; exit 1 ;;
    esac
done

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
REPO="$(cd "$SCRIPT_DIR/../.." && pwd)"
ARTIFACT_ROOT="$REPO/artifacts"
if [ -z "$OUTPUT_DIR" ]; then
    OUTPUT_DIR="$ARTIFACT_ROOT/atlas-linux-$VERSION"
fi

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

# Resolve to an absolute path without requiring the path to exist yet
# (GNU realpath -m does this; fall back to a plain pwd-join on hosts where
# realpath is missing/older — CI always passes absolute paths, so the
# fallback's lack of ".."-collapsing is not a practical risk here).
abspath() {
    if command -v realpath >/dev/null 2>&1 && realpath -m "$1" >/dev/null 2>&1; then
        realpath -m "$1"
        return
    fi
    case "$1" in
        /*) printf '%s\n' "$1" ;;
        *) printf '%s\n' "$(pwd)/$1" ;;
    esac
}

sha256_of() {
    if command -v sha256sum >/dev/null 2>&1; then
        sha256sum "$1" | awk '{print $1}'
    else
        shasum -a 256 "$1" | awk '{print $1}'
    fi
}

assert_hash() {
    path="$1"; expected="$2"
    actual="$(sha256_of "$path")"
    if [ "$actual" != "$expected" ]; then
        echo "SHA-256 mismatch for $path (expected $expected, got $actual)" >&2
        exit 1
    fi
}

get_pinned_file() {
    url="$1"; dest="$2"; expected_sha256="$3"
    if [ ! -f "$dest" ]; then
        mkdir -p "$(dirname "$dest")"
        curl -fsSL "$url" -o "$dest"
    fi
    assert_hash "$dest" "$expected_sha256"
}

copy_tree() {
    # copy_tree <relative-source> [relative-dest]
    relative="$1"
    dest_relative="${2:-$1}"
    source="$REPO/$relative"
    if [ ! -e "$source" ]; then
        echo "required runtime path missing: $relative" >&2
        exit 1
    fi
    destination="$BUNDLE/$dest_relative"
    mkdir -p "$(dirname "$destination")"
    cp -R "$source" "$destination"
}

copy_tracked_path() {
    # copy_tracked_path <pathspec> — mirrors Copy-TrackedPath in the Windows
    # script: only files `git ls-files` actually tracks are copied, so
    # build artifacts / gitignored files never leak into the bundle.
    pathspec="$1"
    files="$(git -C "$REPO" ls-files -- "$pathspec")"
    if [ -z "$files" ]; then
        echo "tracked runtime path missing: $pathspec" >&2
        exit 1
    fi
    printf '%s\n' "$files" | while IFS= read -r file; do
        [ -n "$file" ] || continue
        source="$REPO/$file"
        [ -f "$source" ] || continue
        destination="$BUNDLE/$file"
        mkdir -p "$(dirname "$destination")"
        cp "$source" "$destination"
    done
}

clean_pycache() {
    find "$BUNDLE" -type d -name '__pycache__' -prune -exec rm -rf {} + 2>/dev/null || true
    find "$BUNDLE" -type f -name '*.pyc' -delete 2>/dev/null || true
}

BUNDLE="$(abspath "$OUTPUT_DIR")"
ARTIFACT_PREFIX="$(abspath "$ARTIFACT_ROOT")/"
case "$BUNDLE/" in
    "$ARTIFACT_PREFIX"*) ;;
    *) echo "output dir must stay inside $ARTIFACT_ROOT" >&2; exit 1 ;;
esac

# ---------------------------------------------------------------------------
# Pinned versions — must match scripts/ci/build-windows-runtime.ps1's
# $pythonVersion exactly so every platform ships the same Python.
# ---------------------------------------------------------------------------
PYTHON_VERSION="3.13.11"
PBS_TAG="20251205"
PYTHON_ARCH="$(uname -m)"
if [ "$PYTHON_ARCH" != "x86_64" ]; then
    # TODO(v2): Linux aarch64. python-build-standalone publishes
    # cpython-3.13.11+20251205-aarch64-unknown-linux-gnu-install_only.tar.gz
    # for that target; wire it up alongside a linux-arm64 CI runner when
    # this becomes a priority. Deliberately out of scope for Track B1 v1.
    echo "Linux $PYTHON_ARCH is not supported yet (v1 ships x86_64 only; aarch64 is a v2 TODO)" >&2
    exit 1
fi
PYTHON_ASSET="cpython-${PYTHON_VERSION}+${PBS_TAG}-x86_64-unknown-linux-gnu-install_only.tar.gz"
PYTHON_URL="https://github.com/astral-sh/python-build-standalone/releases/download/${PBS_TAG}/cpython-${PYTHON_VERSION}%2B${PBS_TAG}-x86_64-unknown-linux-gnu-install_only.tar.gz"
PYTHON_SHA256="b4538783d3ad62fc91ce43c2028558f8520b1b753cfbba17eddd8fa480a46a33"

CACHE="$ARTIFACT_ROOT/.cache"
NATIVE_BUILD_ROOT="$ARTIFACT_ROOT/.build/$VERSION"
GATEWAY_BUILD="$NATIVE_BUILD_ROOT/cargo/release/atlas-gateway"
TUI_BUILD="$NATIVE_BUILD_ROOT/atlas-tui"
PYTHON_TARBALL="$CACHE/$PYTHON_ASSET"

# ---------------------------------------------------------------------------
# Native build
# ---------------------------------------------------------------------------
if [ "$SKIP_NATIVE_BUILD" = false ]; then
    mkdir -p "$NATIVE_BUILD_ROOT"
    (
        cd "$REPO/native/atlas-core-rs"
        CARGO_TARGET_DIR="$NATIVE_BUILD_ROOT/cargo" cargo build --release -p atlas-gateway
    )
    (
        cd "$REPO/services/atlas-tui"
        GOOS=linux GOARCH=amd64 go build -trimpath -ldflags '-s -w' -o "$TUI_BUILD" .
    )
else
    GATEWAY_BUILD="$REPO/native/atlas-core-rs/target/release/atlas-gateway"
    TUI_BUILD="$REPO/services/atlas-tui/atlas-tui"
fi

if [ "$SKIP_WEB_BUILD" = false ]; then
    (
        cd "$REPO/services/web-ui-react"
        npm run build
    )
fi

# ---------------------------------------------------------------------------
# Required output guard (same intent as the Windows script's $required list)
# ---------------------------------------------------------------------------
for relative in \
    "services/web-ui-react/dist/index.html" \
    "packages/atlas-cli/runtime/linux/atlas"; do
    if [ ! -f "$REPO/$relative" ]; then
        echo "required build output missing: $relative" >&2
        exit 1
    fi
done
for output in "$GATEWAY_BUILD" "$TUI_BUILD"; do
    if [ ! -f "$output" ]; then
        echo "required native build output missing: $output" >&2
        exit 1
    fi
done

if [ -d "$BUNDLE" ]; then rm -rf "$BUNDLE"; fi
mkdir -p "$BUNDLE"

# ---------------------------------------------------------------------------
# Embedded Python (python-build-standalone install_only — ships pip already;
# no get-pip bootstrap needed, unlike the Windows embeddable zip).
# ---------------------------------------------------------------------------
get_pinned_file "$PYTHON_URL" "$PYTHON_TARBALL" "$PYTHON_SHA256"
# The archive's own top-level entry is "python/", so extracting into $BUNDLE
# (not $BUNDLE/python) yields $BUNDLE/python/bin/python3 directly.
tar -xzf "$PYTHON_TARBALL" -C "$BUNDLE" --no-same-owner
PYTHON="$BUNDLE/python/bin/python3"

# Standard CPython has no ._pth mechanism (that's Windows-embeddable-only);
# the POSIX equivalent is a .pth file in site-packages, whose relative lines
# the `site` module resolves against the site-packages directory itself.
# site-packages here is 4 levels below the bundle root
# ($BUNDLE/python/lib/python3.13/site-packages), so "../../../.." reaches
# the bundle root and each runtime tree hangs off that.
SITE_PACKAGES="$BUNDLE/python/lib/python${PYTHON_VERSION%.*}/site-packages"
if [ ! -d "$SITE_PACKAGES" ]; then
    echo "expected site-packages directory missing: $SITE_PACKAGES" >&2
    exit 1
fi
cat > "$SITE_PACKAGES/atlas-runtime.pth" <<'EOF'
../../../../services/agent-runtime
../../../../packages/atlas-core
../../../../services/wiki-runtime
../../../../foundation/atlas-hermes
EOF

# ---------------------------------------------------------------------------
# Pinned runtime dependencies — identical set/versions to the Windows script
# so every platform runs the same Python dependency closure. PYTHONNOUSERSITE
# is belt-and-suspenders alongside -s (matches the Windows script): neither
# a build host's own user site-packages nor its PYTHONPATH should leak in.
# ---------------------------------------------------------------------------
export PYTHONNOUSERSITE=1
"$PYTHON" -s -m pip install --disable-pip-version-check --no-compile \
    'openai==2.24.0' \
    'python-dotenv==1.2.2' \
    'fire==0.7.1' \
    'httpx[socks]==0.28.1' \
    'rich==14.3.3' \
    'tenacity==9.1.4' \
    'pyyaml==6.0.3' \
    'ruamel.yaml==0.18.17' \
    'requests==2.33.0' \
    'jinja2==3.1.6' \
    'pydantic==2.13.4' \
    'prompt_toolkit==3.0.52' \
    'croniter==6.0.0' \
    'PyJWT[crypto]==2.12.1' \
    'tzdata==2025.3' \
    'psutil==7.2.2' \
    'typer==0.25.1' \
    'claude-agent-sdk==0.2.104'

# ---------------------------------------------------------------------------
# Runtime trees (same source paths as build-windows-runtime.ps1)
# ---------------------------------------------------------------------------
for relative in \
    "infra/migrations" \
    "modules" \
    "skills/atlas" \
    "packages/atlas-core/atlas_core" \
    "services/agent-runtime/atlas_runtime" \
    "services/agent-runtime/atlas_audit" \
    "services/wiki-runtime/atlas_wiki" \
    "foundation/atlas-hermes/acp_adapter" \
    "foundation/atlas-hermes/acp_registry" \
    "foundation/atlas-hermes/agent" \
    "foundation/atlas-hermes/assets" \
    "foundation/atlas-hermes/cron" \
    "foundation/atlas-hermes/gateway" \
    "foundation/atlas-hermes/hermes_cli" \
    "foundation/atlas-hermes/locales" \
    "foundation/atlas-hermes/optional-skills" \
    "foundation/atlas-hermes/plugins" \
    "foundation/atlas-hermes/providers" \
    "foundation/atlas-hermes/skills" \
    "foundation/atlas-hermes/tools" \
    "foundation/atlas-hermes/tui_gateway"; do
    copy_tracked_path "$relative"
done
copy_tracked_path ':(glob)foundation/atlas-hermes/*.py'
copy_tree "services/web-ui-react/dist"
copy_tree "services/web-ui-react/scripts/serve-dist.mjs"

copy_tracked_path "services/atlas-tui/go.mod"
mkdir -p "$BUNDLE/native/atlas-core-rs/target/release"
cp "$GATEWAY_BUILD" "$BUNDLE/native/atlas-core-rs/target/release/atlas-gateway"
chmod 755 "$BUNDLE/native/atlas-core-rs/target/release/atlas-gateway"
mkdir -p "$BUNDLE/services/atlas-tui"
cp "$TUI_BUILD" "$BUNDLE/services/atlas-tui/atlas-tui"
chmod 755 "$BUNDLE/services/atlas-tui/atlas-tui"
mkdir -p "$BUNDLE/bin"
cp "$REPO/packages/atlas-cli/runtime/linux/atlas" "$BUNDLE/bin/atlas"
chmod 755 "$BUNDLE/bin/atlas"
cp "$REPO/LICENSE" "$BUNDLE/LICENSE"
cp "$REPO/THIRD_PARTY_LICENSES.md" "$BUNDLE/THIRD_PARTY_LICENSES.md"

# Never publish bytecode copied from a build-time interpreter.
clean_pycache

BUILT_AT="$(date -u +%Y-%m-%dT%H:%M:%SZ)"
cat > "$BUNDLE/runtime.json" <<EOF
{
  "version": "$VERSION",
  "platform": "linux-x64",
  "entrypoint": "bin/atlas",
  "python": "$PYTHON_VERSION",
  "built_at": "$BUILT_AT"
}
EOF

# ---------------------------------------------------------------------------
# Verification
# ---------------------------------------------------------------------------
PYTHONDONTWRITEBYTECODE=1 "$PYTHON" -s -c \
    'import atlas_core, atlas_runtime, atlas_wiki, agent, claude_agent_sdk; print("embedded runtime imports: OK")'
PYTHONDONTWRITEBYTECODE=1 "$PYTHON" -s -m atlas_runtime.cli.main --help | head -1

# Verification imports must not leave interpreter caches in the immutable
# payload either.
clean_pycache

SIZE="$(find "$BUNDLE" -type f -exec du -k {} + | awk '{sum+=$1} END {printf "%.1f", sum/1024}')"
FILES="$(find "$BUNDLE" -type f | wc -l | tr -d ' ')"
echo "bundle: $BUNDLE"
echo "files: $FILES"
echo "size: ${SIZE} MB"
