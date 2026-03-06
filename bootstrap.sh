#!/usr/bin/env bash
# =============================================================================
# LLM Gateway — Bootstrap
# =============================================================================
# Ensures Python 3.11+ and pip dependencies are present, then launches
# the LLM Gateway service (web UI + service manager + provisioning).
#
# Run from within the LLMGateway repository:
#   ./bootstrap.sh                # start the gateway service
#   ./bootstrap.sh --setup        # run provisioning steps only (headless)
#   ./bootstrap.sh --status       # check component status (no changes)
# =============================================================================

set -euo pipefail

# ── Locate repository root (this script lives in the repo root) ───────────────
if [[ -n "${BASH_SOURCE[0]:-}" && "${BASH_SOURCE[0]}" != "/dev/stdin" ]]; then
    REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
else
    REPO_DIR="$(pwd)"
fi
GATEWAY_SCRIPT="$REPO_DIR/scripts/llmgateway.py"
REQUIREMENTS="$REPO_DIR/requirements.txt"
REQUIRED_MINOR=11

# ── Helpers ───────────────────────────────────────────────────────────────────
die()  { echo "ERROR: $*" >&2; exit 1; }
info() { echo "[bootstrap] $*"; }

# ── Platform ──────────────────────────────────────────────────────────────────
if [[ "$(uname -s)" != "Darwin" ]]; then
    info "WARNING: Designed for macOS — proceeding on $(uname -s) anyway"
fi
info "Platform: $(uname -s)/$(uname -m)"

# ── Xcode Command Line Tools ──────────────────────────────────────────────────
if ! xcode-select -p &>/dev/null; then
    info "Xcode Command Line Tools not found — triggering installer..."
    info "(A dialog will appear — click Install and wait for it to complete)"
    xcode-select --install 2>/dev/null || true
    until xcode-select -p &>/dev/null; do
        info "Waiting for Xcode CLT installation to complete..."
        sleep 10
    done
fi
info "Xcode CLT: $(xcode-select -p)"

# ── Homebrew ──────────────────────────────────────────────────────────────────
if ! command -v brew &>/dev/null; then
    info "Homebrew not found — installing..."
    /bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"
    if [[ "$(uname -m)" == "arm64" ]] && [[ -x "/opt/homebrew/bin/brew" ]]; then
        eval "$(/opt/homebrew/bin/brew shellenv)"
    fi
fi
brew update --quiet 2>/dev/null || info "brew update failed (non-fatal)"
info "Homebrew: $(brew --version | head -1)"

# ── Python 3.11+ ──────────────────────────────────────────────────────────────
find_python() {
    for cmd in python3.13 python3.12 python3.11 python3 python; do
        command -v "$cmd" &>/dev/null || continue
        major=$("$cmd" -c "import sys; print(sys.version_info.major)" 2>/dev/null) || continue
        minor=$("$cmd" -c "import sys; print(sys.version_info.minor)" 2>/dev/null) || continue
        [[ "$major" -eq 3 && "$minor" -ge "$REQUIRED_MINOR" ]] && echo "$cmd" && return 0
    done
    return 1
}

if ! PYTHON="$(find_python 2>/dev/null)"; then
    info "Python 3.$REQUIRED_MINOR+ not found — installing python@3.12 via Homebrew..."
    brew install python@3.12
    PYTHON="$(find_python 2>/dev/null)" || die "Python installation failed"
fi
info "Python: $("$PYTHON" --version) at $(command -v "$PYTHON")"

# ── pip + dependencies ────────────────────────────────────────────────────────
info "Ensuring pip is up to date..."
"$PYTHON" -m pip install --upgrade pip --quiet 2>/dev/null \
    || "$PYTHON" -m ensurepip --upgrade 2>/dev/null || true
"$PYTHON" -m pip install --upgrade pip --quiet 2>/dev/null \
    || info "pip update failed (non-fatal)"

if [[ -f "$REQUIREMENTS" ]]; then
    info "Installing Python dependencies..."
    "$PYTHON" -m pip install -r "$REQUIREMENTS" --quiet 2>/dev/null \
        || "$PYTHON" -m pip install -r "$REQUIREMENTS" \
        || die "Failed to install Python dependencies"
fi

# ── Launch ────────────────────────────────────────────────────────────────────
[[ -f "$GATEWAY_SCRIPT" ]] \
    || die "Gateway script not found: $GATEWAY_SCRIPT
Ensure you are running bootstrap.sh from within the LLMGateway repository."

info "Launching LLM Gateway..."
exec "$PYTHON" "$GATEWAY_SCRIPT" "$@"
