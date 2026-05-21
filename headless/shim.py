#!/usr/bin/env python3
"""
Headless control shim — a minimalist REST + single-page control plane for
running llama.cpp on a headless Mac.

Design goals:
  * Zero third-party dependencies (stdlib only) so it adds almost nothing to
    resident memory — every spare byte is reserved for the model.
  * Launch / stop / restart native `llama-server` instances with arbitrary args.
  * Pull models via `docker model pull` and resolve their GGUF blob path so
    llama-server can be pointed straight at the file.
  * Surface host + per-instance health metrics and logs.
  * Toggle "headless mode" (stop/disable Docker, the LLM Gateway stack and
    ollama) and trigger a reboot back to the GUI, via a sudoers-allowlisted
    helper script.

Everything is served on a single page at `/`.
"""

from __future__ import annotations

import json
import os
import re
import shutil
import signal
import subprocess
import threading
import time
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse, parse_qs

HERE = Path(__file__).resolve().parent


# --------------------------------------------------------------------------- #
# Config
# --------------------------------------------------------------------------- #

def _load_config() -> dict:
    cfg = json.loads((HERE / "config.json").read_text())
    # Expand ~ in path-like values.
    for k in ("docker_model_store", "log_dir", "headless_marker"):
        if cfg.get(k):
            cfg[k] = str(Path(cfg[k]).expanduser())
    # headless_ctl is resolved relative to this file unless given absolutely,
    # so the repo can live anywhere.
    ctl = cfg.get("headless_ctl", "headless_ctl.sh")
    cfg["headless_ctl"] = str((HERE / ctl).resolve()) if not os.path.isabs(ctl) else ctl
    return cfg


CFG = _load_config()
LOG_DIR = Path(CFG["log_dir"])
LOG_DIR.mkdir(parents=True, exist_ok=True)


def _expand(p: str) -> str:
    return str(Path(p).expanduser())


# --------------------------------------------------------------------------- #
# Small shell helper
# --------------------------------------------------------------------------- #

def run(cmd: list[str], timeout: float = 15.0) -> tuple[int, str, str]:
    """Run a command, capture output. Never raises."""
    try:
        p = subprocess.run(
            cmd, capture_output=True, text=True, timeout=timeout
        )
        return p.returncode, p.stdout, p.stderr
    except FileNotFoundError:
        return 127, "", f"not found: {cmd[0]}"
    except subprocess.TimeoutExpired:
        return 124, "", f"timeout after {timeout}s: {' '.join(cmd)}"
    except Exception as e:  # pragma: no cover - defensive
        return 1, "", str(e)


# --------------------------------------------------------------------------- #
# Host metrics (no psutil — shell out to macOS tools)
# --------------------------------------------------------------------------- #

def host_metrics() -> dict:
    out: dict = {}

    # Total physical memory.
    rc, so, _ = run(["sysctl", "-n", "hw.memsize"])
    total = int(so.strip()) if rc == 0 and so.strip().isdigit() else 0

    # vm_stat: page size + page buckets.
    rc, vm, _ = run(["vm_stat"])
    page = 4096
    pages: dict[str, int] = {}
    if rc == 0:
        m = re.search(r"page size of (\d+) bytes", vm)
        if m:
            page = int(m.group(1))
        for line in vm.splitlines():
            mm = re.match(r'"?(.+?)"?:\s+(\d+)\.', line.strip())
            if mm:
                pages[mm.group(1).strip().lower()] = int(mm.group(2))

    def b(key: str) -> int:
        return pages.get(key, 0) * page

    wired = b("pages wired down")
    compressed = b("pages occupied by compressor")
    active = b("pages active")
    inactive = b("pages inactive")
    free = b("pages free") + b("pages speculative")
    # "Used" the way Activity Monitor shows it: wired + active + compressed.
    used = wired + active + compressed
    out["memory"] = {
        "total": total,
        "used": used,
        "free": free,
        "wired": wired,
        "active": active,
        "inactive": inactive,
        "compressed": compressed,
        "available": max(total - used, 0),
        "used_pct": round(used / total * 100, 1) if total else 0,
    }

    # CPU.
    try:
        l1, l5, l15 = os.getloadavg()
    except OSError:
        l1 = l5 = l15 = 0.0
    out["cpu"] = {
        "count": os.cpu_count() or 0,
        "load": [round(l1, 2), round(l5, 2), round(l15, 2)],
    }

    # Uptime from kern.boottime.
    rc, so, _ = run(["sysctl", "-n", "kern.boottime"])
    boot = 0
    m = re.search(r"sec = (\d+)", so)
    if m:
        boot = int(m.group(1))
    out["uptime_sec"] = int(time.time()) - boot if boot else 0

    # Disk for the model store volume.
    try:
        du = shutil.disk_usage(CFG["docker_model_store"])
        out["disk"] = {"total": du.total, "used": du.used, "free": du.free}
    except Exception:
        out["disk"] = {}

    return out


