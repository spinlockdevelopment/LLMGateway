#!/usr/bin/env bash
# =============================================================================
# LLM Gateway — Bootstrap Script
# =============================================================================
# Ensures all OS-level prerequisites are installed, then optionally hands off
# to the Python setup script for application provisioning.
#
# Flow:
#   Phase 1 — Check which tools are already installed (brew, git, python, docker)
#   Phase 2 — If anything is missing, prompt (or auto) then re-exec with sudo
#   Phase 3 — Install only the missing components (unattended)
#   Phase 4 — Ensure the repo is cloned locally or pull latest
#   Phase 5 — Create a virtual environment and install Python dependencies
#   Phase 6 — Prompt (or auto) to hand off to the Python setup script
#
# Modes:
#   ./bootstrap-llmgateway.sh              # interactive — ask before install,
#                                          #   ask before launching setup
#   ./bootstrap-llmgateway.sh --install    # auto-install missing deps,
#                                          #   ask before launching setup
#   ./bootstrap-llmgateway.sh --launch     # auto-install missing deps AND
#                                          #   auto-launch setup (no prompts)
#
# Pass-through flags (forwarded to setup script):
#   --status     status check only (no changes)
#   --verbose    debug-level output
#
# Remote (no local clone yet):
#   curl -fsSL https://raw.githubusercontent.com/spinlockdevelopment/LLMGateway/main/bootstrap-llmgateway.sh | bash
# =============================================================================

set -euo pipefail

# ── Helpers ──────────────────────────────────────────────────────────────────

die()  { echo "ERROR: $*" >&2; exit 1; }
info() { echo "[bootstrap] $*"; }
warn() { echo "[bootstrap] WARNING: $*" >&2; }

prompt_yes_no() {
  # Usage: prompt_yes_no "Question?" [y|n]
  # Returns 0 for yes, 1 for no.  Default is first arg after question (y if omitted).
  local question="$1"
  local default="${2:-y}"
  local suffix
  if [[ "$default" == "y" ]]; then
    suffix=" [Y/n]: "
  else
    suffix=" [y/N]: "
  fi
  # Non-interactive (piped stdin) → use default
  if [[ ! -t 0 ]]; then
    [[ "$default" == "y" ]]
    return
  fi
  local answer
  read -r -p "$question$suffix" answer </dev/tty
  answer="${answer:-$default}"
  [[ "$answer" =~ ^[Yy] ]]
}

LLMGATEWAY_REPO_URL="https://github.com/spinlockdevelopment/LLMGateway.git"
CLONE_DIR="${HOME}/src/LLMGateway"
REQUIRED_PYTHON_MINOR=11

# Canonicalize the script path so re-execs (sudo, privilege drop) always resolve.
# When piped via curl, BASH_SOURCE is empty/"-" so we skip canonicalization.
SCRIPT_ABS=""
if [[ -n "${BASH_SOURCE[0]:-}" && "${BASH_SOURCE[0]}" != "-" && "${BASH_SOURCE[0]}" != "/dev/stdin" ]]; then
  SCRIPT_ABS="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/$(basename "${BASH_SOURCE[0]}")"
fi

# ── Argument parsing ────────────────────────────────────────────────────────
# Bootstrap-specific flags are consumed here.  Everything else is forwarded
# to the Python setup script in Phase 6.

AUTO_INSTALL=false   # --install or --launch: skip "install missing deps?" prompt
AUTO_LAUNCH=false    # --launch: skip "launch setup?" prompt
SETUP_ARGS=()        # args forwarded to setup-llmgateway.py

for arg in "$@"; do
  case "$arg" in
    --install)
      AUTO_INSTALL=true
      ;;
    --launch)
      AUTO_INSTALL=true
      AUTO_LAUNCH=true
      ;;
    *)
      SETUP_ARGS+=("$arg")
      ;;
  esac
done

# ── Tool-detection functions ─────────────────────────────────────────────────
# Each returns 0 if the tool is on PATH and usable, 1 if missing.

has_brew() {
  command -v brew &>/dev/null
}

