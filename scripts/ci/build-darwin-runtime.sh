#!/bin/sh
# Builds the self-contained macOS ATLAS runtime bundle (x86_64 or arm64,
# auto-detected from `uname -m` — matches running this script natively on
# macos-13 (Intel) and macos-14 (Apple Silicon) GitHub-hosted runners).
#
# Mirrors scripts/ci/build-windows-runtime.ps1 step-for-step (native build,
# Python bundling, runtime tree copy, manifest, import verification) adapted
# to POSIX tooling. See build-linux-runtime.sh for the near-identical Linux
# sibling; the two are kept in sync deliberately rather than sharing a
# library, since CI matrix jobs invoke exactly one of them per runner and a
# shared-library indirection would cost more than it saves at this scale.
#
# No code-signing / notarization is performed — explicitly deferred per the
# Phase 2 Track B1 brief; these are unsigned developer-distribution binaries.
#
# Usage:
#   scripts/ci/build-darwin-runtime.sh [--version X.Y.Z] [--output-dir DIR]
#                                      [--skip-native-build] [--skip-web-build]

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

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

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

# ---------------------------------------------------------------------------
# Architecture detection (v1 ships both — Apple Silicon is the dominant Mac
# today, unlike Linux where aarch64 is deferred).
# ---------------------------------------------------------------------------
MAC_ARCH="$(uname -m)"
PYTHON_VERSION="3.13.11"
PBS_TAG="20251205"
case "$MAC_ARCH" in
    x86_64)
        NPM_ARCH="x64"
        GOARCH="amd64"
        PYTHON_TRIPLE="x86_64-apple-darwin"
        PYTHON_SHA256="907c5329932222cbc6fd3acc5872a9287551adcbaa1e9cffad0422c3a3a11feb"
        ;;
    arm64)
        NPM_ARCH="arm64"
        GOARCH="arm64"
        PYTHON_TRIPLE="aarch64-apple-darwin"
        PYTHON_SHA256="6d01501c49e2941876293fe7196315cdb8a2fe665547b4b05a2c8e44102f781c"
        ;;
    *)
        echo "unsupported macOS architecture: $MAC_ARCH" >&2
        exit 1
        ;;
esac
PLATFORM="darwin-$NPM_ARCH"
PYTHON_ASSET="cpython-${PYTHON_VERSION}+${PBS_TAG}-${PYTHON_TRIPLE}-install_only.tar.gz"
PYTHON_URL="https://github.com/astral-sh/python-build-standalone/releases/download/${PBS_TAG}/cpython-${PYTHON_VERSION}%2B${PBS_TAG}-${PYTHON_TRIPLE}-install_only.tar.gz"

if [ -z "$OUTPUT_DIR" ]; then
    OUTPUT_DIR="$ARTIFACT_ROOT/atlas-darwin-$NPM_ARCH-$VERSION"
fi
BUNDLE="$(abspath "$OUTPUT_DIR")"
ARTIFACT_PREFIX="$(abspath "$ARTIFACT_ROOT")/"
case "$BUNDLE/" in
    "$ARTIFACT_PREFIX"*) ;;
    *) echo "output dir must stay inside $ARTIFACT_ROOT" >&2; exit 1 ;;
esac

CACHE="$ARTIFACT_ROOT/.cache"
NATIVE_BUILD_ROOT="$ARTIFACT_ROOT/.build/$VERSION-$NPM_ARCH"
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
        GOOS=darwin GOARCH="$GOARCH" go build -trimpath -ldflags '-s -w' -o "$TUI_BUILD" .
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
# Required output guard
# ---------------------------------------------------------------------------
for relative in \
    "services/web-ui-react/dist/index.html" \
    "packages/atlas-cli/runtime/darwin/atlas"; do
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
# Embedded Python (python-build-standalone install_only — ships pip already).
# ---------------------------------------------------------------------------
get_pinned_file "$PYTHON_URL" "$PYTHON_TARBALL" "$PYTHON_SHA256"
tar -xzf "$PYTHON_TARBALL" -C "$BUNDLE" --no-same-owner
PYTHON="$BUNDLE/python/bin/python3"

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
# Pinned runtime dependencies — identical set/versions to the Windows script.
# PYTHONNOUSERSITE is belt-and-suspenders alongside -s (matches the Windows
# script): neither a build host's user site-packages nor its PYTHONPATH
# should leak into the bundled dependency closure.
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
cp "$REPO/packages/atlas-cli/runtime/darwin/atlas" "$BUNDLE/bin/atlas"
chmod 755 "$BUNDLE/bin/atlas"
cp "$REPO/LICENSE" "$BUNDLE/LICENSE"
cp "$REPO/THIRD_PARTY_LICENSES.md" "$BUNDLE/THIRD_PARTY_LICENSES.md"

clean_pycache

BUILT_AT="$(date -u +%Y-%m-%dT%H:%M:%SZ)"
cat > "$BUNDLE/runtime.json" <<EOF
{
  "version": "$VERSION",
  "platform": "$PLATFORM",
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

clean_pycache

SIZE="$(find "$BUNDLE" -type f -exec du -k {} + | awk '{sum+=$1} END {printf "%.1f", sum/1024}')"
FILES="$(find "$BUNDLE" -type f | wc -l | tr -d ' ')"
echo "bundle: $BUNDLE"
echo "platform: $PLATFORM"
echo "files: $FILES"
echo "size: ${SIZE} MB"