# --------------------------------------------------------------------------- #
# Tailscale
# --------------------------------------------------------------------------- #

def tailscale_status() -> dict:
    bin_ = CFG["tailscale_bin"]
    rc, so, se = run([bin_, "status", "--json"], timeout=8)
    if rc != 0:
        return {"ok": False, "error": (se or so or "tailscale unavailable").strip()}
    try:
        d = json.loads(so)
    except Exception:
        return {"ok": False, "error": "could not parse tailscale status"}
    self_ = d.get("Self", {}) or {}
    return {
        "ok": True,
        "state": d.get("BackendState"),
        "hostname": self_.get("HostName"),
        "ips": self_.get("TailscaleIPs", []),
        "online": self_.get("Online", False),
        "peers": len(d.get("Peer", {}) or {}),
    }


# --------------------------------------------------------------------------- #
# Docker model store
# --------------------------------------------------------------------------- #

def docker_models() -> dict:
    """List local models (first column of `docker model list`, names have no spaces)."""
    rc, so, se = run([CFG["docker_bin"], "model", "list"], timeout=20)
    if rc != 0:
        return {"ok": False, "error": (se or so).strip(), "models": [], "raw": ""}
    names = []
    for line in so.splitlines()[1:]:  # skip header
        line = line.rstrip()
        if not line:
            continue
        names.append(line.split()[0])
    return {"ok": True, "models": names, "raw": so}


def resolve_gguf(model_name: str) -> tuple[str | None, str]:
    """Map a docker model name -> on-disk GGUF blob path."""
    rc, so, se = run([CFG["docker_bin"], "model", "inspect", model_name], timeout=20)
    if rc != 0:
        return None, (se or so or "inspect failed").strip()
    try:
        info = json.loads(so)
    except Exception:
        return None, "could not parse inspect output"
    mid = (info.get("id") or "").replace("sha256:", "")
    if not mid:
        return None, "no model id in inspect output"

    store = Path(CFG["docker_model_store"])
    manifest = store / "manifests" / "sha256" / mid
    if not manifest.exists():
        return None, f"manifest not found: {manifest}"
    try:
        man = json.loads(manifest.read_text())
    except Exception:
        return None, "could not parse manifest"

    for layer in man.get("layers", []):
        if "gguf" in (layer.get("mediaType") or "").lower():
            digest = (layer.get("digest") or "").replace("sha256:", "")
            blob = store / "blobs" / "sha256" / digest
            if blob.exists():
                return str(blob), ""
            return None, f"gguf blob missing: {blob}"
    return None, "no gguf layer in manifest"


# --------------------------------------------------------------------------- #
# Model pull (background job)
# --------------------------------------------------------------------------- #

