#!/usr/bin/env bash
# ============================================================
# LLM Gateway — Bootstrap Script
# ============================================================
# Fetches and runs the Python provisioning script.
# Safe to run on every boot. Idempotent.
#
# Usage:
#   curl -fsSL https://raw.githubusercontent.com/<owner>/LLMGateway/main/bootstrap.sh | bash
#   # or with options:
#   curl -fsSL ... | bash -s -- --launch --repo-dir ~/src/LLMGateway
#
# Options:
#   --launch       Also bring up Docker Compose after provisioning
#   --repo-dir     Path to LLMGateway repo (default: ~/src/LLMGateway)
#   --log-file     Path to log file (default: /tmp/llm-gateway-bootstrap.log)
#   --verbose      Print all output to terminal as well as log
# ============================================================

set -euo pipefail

# ── Defaults ─────────────────────────────────────────────────
REPO_DIR="${HOME}/src/LLMGateway"
LOG_FILE="/tmp/llm-gateway-bootstrap.log"
LAUNCH=false
VERBOSE=false
PROVISIONING_SCRIPT="provisioning/provision.py"

# ── Parse Arguments ──────────────────────────────────────────
while [[ $# -gt 0 ]]; do
    case "$1" in
        --launch)    LAUNCH=true; shift ;;
        --repo-dir)  REPO_DIR="$2"; shift 2 ;;
        --log-file)  LOG_FILE="$2"; shift 2 ;;
        --verbose)   VERBOSE=true; shift ;;
        -h|--help)
            echo "Usage: bootstrap.sh [--launch] [--repo-dir DIR] [--log-file FILE] [--verbose]"
            exit 0
            ;;
        *) echo "Unknown option: $1"; exit 1 ;;
    esac
done

# ── Logging ──────────────────────────────────────────────────
mkdir -p "$(dirname "$LOG_FILE")"
exec > >(tee -a "$LOG_FILE") 2>&1

log() {
    local level="$1"; shift
    local timestamp
    timestamp="$(date '+%Y-%m-%d %H:%M:%S')"
    echo "[$timestamp] [$level] $*"
    # Also log to macOS system log if logger is available
    if command -v logger &>/dev/null; then
        logger -t "llm-gateway-bootstrap" "[$level] $*"
    fi
}

log INFO "=========================================="
log INFO "LLM Gateway Bootstrap — starting"
log INFO "=========================================="
log INFO "Repo dir: $REPO_DIR"
log INFO "Log file: $LOG_FILE"
log INFO "Launch after provision: $LAUNCH"

# ── Detect Platform ──────────────────────────────────────────
OS="$(uname -s)"
ARCH="$(uname -m)"
log INFO "Platform: $OS / $ARCH"

if [[ "$OS" != "Darwin" ]]; then
    log WARN "This script is designed for macOS. Proceeding anyway..."
fi

# ── Ensure Xcode Command Line Tools ─────────────────────────
if ! xcode-select -p &>/dev/null; then
    log INFO "Installing Xcode Command Line Tools..."
    xcode-select --install 2>/dev/null || true
    # Wait for installation (user must click through the dialog)
    until xcode-select -p &>/dev/null; do
        log INFO "Waiting for Xcode CLT installation to complete..."
        sleep 10
    done
    log INFO "Xcode Command Line Tools installed"
else
    log INFO "Xcode Command Line Tools: already installed"
fi

# ── Ensure Homebrew ──────────────────────────────────────────
if ! command -v brew &>/dev/null; then
    log INFO "Installing Homebrew..."
    /bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"
    # Add brew to PATH for Apple Silicon
    if [[ "$ARCH" == "arm64" ]]; then
        eval "$(/opt/homebrew/bin/brew shellenv)"
        # Persist for future shells
        if ! grep -q 'brew shellenv' ~/.zprofile 2>/dev/null; then
            echo 'eval "$(/opt/homebrew/bin/brew shellenv)"' >> ~/.zprofile
        fi
    fi
    log INFO "Homebrew installed"
