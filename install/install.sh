#!/bin/sh
# ATLAS one-line bootstrap for Linux and macOS (POSIX shell).
#
#   curl -fsSL https://raw.githubusercontent.com/L2-ootm/L2-ATLAS-PROJECT/main/install/install.sh | bash
#
# Mirrors install/install.ps1's RELEASE mode exactly:
#   1. Ensures Node.js >= 20 (auto-installs a pinned LTS tarball from
#      nodejs.org if missing/too old — no sudo, no system package manager).
#   2. Installs the public npm launcher (@systemsl2/atlas) globally.
#   3. Runs `atlas install` to materialize the self-contained runtime
#      (embedded Python, Rust gateway, Go TUI, cockpit — no local Python,
#      Rust, Go, or Git required).
#   4. Runs `atlas doctor` to verify.
#
# SOURCE mode (cloning the repo and building from source) is intentionally
# out of scope here — see docs/operations/INSTALL.md's POSIX section for
# the existing `scripts/setup.sh` source path. This script only ever
# installs the published release.
#
# User-level only: everything lands under $HOME, nothing requires root.
# Styled after foundation/atlas-hermes/scripts/install.sh's POSIX
# conventions (color helpers, uname-based platform/arch detection,
# non-interactive-safe prompts) — that script is the local reference for
# "how POSIX installers behave in this repo", though it installs a
# different product (Hermes) via uv/pip rather than npm.
#
# Options (flags only; no positional args):
#   --node-version N   Node.js major version to auto-install if needed
#                       (default: 22, matches the repo's CI node-version)
#   --force            Reinstall even if already on the latest version
#   -h, --help         Show this help

set -eu

# ---------------------------------------------------------------------------
# Colors (disabled when stdout is not a terminal, matching common installer
# hygiene — curl | bash pipes are still colorized because bash's stdout is
# usually still the user's terminal; only redirect-to-file loses color).
# ---------------------------------------------------------------------------
if [ -t 1 ]; then
    RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[0;33m'
    CYAN='\033[0;36m'; GRAY='\033[0;90m'; BOLD='\033[1m'; NC='\033[0m'
else
    RED=''; GREEN=''; YELLOW=''; CYAN=''; GRAY=''; BOLD=''; NC=''
fi

log_step()    { printf "%b==>%b %s\n" "$CYAN" "$NC" "$1"; }
log_ok()      { printf "  %b[OK]%b %s\n" "$GREEN" "$NC" "$1"; }
log_warn()    { printf "  %b[WARN]%b %s\n" "$YELLOW" "$NC" "$1"; }
log_error()   { printf "  %b[ERROR]%b %s\n" "$RED" "$NC" "$1" >&2; }

# ---------------------------------------------------------------------------
# Options
# ---------------------------------------------------------------------------
NODE_MAJOR=22
FORCE=false

while [ $# -gt 0 ]; do
    case "$1" in
        --node-version) NODE_MAJOR="$2"; shift 2 ;;
        --force) FORCE=true; shift ;;
        -h|--help)
            echo "Usage: install.sh [--node-version N] [--force]"
            echo ""
            echo "  --node-version N   Node.js major version to auto-install (default: 22)"
            echo "  --force            Reinstall even if already on the latest version"
            exit 0
            ;;
        *) log_error "Unknown option: $1"; exit 1 ;;
    esac
done

NPM_PACKAGE="@systemsl2/atlas"
NODE_INSTALL_DIR="$HOME/.atlas/node"
LOCAL_BIN="$HOME/.local/bin"
RTK_VERSION="0.43.0"
RTK_BIN_DIR="$HOME/.atlas/rtk"

# ---------------------------------------------------------------------------
# Platform detection
# ---------------------------------------------------------------------------
detect_platform() {
    case "$(uname -s)" in
        Linux*) OS="linux" ;;
        Darwin*) OS="macos" ;;
        *)
            log_error "Unsupported OS: $(uname -s). Use install/install.ps1 on Windows."
            exit 1
            ;;
    esac
    case "$(uname -m)" in
        x86_64|amd64) ARCH="x64" ;;
        aarch64|arm64) ARCH="arm64" ;;
        *)
            log_error "Unsupported architecture: $(uname -m)"
            exit 1
            ;;
    esac
    log_ok "Detected: $OS ($ARCH)"
}

# ---------------------------------------------------------------------------
# Node.js — the only external prerequisite (matches install.ps1's framing)
# ---------------------------------------------------------------------------
node_major_version() {
    node --version 2>/dev/null | sed 's/^v//' | cut -d. -f1
}