has_git() {
  command -v git &>/dev/null
}

has_docker() {
  command -v docker &>/dev/null
}

# find_python: locate a Python >= 3.$REQUIRED_PYTHON_MINOR.
# Prints the command name on success; returns 1 if none qualifies.
find_python() {
  for cmd in python3.13 python3.12 python3.11 python3 python; do
    command -v "$cmd" &>/dev/null || continue
    local major minor
    major=$("$cmd" -c "import sys; print(sys.version_info.major)" 2>/dev/null) || continue
    minor=$("$cmd" -c "import sys; print(sys.version_info.minor)" 2>/dev/null) || continue
    if [[ "$major" -eq 3 && "$minor" -ge "$REQUIRED_PYTHON_MINOR" ]]; then
      echo "$cmd"
      return 0
    fi
  done
  return 1
}

has_python() {
  find_python &>/dev/null
}

# Add Homebrew to PATH if it exists but hasn't been sourced yet.
# Apple Silicon: /opt/homebrew    Intel: /usr/local
_ensure_brew_path() {
  if ! command -v brew &>/dev/null; then
    if [[ -x "/opt/homebrew/bin/brew" ]]; then
      eval "$(/opt/homebrew/bin/brew shellenv)"
    elif [[ -x "/usr/local/bin/brew" ]]; then
      eval "$(/usr/local/bin/brew shellenv)"
    fi
  fi
}

# =============================================================================
# Phase 1 — Check what is already installed
# =============================================================================

_ensure_brew_path

MISSING=()
has_brew   || MISSING+=(homebrew)
has_git    || MISSING+=(git)
has_python || MISSING+=(python)
has_docker || MISSING+=(docker)

