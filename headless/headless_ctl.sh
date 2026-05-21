#!/bin/bash
#
# headless_ctl.sh — privileged helper for the headless shim.
#
# Invoked only as:   sudo -n /path/to/headless_ctl.sh <enter|exit|status>
# Allowlisted (NOPASSWD) in /etc/sudoers.d/headless-shim so the shim, running
# as the regular user, can toggle headless mode without an interactive password.
#
# "enter": stop + disable the RAM-hungry stack (Docker Desktop, the LLM Gateway
#          management agent, ollama) so the box runs only tailscaled + this shim
#          + llama-server. Reversible.
# "exit" : re-enable that stack and reboot — the Mac comes back up to the GUI.
# "status": print what's currently disabled/running.
#
# Conservative on purpose: we do NOT touch WindowServer or auto-login here, to
# avoid locking anyone out of the local console while this is still new.

set -uo pipefail

# Who triggered the sudo? We act on that user's per-user services + settings.
USER_NAME="${SUDO_USER:-$(stat -f%Su /dev/console)}"
USER_UID="$(id -u "$USER_NAME")"
USER_HOME="$(eval echo "~$USER_NAME")"

MARKER="$USER_HOME/.headless_mode"
GATEWAY_PLIST="$USER_HOME/Library/LaunchAgents/com.local.llm-gateway.plist"
OLLAMA_PLIST="$USER_HOME/Library/LaunchAgents/homebrew.mxcl.ollama.plist"
DOCKER_SETTINGS="$USER_HOME/Library/Group Containers/group.com.docker/settings-store.json"

log() { echo "[headless_ctl] $*"; }

# Run a command in the target user's GUI/Aqua session (needed for launchctl
# gui-domain agents and `osascript`).
as_user() { launchctl asuser "$USER_UID" sudo -u "$USER_NAME" "$@"; }

# Flip the Docker Desktop AutoStart flag without needing jq.
set_docker_autostart() { # $1 = true|false
  [ -f "$DOCKER_SETTINGS" ] || { log "docker settings not found, skipping"; return; }
  /usr/bin/python3 - "$DOCKER_SETTINGS" "$1" <<'PY'
import json, sys
path, val = sys.argv[1], sys.argv[2] == "true"
try:
    d = json.load(open(path))
except Exception as e:
    print("could not read docker settings:", e); sys.exit(0)
d["AutoStart"] = val
json.dump(d, open(path, "w"), indent=2)
print("docker AutoStart =", val)
PY
}

unload_agent() { # $1 = plist path, $2 = label
  local plist="$1" label="$2"
  [ -f "$plist" ] || { log "$label: no plist, skipping"; return; }
  as_user launchctl bootout "gui/$USER_UID/$label" 2>/dev/null \
    && log "$label: booted out" || log "$label: not loaded"
  as_user launchctl disable "gui/$USER_UID/$label" 2>/dev/null \
    && log "$label: disabled (won't auto-start)"
}

enable_agent() { # $1 = plist path, $2 = label
  local plist="$1" label="$2"
  [ -f "$plist" ] || return
  as_user launchctl enable "gui/$USER_UID/$label" 2>/dev/null \
    && log "$label: enabled"
  as_user launchctl bootstrap "gui/$USER_UID" "$plist" 2>/dev/null \
    && log "$label: bootstrapped" || true
}

cmd_enter() {
  log "entering headless mode as $USER_NAME (uid $USER_UID)"

  # 1. Docker Desktop: quit the app + its VM, disable autostart.
  set_docker_autostart false
  as_user osascript -e 'quit app "Docker"' 2>/dev/null && log "Docker app quit" || true
  /usr/bin/pkill -f 'Docker Desktop' 2>/dev/null && log "Docker Desktop killed" || true
  /usr/bin/pkill -f 'com.docker.virtualization' 2>/dev/null || true
  /usr/bin/pkill -f 'com.docker.backend' 2>/dev/null || true

  # 2. LLM Gateway management agent + ollama.
  unload_agent "$GATEWAY_PLIST" "com.local.llm-gateway"
  unload_agent "$OLLAMA_PLIST"  "homebrew.mxcl.ollama"
  /usr/bin/pkill -f 'ollama' 2>/dev/null || true

  # 3. Marker.
  /usr/bin/touch "$MARKER"; /usr/sbin/chown "$USER_NAME" "$MARKER"
  log "headless mode ACTIVE — only tailscaled + shim + llama remain"
  cmd_status
}

cmd_exit() {
  log "exiting headless mode — re-enabling stack, then rebooting to GUI"
  set_docker_autostart true
  enable_agent "$GATEWAY_PLIST" "com.local.llm-gateway"
  enable_agent "$OLLAMA_PLIST"  "homebrew.mxcl.ollama"
  /bin/rm -f "$MARKER"
  log "rebooting now…"
  /sbin/shutdown -r now
}

cmd_status() {
  if [ -f "$MARKER" ]; then echo "headless: ACTIVE"; else echo "headless: off"; fi
  if pgrep -qf 'com.docker.virtualization' || pgrep -qf 'Docker Desktop'; then
    echo "docker: running"; else echo "docker: stopped"; fi
  if pgrep -qf 'ollama serve' >/dev/null 2>&1; then echo "ollama: running"; else echo "ollama: stopped"; fi
  if pgrep -qf 'llmgateway' >/dev/null 2>&1; then echo "llm-gateway: running"; else echo "llm-gateway: stopped"; fi
}

case "${1:-}" in
  enter)  cmd_enter ;;
  exit)   cmd_exit ;;
  status) cmd_status ;;
  *) echo "usage: $0 {enter|exit|status}" >&2; exit 2 ;;
esac