ensure_node() {
    if command -v node >/dev/null 2>&1; then
        found_major="$(node_major_version)"
        if [ "$found_major" -ge 20 ] 2>/dev/null; then
            log_ok "Node.js $(node --version) found"
            return 0
        fi
        log_warn "Node.js $(node --version) found but >= 20 is required"
    fi

    # Reuse a previous auto-install before downloading again.
    if [ -x "$NODE_INSTALL_DIR/bin/node" ]; then
        export PATH="$NODE_INSTALL_DIR/bin:$PATH"
        found_major="$(node_major_version)"
        if [ "$found_major" -ge 20 ] 2>/dev/null; then
            log_ok "Node.js $(node --version) found (ATLAS-managed)"
            return 0
        fi
    fi

    log_step "Installing Node.js ${NODE_MAJOR}.x LTS (no system package manager, no sudo)"
    node_os="$OS"
    if [ "$node_os" = "macos" ]; then node_os="darwin"; fi
    node_arch="$ARCH"

    index_url="https://nodejs.org/dist/latest-v${NODE_MAJOR}.x/"
    tarball_name="$(curl -fsSL "$index_url" \
        | grep -oE "node-v${NODE_MAJOR}\.[0-9]+\.[0-9]+-${node_os}-${node_arch}\.tar\.xz" \
        | head -1)"
    if [ -z "$tarball_name" ]; then
        tarball_name="$(curl -fsSL "$index_url" \
            | grep -oE "node-v${NODE_MAJOR}\.[0-9]+\.[0-9]+-${node_os}-${node_arch}\.tar\.gz" \
            | head -1)"
    fi
    if [ -z "$tarball_name" ]; then
        log_error "Could not find a Node.js ${NODE_MAJOR}.x build for ${node_os}-${node_arch}"
        log_error "Install Node.js 20+ manually (https://nodejs.org) and re-run this script."
        exit 1
    fi

    tmp_dir="$(mktemp -d)"
    trap 'rm -rf "$tmp_dir"' EXIT
    log_step "Downloading $tarball_name"
    curl -fsSL "${index_url}${tarball_name}" -o "$tmp_dir/$tarball_name"

    log_step "Extracting to $NODE_INSTALL_DIR"
    case "$tarball_name" in
        *.tar.xz) tar -xf "$tmp_dir/$tarball_name" -C "$tmp_dir" ;;
        *) tar -xzf "$tmp_dir/$tarball_name" -C "$tmp_dir" ;;
    esac
    extracted_dir="$(find "$tmp_dir" -maxdepth 1 -type d -name 'node-v*' | head -1)"
    if [ -z "$extracted_dir" ]; then
        log_error "Node.js archive extraction failed"
        exit 1
    fi

    rm -rf "$NODE_INSTALL_DIR"
    mkdir -p "$(dirname "$NODE_INSTALL_DIR")"
    mv "$extracted_dir" "$NODE_INSTALL_DIR"

    mkdir -p "$LOCAL_BIN"
    ln -sf "$NODE_INSTALL_DIR/bin/node" "$LOCAL_BIN/node"
    ln -sf "$NODE_INSTALL_DIR/bin/npm" "$LOCAL_BIN/npm"
    ln -sf "$NODE_INSTALL_DIR/bin/npx" "$LOCAL_BIN/npx"
    export PATH="$NODE_INSTALL_DIR/bin:$LOCAL_BIN:$PATH"

    if ! command -v node >/dev/null 2>&1; then
        log_error "Node.js installation completed but node is not on PATH"
        exit 1
    fi
    log_ok "Node.js $(node --version) installed to $NODE_INSTALL_DIR"
    log_warn "Add $LOCAL_BIN to your PATH permanently (e.g. in ~/.profile or ~/.zshrc):"
    log_warn "  export PATH=\"$LOCAL_BIN:\$PATH\""
}