else
    log INFO "Homebrew: already installed ($(brew --version | head -1))"
    log INFO "Updating Homebrew..."
    brew update --quiet
fi

# ── Ensure Python 3.11+ ─────────────────────────────────────
REQUIRED_PYTHON_MINOR=11

get_python_cmd() {
    # Prefer python3, fall back to python
    for cmd in python3 python; do
        if command -v "$cmd" &>/dev/null; then
            local ver
            ver="$("$cmd" --version 2>&1 | grep -oE '[0-9]+\.[0-9]+')"
            local major minor
            major="$(echo "$ver" | cut -d. -f1)"
            minor="$(echo "$ver" | cut -d. -f2)"
            if [[ "$major" -eq 3 && "$minor" -ge "$REQUIRED_PYTHON_MINOR" ]]; then
                echo "$cmd"
                return 0
            fi
        fi
    done
    return 1
}

PYTHON_CMD=""
if PYTHON_CMD="$(get_python_cmd)"; then
    log INFO "Python: $($PYTHON_CMD --version) at $(which "$PYTHON_CMD")"
else
    log INFO "Installing Python 3 via Homebrew..."
    brew install python@3.12
    PYTHON_CMD="$(get_python_cmd)" || { log ERROR "Python installation failed"; exit 1; }
    log INFO "Python installed: $($PYTHON_CMD --version)"
fi

# ── Update pip ───────────────────────────────────────────────
log INFO "Updating pip..."
"$PYTHON_CMD" -m pip install --upgrade pip --quiet 2>/dev/null || \
    "$PYTHON_CMD" -m ensurepip --upgrade 2>/dev/null && \
    "$PYTHON_CMD" -m pip install --upgrade pip --quiet

# ── Ensure Git ───────────────────────────────────────────────
if ! command -v git &>/dev/null; then
    log INFO "Installing git via Homebrew..."
    brew install git
fi
log INFO "Git: $(git --version)"

# ── Clone or Update Repository ───────────────────────────────
if [[ -d "$REPO_DIR/.git" ]]; then
    log INFO "Repository exists at $REPO_DIR — pulling latest..."
    git -C "$REPO_DIR" pull --ff-only 2>/dev/null || \
        log WARN "Could not fast-forward pull (local changes?). Continuing with existing code."
elif [[ -d "$REPO_DIR" ]]; then
    log WARN "$REPO_DIR exists but is not a git repo. Using existing files."
else
    log INFO "Cloning repository to $REPO_DIR..."
    mkdir -p "$(dirname "$REPO_DIR")"
    # Replace with your actual repo URL:
    git clone https://github.com/<owner>/LLMGateway.git "$REPO_DIR" 2>/dev/null || {
        log WARN "Could not clone repo (URL not set?). Please clone manually."
        log WARN "Continuing without clone — provision.py must exist at $REPO_DIR/$PROVISIONING_SCRIPT"
    }
fi

# ── Hand Off to Python Provisioning Script ───────────────────
PROVISION_PATH="$REPO_DIR/$PROVISIONING_SCRIPT"

if [[ ! -f "$PROVISION_PATH" ]]; then
    log ERROR "Provisioning script not found at: $PROVISION_PATH"
    log ERROR "Please ensure the LLMGateway repository is cloned to $REPO_DIR"
    exit 1
fi

log INFO "Handing off to Python provisioning script..."

PROVISION_ARGS=("--repo-dir" "$REPO_DIR" "--log-file" "$LOG_FILE")
if $LAUNCH; then
    PROVISION_ARGS+=("--launch")
fi
if $VERBOSE; then
    PROVISION_ARGS+=("--verbose")
fi

"$PYTHON_CMD" "$PROVISION_PATH" "${PROVISION_ARGS[@]}"
EXIT_CODE=$?

if [[ $EXIT_CODE -eq 0 ]]; then
    log INFO "=========================================="
    log INFO "LLM Gateway Bootstrap — complete"
    log INFO "=========================================="
else
    log ERROR "Provisioning exited with code $EXIT_CODE"
    exit $EXIT_CODE
fi