class PullJob:
    def __init__(self):
        self.lock = threading.Lock()
        self.state = "idle"   # idle | running | done | error
        self.model = ""
        self.started = 0.0
        self.logfile = LOG_DIR / "pull.log"

    def start(self, model: str) -> tuple[bool, str]:
        with self.lock:
            if self.state == "running":
                return False, f"a pull is already running ({self.model})"
            self.state = "running"
            self.model = model
            self.started = time.time()
        threading.Thread(target=self._run, args=(model,), daemon=True).start()
        return True, "pull started"

    def _run(self, model: str):
        with open(self.logfile, "ab") as fh:
            fh.write(f"\n=== pull {model} @ {time.ctime()} ===\n".encode())
            fh.flush()
            try:
                p = subprocess.Popen(
                    [CFG["docker_bin"], "model", "pull", model],
                    stdout=fh, stderr=subprocess.STDOUT,
                )
                rc = p.wait()
            except Exception as e:
                fh.write(f"error: {e}\n".encode())
                rc = 1
        with self.lock:
            self.state = "done" if rc == 0 else "error"

    def status(self) -> dict:
        with self.lock:
            return {
                "state": self.state,
                "model": self.model,
                "started": self.started,
                "elapsed": round(time.time() - self.started, 1) if self.started else 0,
            }


PULL = PullJob()


# --------------------------------------------------------------------------- #
# llama-server instance registry
# --------------------------------------------------------------------------- #

# Presence-only flags: a truthy config/request value includes the bare flag,
# a falsy one omits it. (Note: --flash-attn is NOT here — recent llama-server
# builds take it as a valued flag, `--flash-attn on|off|auto`.)
_BOOL_FLAGS = {"--metrics", "--no-mmap", "--mlock",
               "--cont-batching", "--embedding", "--verbose"}


class Instance:
    def __init__(self, port: int, model_name: str, gguf: str, args: dict, proc):
        self.port = port
        self.model_name = model_name
        self.gguf = gguf
        self.args = args
        self.proc = proc
        self.started = time.time()
        self.logfile = LOG_DIR / f"llama-{port}.log"

    def alive(self) -> bool:
        return self.proc.poll() is None

    def health(self) -> dict:
        try:
            with urllib.request.urlopen(
                f"http://127.0.0.1:{self.port}/health", timeout=2
            ) as r:
                return {"reachable": True, "status": json.loads(r.read() or b"{}")}
        except Exception as e:
            return {"reachable": False, "error": str(e)}

    def info(self) -> dict:
        return {
            "port": self.port,
            "model": self.model_name,
            "gguf": self.gguf,
            "pid": self.proc.pid,
            "alive": self.alive(),
            "returncode": self.proc.returncode,
            "started": self.started,
            "uptime_sec": round(time.time() - self.started, 1),
            "args": self.args,
            "logfile": str(self.logfile),
        }