# ---------------------------------------------------------------------------
# RTK (Rust Token Killer) — optional but recommended for 60-90% token savings
# ---------------------------------------------------------------------------
ensure_rtk() {
    if command -v rtk >/dev/null 2>&1; then
        log_ok "RTK $(rtk --version 2>/dev/null | head -1) found"
        return 0
    fi

    if [ -x "$RTK_BIN_DIR/rtk" ]; then
        export PATH="$RTK_BIN_DIR:$PATH"
        log_ok "RTK found at $RTK_BIN_DIR"
        return 0
    fi

    log_step "Installing RTK v${RTK_VERSION} (60-90% token savings on shell commands)"

    # Map platform to RTK release asset name
    rtk_os="$OS"
    rtk_arch="$ARCH"
    if [ "$rtk_arch" = "x64" ]; then rtk_arch="x86_64"; fi
    if [ "$rtk_os" = "linux" ]; then
        rtk_target="${rtk_arch}-unknown-linux-musl"
        rtk_ext="tar.gz"
    elif [ "$rtk_os" = "macos" ]; then
        rtk_target="${rtk_arch}-apple-darwin"
        rtk_ext="tar.gz"
    fi

    rtk_url="https://github.com/rtk-ai/rtk/releases/download/v${RTK_VERSION}/rtk-${rtk_target}.tar.gz"
    tmp_dir="$(mktemp -d)"
    trap 'rm -rf "$tmp_dir"' EXIT

    log_step "Downloading RTK from $rtk_url"
    if ! curl -fsSL "$rtk_url" -o "$tmp_dir/rtk.tar.gz" 2>/dev/null; then
        log_warn "RTK download failed — RTK will not be installed (optional)"
        log_warn "Install manually: https://github.com/rtk-ai/rtk"
        return 0
    fi

    log_step "Extracting RTK"
    tar -xzf "$tmp_dir/rtk.tar.gz" -C "$tmp_dir" 2>/dev/null || {
        log_warn "RTK extraction failed — RTK will not be installed (optional)"
        return 0
    }

    mkdir -p "$RTK_BIN_DIR"
    # Find the rtk binary in the extracted directory
    rtk_extracted="$(find "$tmp_dir" -name "rtk" -type f -executable 2>/dev/null | head -1)"
    if [ -z "$rtk_extracted" ]; then
        rtk_extracted="$(find "$tmp_dir" -name "rtk" -type f 2>/dev/null | head -1)"
    fi

    if [ -n "$rtk_extracted" ]; then
        cp "$rtk_extracted" "$RTK_BIN_DIR/rtk"
        chmod +x "$RTK_BIN_DIR/rtk"
        export PATH="$RTK_BIN_DIR:$PATH"
        log_ok "RTK installed to $RTK_BIN_DIR/rtk"
        log_warn "Add $RTK_BIN_DIR to your PATH permanently (e.g. in ~/.profile or ~/.zshrc):"
        log_warn "  export PATH=\"$RTK_BIN_DIR:\$PATH\""
    else
        log_warn "RTK binary not found in archive — RTK will not be installed (optional)"
    fi
}

# ---------------------------------------------------------------------------
# Existing installation check (mirrors install.ps1's Get-CurrentVersion:
# read the materialized runtime's install.json directly — this is the
# runtime version atlas-cli manages via installState.js's readInstallState,
# not the npm launcher package version, which is a separate number).
# ---------------------------------------------------------------------------
atlas_install_root() {
    if [ -n "${ATLAS_INSTALL_ROOT:-}" ]; then
        echo "$ATLAS_INSTALL_ROOT"
        return
    fi
    if [ "$OS" = "macos" ]; then
        echo "$HOME/Library/Application Support/atlas"
    else
        echo "${XDG_DATA_HOME:-$HOME/.local/share}/atlas"
    fi
}

current_atlas_version() {
    install_json="$(atlas_install_root)/install.json"
    [ -f "$install_json" ] || return 0
    grep -o '"installedVersion"[[:space:]]*:[[:space:]]*"[^"]*"' "$install_json" \
        | head -1 | sed -E 's/.*"([^"]*)"$/\1/'
}

# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
printf "\n  %bA T L A S%b — operator install\n" "$BOLD" "$NC"
printf "  %bL2 Systems%b\n\n" "$GRAY" "$NC"

detect_platform

current_version="$(current_atlas_version || true)"
if [ -n "$current_version" ]; then
    log_ok "Current installation: $current_version"
    latest_version="$(npm view "$NPM_PACKAGE" version 2>/dev/null || true)"
    if [ -n "$latest_version" ] && [ "$latest_version" = "$current_version" ] && [ "$FORCE" = false ]; then
        printf "\n  Already on latest version (%s)\n" "$current_version"
        printf "  Run with --force to reinstall, or: atlas update\n\n"
        exit 0
    fi
    if [ -n "$latest_version" ]; then
        log_warn "Available update: $latest_version"
    fi
fi

log_step "Checking the only external prerequisite: Node.js 20+"
ensure_node

log_step "Installing the latest ${NPM_PACKAGE} lifecycle launcher"
npm install --global "${NPM_PACKAGE}@latest"