if [[ ${#MISSING[@]} -eq 0 ]]; then
  info "All prerequisites found (brew, git, python, docker) — no sudo needed."
fi

# =============================================================================
# Phase 2 — If anything is missing, prompt then re-exec with sudo
# =============================================================================
# Tools like Xcode CLT and Docker Desktop need elevated privileges to install.
# Re-exec the whole script so all installs happen under one sudo session.

if [[ ${#MISSING[@]} -gt 0 ]]; then
  info "Missing tools: ${MISSING[*]}"

  # ── Interactive gate: ask the user before installing ──────────────────────
  # Skipped when --install or --launch was given, or when already running as
  # root (meaning we've already been through the prompt and re-exec'd).
  if [[ "$AUTO_INSTALL" == "false" && $EUID -ne 0 ]]; then
    info ""
    info "The following dependencies need to be installed:"
    for tool in "${MISSING[@]}"; do
      info "  • $tool"
    done
    info ""
    info "Installation requires elevated (sudo) privileges."
    info ""
    if ! prompt_yes_no "  Install missing dependencies?"; then
      info ""
      info "Exiting. Install the missing tools manually and re-run:"
      if [[ -n "$SCRIPT_ABS" ]]; then
        info "  $SCRIPT_ABS"
      else
        info "  curl -fsSL https://raw.githubusercontent.com/spinlockdevelopment/LLMGateway/main/bootstrap-llmgateway.sh | bash"
      fi
      exit 0
    fi
    info ""
  fi

  # When piped via curl, $0 is "bash" or "-" — we need a real file path for
  # the sudo re-exec.  Save the script to a temp file so sudo can re-run it.
  if [[ $EUID -ne 0 && -z "$SCRIPT_ABS" ]]; then
    TEMP_SCRIPT="$(mktemp /tmp/bootstrap-llmgateway.XXXXXX.sh)"
    # In the curl-pipe case the script has already been read into memory by
    # bash, so we download a fresh copy for the sudo re-exec.
    curl -fsSL "https://raw.githubusercontent.com/spinlockdevelopment/LLMGateway/main/bootstrap-llmgateway.sh" \
      > "$TEMP_SCRIPT" 2>/dev/null \
      || die "Failed to download bootstrap script for sudo re-exec"
    chmod +x "$TEMP_SCRIPT"
    SCRIPT_ABS="$TEMP_SCRIPT"
  fi

  if [[ $EUID -ne 0 ]]; then
    info "Elevated privileges needed — re-running with sudo..."
    exec sudo --preserve-env=HOME,USER bash "${SCRIPT_ABS:-$0}" "$@"
  fi

  # We're now running as root.
  # REAL_USER is the actual logged-in user (for commands that refuse root).
  REAL_USER="${SUDO_USER:-}"
  if [[ -z "$REAL_USER" || "$REAL_USER" == "root" ]]; then
    die "Cannot determine the real user. Run this script as your normal user account (not as root directly)."
  fi
  info "Running as root (real user: $REAL_USER)"
  info ""

  # ===========================================================================
  # Phase 3 — Install only what is missing (unattended)
  # ===========================================================================

  # ── 3a. Xcode Command Line Tools ──────────────────────────────────────────
  # Required by Homebrew and any compilation. We use the headless approach:
  # create a trigger file so softwareupdate can find CLT, then install silently.
  if ! xcode-select -p &>/dev/null; then
    info "Installing Xcode Command Line Tools (headless)..."

    # Create the trigger file that makes softwareupdate list CLT
    touch /tmp/.com.apple.dt.CommandLineTools.installondemand.in-progress

    # Find the CLT package name from softwareupdate
    CLT_PACKAGE=$(softwareupdate -l 2>/dev/null \
      | grep -B 1 -E "Command Line Tools" \
      | awk -F'\\* ' '/\\*/{print $2}' \
      | head -1)

    if [[ -n "$CLT_PACKAGE" ]]; then
      info "Found package: $CLT_PACKAGE"
      softwareupdate -i "$CLT_PACKAGE" --verbose 2>&1 | tail -5
    else
      warn "Could not find CLT in softwareupdate — falling back to xcode-select..."
      xcode-select --install 2>/dev/null || true
      until xcode-select -p &>/dev/null; do
        info "Waiting for Xcode CLT installation..."
        sleep 10
      done
    fi

    rm -f /tmp/.com.apple.dt.CommandLineTools.installondemand.in-progress

    # Accept the Xcode/CLT license agreement automatically.
    # xcodebuild -license accept works for both full Xcode and CLT-only installs.
    if command -v xcodebuild &>/dev/null; then
      xcodebuild -license accept 2>/dev/null || true
    fi

    info "Xcode CLT: installed"
  fi

  # ── 3b. Homebrew ──────────────────────────────────────────────────────────
  # Homebrew must NOT run as root — run the installer as the real user.
  # NONINTERACTIVE=1 suppresses all prompts.
  _ensure_brew_path
  if ! has_brew; then
    info "Installing Homebrew (non-interactive)..."
    sudo -u "$REAL_USER" env NONINTERACTIVE=1 \
      /bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"
    _ensure_brew_path
    has_brew || die "Homebrew installation failed"
    info "Homebrew: installed"
  fi

  # brew commands must run as the real user (brew refuses root)
  BREW="sudo -u $REAL_USER brew"
  $BREW update --quiet 2>/dev/null || true

  # ── 3c. Git ───────────────────────────────────────────────────────────────
  if ! has_git; then
    info "Installing Git via Homebrew..."
    $BREW install git
    info "Git: $(git --version)"
  fi

  # ── 3d. Python 3.11+ ─────────────────────────────────────────────────────
  if ! has_python; then
    info "Installing Python 3.12 via Homebrew..."
    $BREW install python@3.12
    has_python || die "Python installation failed"
    info "Python: $(find_python) installed"
  fi

  # ── 3e. Docker Desktop ───────────────────────────────────────────────────
  # Install via Homebrew cask (handles DMG download, mount, copy, unmount).
  # Then run the install binary to accept the license and configure privileged
  # helper components — all without GUI prompts.
  if ! has_docker; then
    info "Installing Docker Desktop via Homebrew cask..."
    $BREW install --cask docker

    # Accept the Docker license and install privileged components headlessly.
    # The install binary lives inside Docker.app after the cask copies it.
    DOCKER_INSTALL="/Applications/Docker.app/Contents/MacOS/install"
    if [[ -x "$DOCKER_INSTALL" ]]; then
      info "Accepting Docker Desktop license and configuring components..."
      "$DOCKER_INSTALL" --accept-license --user="$REAL_USER" 2>/dev/null || true
    else
      warn "Docker install binary not found at $DOCKER_INSTALL"
      warn "You may need to open Docker Desktop manually to accept the license."
    fi

    # Start Docker Desktop in the background (as the real user)
    info "Starting Docker Desktop..."
    sudo -u "$REAL_USER" open -a Docker 2>/dev/null || true

    # Wait for the daemon to become responsive (up to ~2 minutes).
    # Docker Desktop creates a socket owned by the real user's group,
    # so we check as the real user to avoid socket permission issues.
    info "Waiting for Docker daemon to start (this may take a minute)..."
    DOCKER_WAIT=120
    DOCKER_POLL=5
    for (( elapsed=0; elapsed<DOCKER_WAIT; elapsed+=DOCKER_POLL )); do
      if sudo -u "$REAL_USER" docker info &>/dev/null; then
        info "Docker daemon: ready (after ${elapsed}s)"
        break
      fi
      sleep $DOCKER_POLL
      if (( elapsed > 0 && elapsed % 30 == 0 )); then
        info "Still waiting for Docker (${elapsed}s elapsed)..."
      fi
    done

    if ! sudo -u "$REAL_USER" docker info &>/dev/null; then
      warn "Docker daemon did not respond within ${DOCKER_WAIT}s."
      warn "Start Docker Desktop manually after bootstrap completes."
    fi

    info "Docker Desktop: installed"
  fi

  info ""
  info "All missing tools installed successfully."

  # ── Drop back to the real user for Phases 4–6 ────────────────────────────
  # Phases 4–6 (repo, venv, setup) must NOT run as root because:
  #   - Files created as root have wrong ownership
  #   - The venv python path baked into launchd plist would be root's
  #   - launchd agent would install to /var/root/ instead of ~/
  # Re-exec as the original user now that installations are complete.
  info "Dropping privileges — re-running as $REAL_USER..."
  exec sudo -u "$REAL_USER" bash "${SCRIPT_ABS:-$0}" "$@"
fi

# =============================================================================
# Phase 4 — Ensure the repository is present and up to date
# =============================================================================

# Detect if we're running from inside the repo already
REPO_DIR=""
if [[ -n "${BASH_SOURCE[0]:-}" && "${BASH_SOURCE[0]}" != "-" && "${BASH_SOURCE[0]}" != "/dev/stdin" ]]; then
  SCRIPT_PATH="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
  if [[ -f "$SCRIPT_PATH/scripts/setup-llmgateway.py" ]]; then
    REPO_DIR="$SCRIPT_PATH"
  fi
fi

if [[ -z "$REPO_DIR" ]]; then
  # Not running from inside the repo — check the expected clone location
  if [[ -d "$CLONE_DIR/.git" ]]; then
    info "Repository found at $CLONE_DIR — pulling latest..."
    git -C "$CLONE_DIR" pull --ff-only 2>/dev/null \
      || warn "git pull failed (non-fatal) — using existing checkout"
    REPO_DIR="$CLONE_DIR"
  else
    info "Repository not found — cloning into $CLONE_DIR ..."
    mkdir -p "$(dirname "$CLONE_DIR")"
    git clone "$LLMGATEWAY_REPO_URL" "$CLONE_DIR"
    REPO_DIR="$CLONE_DIR"
  fi

  # Re-exec from the cloned repo so all paths resolve correctly
  info "Re-running bootstrap from $REPO_DIR ..."
  exec bash "$REPO_DIR/bootstrap-llmgateway.sh" "$@"
fi

# If we ARE in the repo already, pull latest (fast-forward only, non-fatal)
if [[ -d "$REPO_DIR/.git" ]]; then
  info "Pulling latest changes..."
  git -C "$REPO_DIR" pull --ff-only 2>/dev/null \
    || warn "git pull failed (non-fatal) — continuing with current checkout"
fi

# =============================================================================
# Phase 5 — Create virtual environment and install Python dependencies
# =============================================================================

REQUIREMENTS="$REPO_DIR/requirements.txt"
VENV_DIR="$REPO_DIR/.venv"

# Platform info
if [[ "$(uname -s)" != "Darwin" ]]; then
  warn "This project is designed for macOS — proceeding on $(uname -s) anyway"
fi
info "Platform: $(uname -s)/$(uname -m)"

# Locate Python (Phase 3 ensures it's available)
PYTHON="$(find_python 2>/dev/null)" || die "Python 3.$REQUIRED_PYTHON_MINOR+ not found"
info "Python: $("$PYTHON" --version) at $(command -v "$PYTHON")"

# Create the virtual environment if it doesn't exist yet
if [[ ! -d "$VENV_DIR" ]]; then
  info "Creating virtual environment at $VENV_DIR ..."
  "$PYTHON" -m venv "$VENV_DIR"
fi

# Use the venv's Python for all subsequent operations
VENV_PYTHON="$VENV_DIR/bin/python3"
info "Using venv Python: $VENV_PYTHON"

# Ensure pip is current inside the venv
info "Upgrading pip in venv..."
"$VENV_PYTHON" -m pip install --upgrade pip --quiet 2>/dev/null \
  || "$VENV_PYTHON" -m ensurepip --upgrade 2>/dev/null || true
"$VENV_PYTHON" -m pip install --upgrade pip --quiet 2>/dev/null || true

# Install project dependencies into the venv
if [[ -f "$REQUIREMENTS" ]]; then
  info "Installing Python dependencies into venv..."
  "$VENV_PYTHON" -m pip install -r "$REQUIREMENTS" --quiet 2>/dev/null \
    || "$VENV_PYTHON" -m pip install -r "$REQUIREMENTS" \
    || die "Failed to install Python dependencies"
fi

# =============================================================================
# Phase 6 — Hand off to the Python setup script
# =============================================================================
# Bootstrap's job is done (OS tools + venv). The setup script handles all
# application-level provisioning: Docker stack, Node/Claude Code, Ollama,
# and installing + starting the management console.

SETUP_SCRIPT="$REPO_DIR/scripts/setup-llmgateway.py"
[[ -f "$SETUP_SCRIPT" ]] \
  || die "Setup script not found: $SETUP_SCRIPT"

info ""
info "Prerequisites ready."
info ""

# ── Launch gate: ask the user before launching setup ─────────────────────────
# Skipped when --launch was given.
if [[ "$AUTO_LAUNCH" == "false" ]]; then
  info "======================================================"
  info "  Ready to launch the Python setup script."
  info ""
  info "  The setup script provisions application components"
  info "  (Node.js, Claude Code, Docker stack, Ollama, etc.)"
  info "  and installs the management console."
  info ""
  info "  It should be run as a STANDARD user account."
  if [[ $EUID -eq 0 ]]; then
    info "  ⚠  You are currently running as root/admin."
  else
    info "  ✓  Current user: $(whoami)"
  fi
  info "======================================================"
  info ""
  if ! prompt_yes_no "  Launch setup now?"; then
    info ""
    info "No problem. Run setup whenever you're ready:"
    info ""
    info "  cd $REPO_DIR"
    info "  $VENV_PYTHON scripts/setup-llmgateway.py"
    info ""
    info "Options:"
    info "  $VENV_PYTHON scripts/setup-llmgateway.py --status   # check status only"
    info "  $VENV_PYTHON scripts/setup-llmgateway.py --verbose  # debug output"
    info ""
    exit 0
  fi
  info ""
fi

info "Launching setup..."
info ""
# ${SETUP_ARGS[@]+...} guards against "unbound variable" on empty arrays in Bash 3.x
exec "$VENV_PYTHON" "$SETUP_SCRIPT" ${SETUP_ARGS[@]+"${SETUP_ARGS[@]}"}
