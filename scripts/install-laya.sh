#!/usr/bin/env bash
# Install laya-serve into its own venv for the gateway-managed `laya` service.
#
# Run as your normal user (not sudo). The venv goes on the internal disk:
# TCC blocks interactive shells (even root) from writing /opt/storage.
# The checkpoints are fetched later by laya-serve itself, which runs under
# the gateway's launchd job (it has /opt/storage access) and downloads into
# its HF_HOME on first start.
#
#   ./scripts/install-laya.sh            # install / upgrade
#   gw restart management                # pick up the new service
set -euo pipefail

VENV="${LAYA_VENV:-$HOME/.local/share/llmgateway/venv-laya}"
PY="${PYTHON:-/opt/homebrew/bin/python3.12}"
VERSION="${LAYA_VERSION:-0.3.20}"

if [[ ! -x "$VENV/bin/python" ]]; then
  echo "Creating venv at $VENV"
  mkdir -p "$(dirname "$VENV")"
  "$PY" -m venv "$VENV"
fi

"$VENV/bin/pip" install -q --upgrade pip
"$VENV/bin/pip" install -q "laya[serve]==$VERSION"

echo "Installed: $("$VENV/bin/pip" show laya | grep ^Version)"
echo "Binary:    $VENV/bin/laya-serve"
echo "Next: gw restart management  (first start downloads ~2.5 GB of checkpoints)"
