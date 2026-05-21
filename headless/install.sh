#!/bin/bash
#
# install.sh — wire up the headless shim on this Mac.
#
#   ./install.sh          # install: sudoers entry + boot LaunchDaemon
#   ./install.sh uninstall
#
# Idempotent. Re-running re-stamps the plist/sudoers from the templates.

set -euo pipefail

DIR="$(cd "$(dirname "$0")" && pwd)"
USER_NAME="$(id -un)"
SHIM="$DIR/shim.py"
CTL="$DIR/headless_ctl.sh"
LABEL="com.local.headless-shim"
DAEMON="/Library/LaunchDaemons/$LABEL.plist"
SUDOERS="/etc/sudoers.d/headless-shim"

# Resolve the configured log dir (with ~ expanded).
LOGDIR="$(/usr/bin/python3 -c 'import json,os;print(os.path.expanduser(json.load(open("'"$DIR"'/config.json"))["log_dir"]))')"

stamp() { sed -e "s#__USER__#$USER_NAME#g" -e "s#__SHIM__#$SHIM#g" \
              -e "s#__CTL__#$CTL#g"   -e "s#__DIR__#$DIR#g" \
              -e "s#__LOGDIR__#$LOGDIR#g" "$1"; }

if [ "${1:-install}" = "uninstall" ]; then
  echo "==> uninstalling"
  sudo launchctl bootout system "$DAEMON" 2>/dev/null || true
  sudo rm -f "$DAEMON" "$SUDOERS"
  echo "done. (config + logs left in place)"
  exit 0
fi

echo "==> user=$USER_NAME  dir=$DIR  logdir=$LOGDIR"
mkdir -p "$LOGDIR"
chmod +x "$SHIM" "$CTL"

echo "==> installing sudoers allowlist -> $SUDOERS"
stamp "$DIR/sudoers.d/headless-shim" | sudo tee "$SUDOERS" >/dev/null
sudo chown root:wheel "$SUDOERS"; sudo chmod 0440 "$SUDOERS"
sudo visudo -cf "$SUDOERS"   # abort if syntax is wrong

echo "==> installing LaunchDaemon -> $DAEMON"
stamp "$DIR/$LABEL.plist" | sudo tee "$DAEMON" >/dev/null
sudo chown root:wheel "$DAEMON"; sudo chmod 0644 "$DAEMON"
sudo launchctl bootout system "$DAEMON" 2>/dev/null || true
sudo launchctl bootstrap system "$DAEMON"
sudo launchctl enable "system/$LABEL"

PORT="$(/usr/bin/python3 -c 'import json;print(json.load(open("'"$DIR"'/config.json"))["port"])')"
echo "==> done. shim should be live shortly on:"
echo "    http://127.0.0.1:$PORT   and over tailscale at http://<this-host>:$PORT"
echo "    logs: $LOGDIR/shim.log"
echo "    sanity: sudo -n $CTL status"
