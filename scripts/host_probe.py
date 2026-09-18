"""
Host-level probes used by the ``gw`` CLI (stdlib only — gw may run under the
system python3 without the repo venv).

- Docker: distinguish "not installed", "not running", and "running but this
  user can't reach the socket" (e.g. Docker Desktop launched by another macOS
  user). Falls back to /var/run/docker.sock when the active context's socket
  is missing.
- Containers: list every container with state + published ports.
- Tailscale: MagicDNS name, tailnet IP, and ``tailscale serve`` mappings so
  local ports can be shown with their tailnet URLs.
- Port probes: HTTP / TCP reachability checks, run concurrently.
"""

from __future__ import annotations

import json
import os
import re
import shutil
import socket
import subprocess
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from urllib.parse import urlparse

FALLBACK_DOCKER_SOCKET = "/var/run/docker.sock"


def _run(cmd: list[str], timeout: float = 10, env: dict | None = None) -> tuple[int, str, str]:
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout, env=env)
        return r.returncode, r.stdout, r.stderr
    except (subprocess.TimeoutExpired, FileNotFoundError, OSError):
        return -1, "", ""


# ── Docker ────────────────────────────────────────────────────────────────────

@dataclass
class DockerStatus:
    state: str               # ok | no_access | not_running | not_installed
    detail: str = ""
    hint: str = ""
    owner: str = ""          # macOS user running Docker Desktop, if detected


def _docker_desktop_owner() -> str:
    """Return the macOS user running Docker Desktop's backend, or ''."""
    rc, out, _ = _run(["pgrep", "-f", "Docker.app/Contents/MacOS/com.docker.backend"], timeout=5)
    if rc != 0 or not out.strip():
        return ""
    pid = out.split()[0]
    rc, out, _ = _run(["ps", "-o", "user=", "-p", pid], timeout=5)
    return out.strip() if rc == 0 else ""


def docker_status() -> DockerStatus:
    """Diagnose Docker reachability.

    If the active context's socket is missing but /var/run/docker.sock works,
    DOCKER_HOST is set in os.environ so later docker/compose calls use it.
    """
    if not shutil.which("docker"):
        return DockerStatus("not_installed", "docker CLI not found",
                            "Install Docker Desktop: https://docker.com/products/docker-desktop/")

    rc, _, err = _run(["docker", "info", "--format", "{{.ServerVersion}}"])
    if rc == 0:
        return DockerStatus("ok")

    if "DOCKER_HOST" not in os.environ and os.path.exists(FALLBACK_DOCKER_SOCKET):
        env = {**os.environ, "DOCKER_HOST": f"unix://{FALLBACK_DOCKER_SOCKET}"}
        rc2, _, err2 = _run(["docker", "info", "--format", "{{.ServerVersion}}"], env=env)
        if rc2 == 0:
            os.environ["DOCKER_HOST"] = env["DOCKER_HOST"]
            return DockerStatus("ok", f"via {FALLBACK_DOCKER_SOCKET}")
        err = err2 or err

    me = os.environ.get("USER") or ""
    owner = _docker_desktop_owner()
    if owner and me and owner != me:
        return DockerStatus(
            "no_access",
            f"Docker Desktop is running as '{owner}' — '{me}' can't reach its socket",
            f"Run gw as '{owner}', or run Docker Desktop as '{me}'",
            owner,
        )
    if "permission denied" in err.lower():
        return DockerStatus("no_access", "permission denied on Docker socket",
                            "Check socket permissions / docker context", owner)
    if owner:
        return DockerStatus("not_running", "Docker Desktop is starting or its engine is down",
                            "Wait for Docker Desktop, or restart it", owner)
    return DockerStatus("not_running", "Docker Desktop is not running",
                        "open -a Docker")


@dataclass
class Container:
    name: str
    state: str               # running | starting | stopped | unhealthy | <raw>
    image: str = ""
    ports: list[int] = field(default_factory=list)   # host-published TCP ports


def _normalize_state(status: str, health: str) -> str:
    if status == "running":
        if health == "unhealthy":
            return "unhealthy"
        if health == "starting":
            return "starting"
        return "running"
    if status in ("exited", "dead", "created"):
        return "stopped"
    if status == "restarting":
        return "starting"
    return status