class Registry:
    def __init__(self):
        self.lock = threading.Lock()
        self.byport: dict[int, Instance] = {}

    def _build_cmd(self, gguf: str, args: dict) -> list[str]:
        merged = dict(CFG.get("llama_defaults", {}))
        merged.update(args or {})
        cmd = [CFG["llama_server_bin"], "--model", gguf]
        for flag, val in merged.items():
            if flag in _BOOL_FLAGS:
                # Truthy -> include the bare flag; falsy -> omit.
                if str(val).lower() in ("1", "true", "on", "yes"):
                    cmd.append(flag)
                continue
            if val is None or str(val).strip() == "":
                continue
            cmd += [flag, str(val)]
        return cmd

    def start(self, model_name: str, args: dict) -> tuple[bool, str, dict | None]:
        gguf, err = resolve_gguf(model_name)
        if not gguf:
            return False, f"could not resolve model '{model_name}': {err}", None

        merged = dict(CFG.get("llama_defaults", {}))
        merged.update(args or {})
        try:
            port = int(merged.get("--port", 8080))
        except (TypeError, ValueError):
            return False, "invalid --port", None

        with self.lock:
            existing = self.byport.get(port)
            if existing and existing.alive():
                return False, f"port {port} already serving {existing.model_name}", None

        cmd = self._build_cmd(gguf, args)
        logfile = LOG_DIR / f"llama-{port}.log"
        with open(logfile, "ab") as fh:
            fh.write(f"\n=== start {model_name} @ {time.ctime()} ===\n".encode())
            fh.write((" ".join(cmd) + "\n").encode())
            fh.flush()
            proc = subprocess.Popen(
                cmd, stdout=fh, stderr=subprocess.STDOUT,
                start_new_session=True,  # own process group -> clean killpg
            )
        inst = Instance(port, model_name, gguf, merged, proc)
        with self.lock:
            self.byport[port] = inst
        return True, f"started {model_name} on :{port} (pid {proc.pid})", inst.info()

    def stop(self, port: int) -> tuple[bool, str]:
        with self.lock:
            inst = self.byport.get(port)
        if not inst:
            return False, f"no instance on :{port}"
        if inst.alive():
            try:
                os.killpg(os.getpgid(inst.proc.pid), signal.SIGTERM)
            except ProcessLookupError:
                pass
            for _ in range(50):  # up to ~5s
                if inst.proc.poll() is not None:
                    break
                time.sleep(0.1)
            if inst.proc.poll() is None:
                try:
                    os.killpg(os.getpgid(inst.proc.pid), signal.SIGKILL)
                except ProcessLookupError:
                    pass
        with self.lock:
            self.byport.pop(port, None)
        return True, f"stopped :{port}"

    def restart(self, port: int) -> tuple[bool, str, dict | None]:
        with self.lock:
            inst = self.byport.get(port)
        if not inst:
            return False, f"no instance on :{port}", None
        model_name, args = inst.model_name, dict(inst.args)
        self.stop(port)
        return self.start(model_name, args)

    def list(self) -> list[dict]:
        with self.lock:
            insts = list(self.byport.values())
        return [i.info() for i in insts]


REG = Registry()


# --------------------------------------------------------------------------- #
# Headless mode (privileged helper via sudo)
# --------------------------------------------------------------------------- #

def headless_status() -> dict:
    active = Path(CFG["headless_marker"]).exists()
    return {"headless": active, "marker": CFG["headless_marker"]}


def headless_ctl(action: str) -> tuple[bool, str]:
    ctl = CFG["headless_ctl"]
    if not Path(ctl).exists():
        return False, f"helper not installed: {ctl}"
    rc, so, se = run(["sudo", "-n", ctl, action], timeout=120)
    ok = rc == 0
    return ok, (so + se).strip() or (f"exit {rc}")


# --------------------------------------------------------------------------- #
# Logs
# --------------------------------------------------------------------------- #

def tail(path: Path, lines: int = 200) -> str:
    if not path.exists():
        return ""
    try:
        with open(path, "rb") as f:
            f.seek(0, os.SEEK_END)
            size = f.tell()
            block = 4096
            data = b""
            while size > 0 and data.count(b"\n") <= lines:
                step = min(block, size)
                size -= step
                f.seek(size)
                data = f.read(step) + data
        return b"\n".join(data.splitlines()[-lines:]).decode(errors="replace")
    except Exception as e:
        return f"<error reading {path}: {e}>"


# --------------------------------------------------------------------------- #
# HTTP handler
# --------------------------------------------------------------------------- #

INDEX_HTML = (HERE / "index.html").read_text()