ATLAS_BIN="$(command -v atlas || echo "")"
if [ -z "$ATLAS_BIN" ]; then
    log_error "npm installed ATLAS but 'atlas' was not found on PATH"
    log_error "It may be at: $(npm prefix -g 2>/dev/null)/bin/atlas — add that directory to PATH and re-run."
    exit 1
fi

REPO="L2-ootm/L2-ATLAS-PROJECT"
PLATFORM_PKG="systemsl2-atlas-${OS}-${ARCH}"

download_runtime_from_github() {
    log_step "Looking up latest release from GitHub"
    releases_json="$(curl -fsSL "https://api.github.com/repos/${REPO}/releases?per_page=10")"

    # Find the first release containing the platform asset
    asset_name=""; download_url=""; version=""; tag_name=""
    for name in $(echo "$releases_json" | grep -oE "\"name\":\"${PLATFORM_PKG}-[0-9][^\"]*\.tgz\"" | sed 's/"name":"//;s/"//'); do
        asset_name="$name"
        version="$(echo "$name" | sed "s/^${PLATFORM_PKG}-//;s/\.tgz$//")"
        download_url="$(echo "$releases_json" | grep -oE "\"browser_download_url\":\"[^\"]*${name}\"" | head -1 | sed 's/"browser_download_url":"//;s/"//')"
        tag_name="$(echo "$releases_json" | grep -oE "\"tag_name\":\"[^\"]*\"" | head -1 | sed 's/"tag_name":"//;s/"//')"
        break
    done
    if [ -z "$download_url" ]; then
        log_error "No ${PLATFORM_PKG} asset found in any GitHub release"
        exit 1
    fi

    log_step "Downloading ATLAS runtime v${version} (${asset_name})"
    tmp_dir="$(mktemp -d)"
    trap 'rm -rf "$tmp_dir"' EXIT
    curl -fsSL "$download_url" -o "$tmp_dir/runtime.tgz"

    dest="$(atlas_install_root)/versions/${version}"
    rm -rf "$dest"
    mkdir -p "$dest"
    log_step "Extracting runtime"
    tar -xzf "$tmp_dir/runtime.tgz" -C "$dest" --strip-components=1

    rm -rf "$tmp_dir"

    ep="bin/atlas.js"
    if [ ! -f "$dest/$ep" ]; then ep="atlas.js"; fi

    install_root="$(atlas_install_root)"
    printf '%s\n' "$version" > "$install_root/current"
    cat > "$install_root/install.json" <<EOJSON
{
  "installedVersion": "$version",
  "installMethod": "github-release",
  "lastUpdateCheck": "$(date -u +%Y-%m-%dT%H:%M:%SZ)",
  "runtimeEntrypoint": "$ep"
}
EOJSON
    log_ok "Runtime v${version} installed from GitHub release ${tag_name}"
}

log_step "Materializing the verified, self-contained ATLAS runtime"
if ! atlas install; then
    log_warn "npm platform package unavailable; downloading runtime from GitHub releases"
    state_file="$(atlas_install_root)/install.json"
    has_entrypoint=false
    if [ -f "$state_file" ]; then
        ep_val="$(grep -o '"runtimeEntrypoint"[[:space:]]*:[[:space:]]*"[^"]*"' "$state_file" | head -1 | sed 's/.*"\([^"]*\)"$/\1/')"
        ver_val="$(grep -o '"installedVersion"[[:space:]]*:[[:space:]]*"[^"]*"' "$state_file" | head -1 | sed 's/.*"\([^"]*\)"$/\1/')"
        if [ -n "$ep_val" ] && [ -f "$(atlas_install_root)/versions/$ver_val/$ep_val" ]; then
            has_entrypoint=true
        fi
    fi
    if [ "$has_entrypoint" != "true" ]; then
        download_runtime_from_github
    fi
fi

log_step "Installing RTK (optional, 60-90% token savings)"
ensure_rtk

log_step "Verifying the installation"
atlas doctor --install-only

new_version="$(current_atlas_version || true)"
printf "\n"
if [ -n "$current_version" ]; then
    printf "  %bUpdated: %s -> %s%b\n" "$GREEN" "$current_version" "$new_version" "$NC"
else
    printf "  %bInstalled: %s%b\n" "$GREEN" "$new_version" "$NC"
fi
printf "\n  Next steps:\n"
printf "    atlas up       # start gateway + cockpit (+ sidecars)\n"
printf "    atlas doctor   # verify the installation\n"
printf "    atlas          # launch the terminal UI\n\n"