def list_containers() -> list[Container]:
    """All containers (running and stopped) with host-published ports."""
    rc, out, _ = _run(["docker", "ps", "-a", "--format", "{{json .}}"])
    if rc != 0:
        return []
    containers = []
    for line in out.splitlines():
        try:
            row = json.loads(line)
        except json.JSONDecodeError:
            continue
        status_text = row.get("Status", "")
        health = ""
        m = re.search(r"\((healthy|unhealthy|health: starting)\)", status_text)
        if m:
            health = "starting" if "starting" in m.group(1) else m.group(1)
        ports = sorted({int(p) for p in re.findall(r"(?:0\.0\.0\.0|\[::\]|127\.0\.0\.1):(\d+)->", row.get("Ports", ""))})
        containers.append(Container(
            name=row.get("Names", ""),
            state=_normalize_state(row.get("State", ""), health),
            image=row.get("Image", ""),
            ports=ports,
        ))
    return containers


# ── Tailscale ─────────────────────────────────────────────────────────────────

@dataclass
class Tailnet:
    dns_name: str = ""                                          # host.tailnet.ts.net
    ip: str = ""                                                # 100.x.y.z
    serve: dict[int, list[str]] = field(default_factory=dict)   # local port -> tailnet URLs

    @property
    def up(self) -> bool:
        return bool(self.ip)


def tailnet_info() -> Tailnet:
    """Read Tailscale self info and `tailscale serve` mappings. Empty if unavailable."""
    if not shutil.which("tailscale"):
        return Tailnet()
    rc, out, _ = _run(["tailscale", "status", "--json"], timeout=5)
    if rc != 0:
        return Tailnet()
    try:
        data = json.loads(out)
    except json.JSONDecodeError:
        return Tailnet()
    if data.get("BackendState") not in (None, "Running"):
        return Tailnet()
    me = data.get("Self") or {}
    ips = [ip for ip in me.get("TailscaleIPs") or [] if "." in ip]
    tn = Tailnet(dns_name=(me.get("DNSName") or "").rstrip("."), ip=ips[0] if ips else "")

    rc, out, _ = _run(["tailscale", "serve", "status", "--json"], timeout=5)
    if rc == 0 and out.strip():
        try:
            serve = json.loads(out)
        except json.JSONDecodeError:
            serve = {}
        tcp = serve.get("TCP") or {}
        for hostport, cfg in (serve.get("Web") or {}).items():
            host, _, port = hostport.rpartition(":")
            https = (tcp.get(port) or {}).get("HTTPS", False)
            scheme = "https" if https else "http"
            default = "443" if https else "80"
            base = f"{scheme}://{host}" + ("" if port == default else f":{port}")
            for path, handler in (cfg.get("Handlers") or {}).items():
                target = urlparse(handler.get("Proxy") or "")
                if target.hostname in ("127.0.0.1", "localhost") and target.port:
                    url = base + ("" if path == "/" else path)
                    tn.serve.setdefault(target.port, []).append(url)
    return tn


# ── Port probes ───────────────────────────────────────────────────────────────

def http_ok(url: str, timeout: float = 2) -> bool:
    try:
        with urllib.request.urlopen(url, timeout=timeout) as resp:
            return 200 <= resp.status < 400
    except urllib.error.HTTPError as e:
        # Server answered — it's up even if / isn't a 2xx (e.g. 401, 404)
        return e.code < 500
    except Exception:
        return False


def tcp_open(host: str, port: int, timeout: float = 1) -> bool:
    try:
        with socket.create_connection((host, port), timeout=timeout):
            return True
    except OSError:
        return False


def html_title(url: str, timeout: float = 2) -> str:
    """Best-effort <title> of a page, for naming unknown services."""
    try:
        with urllib.request.urlopen(url, timeout=timeout) as resp:
            body = resp.read(65536).decode(errors="replace")
        m = re.search(r"<title[^>]*>([^<]{1,80})</title>", body, re.I)
        return m.group(1).strip() if m else ""
    except Exception:
        return ""


def parallel(fn, items) -> list:
    """Map fn over items concurrently (I/O-bound probes)."""
    items = list(items)
    if not items:
        return []
    with ThreadPoolExecutor(max_workers=min(16, len(items))) as pool:
        return list(pool.map(fn, items))