class Handler(BaseHTTPRequestHandler):
    server_version = "headless-shim/1.0"

    def log_message(self, *a):  # quieter
        pass

    # -- helpers --
    def _json(self, obj, code: int = 200):
        body = json.dumps(obj).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _text(self, text: str, code: int = 200, ctype="text/plain; charset=utf-8"):
        body = text.encode()
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _body(self) -> dict:
        n = int(self.headers.get("Content-Length") or 0)
        if not n:
            return {}
        try:
            return json.loads(self.rfile.read(n) or b"{}")
        except Exception:
            return {}

    # -- routing --
    def do_GET(self):
        u = urlparse(self.path)
        p, q = u.path, parse_qs(u.query)

        if p in ("/", "/index.html"):
            return self._text(INDEX_HTML, ctype="text/html; charset=utf-8")

        if p == "/api/health":
            return self._json({"ok": True, "ts": time.time()})

        if p == "/api/metrics":
            return self._json({
                "host": host_metrics(),
                "tailscale": tailscale_status(),
                "instances": REG.list(),
                "headless": headless_status(),
                "pull": PULL.status(),
            })

        if p == "/api/instances":
            return self._json({"instances": REG.list()})

        if p == "/api/instance/health":
            try:
                port = int(q.get("port", ["0"])[0])
            except ValueError:
                return self._json({"error": "bad port"}, 400)
            inst = REG.byport.get(port)
            if not inst:
                return self._json({"error": "no such instance"}, 404)
            return self._json(inst.health())

        if p == "/api/models":
            return self._json(docker_models())

        if p == "/api/pull/status":
            return self._json(PULL.status())

        if p == "/api/tailscale":
            return self._json(tailscale_status())

        if p == "/api/headless/status":
            return self._json(headless_status())

        if p == "/api/logs":
            which = q.get("name", ["shim"])[0]
            n = int(q.get("lines", ["200"])[0])
            if which == "pull":
                fp = PULL.logfile
            elif which == "shim":
                fp = LOG_DIR / "shim.log"
            else:
                # llama-<port>
                fp = LOG_DIR / f"{which}.log"
            return self._text(tail(fp, n))

        return self._json({"error": "not found"}, 404)

    def do_POST(self):
        u = urlparse(self.path)
        p = u.path
        body = self._body()

        if p == "/api/llama/start":
            model = body.get("model")
            if not model:
                return self._json({"ok": False, "error": "model required"}, 400)
            ok, msg, info = REG.start(model, body.get("args", {}))
            return self._json({"ok": ok, "message": msg, "instance": info},
                              200 if ok else 400)

        if p == "/api/llama/stop":
            try:
                port = int(body.get("port"))
            except (TypeError, ValueError):
                return self._json({"ok": False, "error": "port required"}, 400)
            ok, msg = REG.stop(port)
            return self._json({"ok": ok, "message": msg}, 200 if ok else 404)

        if p == "/api/llama/restart":
            try:
                port = int(body.get("port"))
            except (TypeError, ValueError):
                return self._json({"ok": False, "error": "port required"}, 400)
            ok, msg, info = REG.restart(port)
            return self._json({"ok": ok, "message": msg, "instance": info},
                              200 if ok else 400)

        if p == "/api/models/pull":
            model = body.get("model")
            if not model:
                return self._json({"ok": False, "error": "model required"}, 400)
            ok, msg = PULL.start(model)
            return self._json({"ok": ok, "message": msg}, 200 if ok else 409)

        if p == "/api/headless/enter":
            ok, msg = headless_ctl("enter")
            return self._json({"ok": ok, "output": msg}, 200 if ok else 500)

        if p == "/api/headless/exit":
            # Re-enables services and reboots to GUI; the connection will drop.
            ok, msg = headless_ctl("exit")
            return self._json({"ok": ok, "output": msg,
                               "note": "rebooting to GUI"}, 200 if ok else 500)

        return self._json({"error": "not found"}, 404)


class Server(ThreadingHTTPServer):
    daemon_threads = True
    allow_reuse_address = True

    def server_bind(self):
        # HTTPServer.server_bind() resolves a FQDN via socket.getfqdn(), a
        # reverse-DNS lookup that can hang for seconds on a box with no/slow
        # DNS — exactly the situation at headless boot. Bind without it.
        import socketserver
        socketserver.TCPServer.server_bind(self)
        host, port = self.server_address[:2]
        self.server_name = host
        self.server_port = port


def main():
    host, port = CFG["host"], int(CFG["port"])
    httpd = Server((host, port), Handler)
    print(f"headless-shim listening on http://{host}:{port}  (logs: {LOG_DIR})")
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
