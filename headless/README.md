# headless shim

A deliberately tiny control plane for running `llama.cpp` on a **headless Mac**.
The point of "headless mode" is to free as much RAM as possible for the model:
shut down Docker Desktop, the LLM Gateway management stack, and ollama, leaving
only `tailscaled` (SSH-over-Tailscale), this shim, and `llama-server` running.

The shim itself is **stdlib-only Python** (no FastAPI/uvicorn/psutil) so it adds
almost nothing to resident memory. Everything is driven from one HTML page.

```
┌─ tailscale (system daemon, SSH) ─┐
│  headless-shim  :8088  ───────────┼──> launches/stops llama-server :8080…
│  └─ single-page UI + REST          │    pulls models via `docker model pull`
└────────────────────────────────────┘    toggles headless mode + reboot
```

## Files

| file | role |
|------|------|
| `shim.py` | the service: REST API + serves `index.html`. Stdlib only. |
| `index.html` | single-page control + metrics UI (vanilla JS, polls every 3 s). |
| `config.json` | paths, listen port, default `llama-server` args. |
| `headless_ctl.sh` | **privileged** helper (`enter`/`exit`/`status`). Invoked only via `sudo -n`. |
| `com.local.headless-shim.plist` | LaunchDaemon — starts the shim at boot, no GUI login needed. |
| `sudoers.d/headless-shim` | NOPASSWD allowlist for the helper — the entire privileged surface. |
| `install.sh` | stamps + installs the plist and sudoers entry. |

## Install

```bash
cd headless
./install.sh                 # installs sudoers entry + boot LaunchDaemon (asks for sudo)
sudo -n ./headless_ctl.sh status   # sanity check the allowlist works
```

The shim then runs at boot as your user (via the daemon's `UserName` key, so it
works with no one logged in) and listens on `:8088`:

- locally: <http://127.0.0.1:8088>
- over Tailscale: `http://<this-host>:8088`

`./install.sh uninstall` removes the daemon and sudoers entry (config + logs stay).

## REST API

| method | path | body / query | does |
|--------|------|--------------|------|
| GET | `/api/metrics` | | host mem/cpu/disk + tailscale + instances + headless + pull status |
| GET | `/api/models` | | local models (`docker model list`) |
| GET | `/api/instances` | | running llama-server instances |
| GET | `/api/instance/health` | `?port=` | proxy llama-server `/health` |
| GET | `/api/logs` | `?name=shim\|pull\|llama-<port>&lines=` | tail a log |
| GET | `/api/tailscale` | | `tailscale status --json` summary |
| POST | `/api/llama/start` | `{model, args:{"--port":...}}` | launch an instance |
| POST | `/api/llama/stop` | `{port}` | SIGTERM→SIGKILL the process group |
| POST | `/api/llama/restart` | `{port}` | stop + start with same args |
| POST | `/api/models/pull` | `{model}` | background `docker model pull` |
| POST | `/api/headless/enter` | | free RAM (stop/disable Docker, gateway, ollama) |
| POST | `/api/headless/exit` | | re-enable that stack and **reboot to GUI** |

Models are docker-model bundles; the shim resolves a name → GGUF blob via
`docker model inspect` + the OCI manifest, then runs `llama-server --model <blob>`.

## Headless mode

`enter` (reversible):
- quits Docker Desktop + its VM and sets `AutoStart=false`,
- `launchctl bootout` + `disable` the LLM Gateway agent (`com.local.llm-gateway`) and ollama,
- writes the marker `~/.headless_mode`.

`exit`:
- re-enables Docker autostart and both agents,
- removes the marker,
- `shutdown -r now` — the box reboots and comes back to the normal GUI.

### Privilege

The shim runs as your user. The only thing it can do as root is run
`headless_ctl.sh {enter,exit,status}`, pinned by absolute path in
`/etc/sudoers.d/headless-shim`. Nothing else in the REST surface is privileged.

### Deliberately conservative

This does **not** touch WindowServer or auto-login — the Mac still boots to a
login window, it just doesn't auto-start the heavy stack. That keeps the local
console as a recovery path while this is new. Re-enabling GUI auto-login (if you
ever disable it) needs a password and must be done in System Settings.

## RAM notes

- The shim defaults `--mlock` **off**: `--mlock` + a large `--ctx-size` has
  panicked the kernel on this 32 GB machine. Turn it on only deliberately.
- `--flash-attn` is sent as a valued flag (`on`/`off`) — recent `llama-server`
  builds reject the bare flag.
- `--threads 0` lets llama-server pick the core count.
