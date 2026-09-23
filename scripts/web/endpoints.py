"""
Endpoint catalog + server-side reachability probes.

Backs the dashboard's "Endpoints" section. Two concerns live here:

  * Building the catalog — every service this gateway exposes, paired with
    the URL a *remote* client can actually reach it on. Preference order is
    tailscale serve (HTTPS front door) → MagicDNS name → tailnet IP → LAN IP
    → localhost. "localhost" only means something on the box running the
    dashboard, which is rarely where the user's client lives.

  * Probing — the Test button. Probes run server-side, not in the browser:
    the dashboard is a different origin from every service it lists, so a
    fetch() from the page would be blocked by CORS long before it learned
    anything useful. The server has no such restriction.

Probes never mutate anything — GET / TCP connect / `redis-cli ping`.
"""

from __future__ import annotations

import asyncio
import http.client
import json
import socket
import ssl
import time
import urllib.parse
from pathlib import Path
from typing import Any


# ── Environment ─────────────────────────────────────────────────────────────

def _parse_env(path: Path) -> dict[str, str]:
    """Minimal .env reader — KEY=VALUE, '#' comments, optional quotes."""
    out: dict[str, str] = {}
    if not path.exists():
        return out
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, val = line.partition("=")
        val = val.strip()
        if len(val) >= 2 and val[0] == val[-1] and val[0] in "\"'":
            val = val[1:-1]
        out[key.strip()] = val
    return out


async def _run(*args: str, timeout: float = 10.0) -> tuple[int, bytes, bytes]:
    """Run a command, returning (rc, stdout, stderr). rc=-1 if not installed."""
    try:
        proc = await asyncio.create_subprocess_exec(
            *args,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
    except FileNotFoundError:
        return -1, b"", b"not found"
    try:
        out, err = await asyncio.wait_for(proc.communicate(), timeout=timeout)
    except asyncio.TimeoutError:
        try:
            proc.kill()
        except ProcessLookupError:
            pass
        return -2, b"", b"timed out"
    return proc.returncode or 0, out, err


# ── Host reachability ───────────────────────────────────────────────────────

def _lan_ip() -> str | None:
    # UDP "connect" only picks a route/local address — nothing is sent — so
    # this works offline and doesn't require 8.8.8.8 to be reachable.
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
            s.connect(("8.8.8.8", 80))
            return s.getsockname()[0]
    except OSError:
        return None


async def _network_info() -> dict[str, Any]:
    """Tailnet DNS name / IP plus a LAN-IP fallback."""
    info: dict[str, Any] = {
        "dns_name": None,
        "tailscale_ip": None,
        "lan_ip": _lan_ip(),
        "tailscale_online": False,
    }
    rc, out, _ = await _run("tailscale", "status", "--json")
    if rc != 0:
        return info
    try:
        status = json.loads(out.decode("utf-8"))
    except Exception:
        return info
    self_node = status.get("Self") or {}
    ips = status.get("TailscaleIPs") or []
    info["dns_name"] = (self_node.get("DNSName") or "").rstrip(".") or None
    info["tailscale_ip"] = ips[0] if ips else None
    info["tailscale_online"] = (
        bool(self_node.get("Online")) and status.get("BackendState") == "Running"
    )
    return info


async def _serve_map() -> dict[int, str]:
    """
    Map local backend port → public HTTPS origin, from `tailscale serve`.

    e.g. {4000: "https://host.tailnet.ts.net", 3001: "https://host.tailnet.ts.net:8443"}
    These are the URLs to prefer: they terminate TLS with a real cert, which
    some browser features (Open WebUI's microphone) require.
    """
    rc, out, _ = await _run("tailscale", "serve", "status", "--json")
    if rc != 0:
        return {}
    try:
        serve = json.loads(out.decode("utf-8") or "{}")
    except Exception:
        return {}
    mapping: dict[int, str] = {}
    for hostport, cfg in (serve.get("Web") or {}).items():
        host, _, front_port = hostport.rpartition(":")
        proxy = ((cfg.get("Handlers") or {}).get("/") or {}).get("Proxy", "")
        backend_port = proxy.rpartition(":")[2]
        if not backend_port.isdigit():
            continue
        origin = f"https://{host}" + ("" if front_port == "443" else f":{front_port}")
        mapping[int(backend_port)] = origin
    return mapping


_LOOPBACK = {"127.0.0.1", "::1", "localhost"}


def _port_binds(ports: str) -> dict[int, set[str]]:
    """
    Parse docker's Ports column into {host_port: {bind_ip, …}}.

    Format is a comma-separated list like
    "0.0.0.0:3001->8080/tcp, [::]:3001->8080/tcp" or "127.0.0.1:9119->9119/tcp".
    Entries without "->" (e.g. "6379/tcp") are exposed but not published, so
    they contribute nothing — that distinction is exactly what tells us Redis
    has no host-reachable URL.
    """
    binds: dict[int, set[str]] = {}
    for seg in (ports or "").split(","):
        seg = seg.strip()
        if "->" not in seg:
            continue
        left = seg.split("->", 1)[0].strip()
        ip, _, host_port = left.rpartition(":")
        ip = ip.strip("[]")
        if not host_port.isdigit():
            continue
        binds.setdefault(int(host_port), set()).add(ip or "0.0.0.0")
    return binds


async def _container_info() -> dict[str, dict[str, Any]]:
    """Container name → {'state': 'running'|…, 'binds': {host_port: {ip,…}}}."""
    rc, out, _ = await _run("docker", "ps", "-a", "--format", "{{json .}}", timeout=15)
    if rc != 0:
        return {}
    info: dict[str, dict[str, Any]] = {}
    for raw in out.splitlines():
        raw = raw.strip()
        if not raw:
            continue
        try:
            row = json.loads(raw.decode("utf-8"))
        except Exception:
            continue
        name = row.get("Names")
        if name:
            info[name] = {
                "state": (row.get("State") or "").lower(),
                "binds": _port_binds(row.get("Ports") or ""),
            }
    return info


# ── Catalog ─────────────────────────────────────────────────────────────────

def _param(label: str, value: str, *, secret: bool = False, note: str = "") -> dict:
    return {"label": label, "value": value, "secret": secret, "note": note}


async def build_catalog(request) -> dict[str, Any]:
    """
    Assemble every endpoint this install exposes, with its reachable URL,
    the extra parameters a client needs, and how to probe it.
    """
    registry = getattr(request.app.state, "service_registry", None)
    repo_dir = getattr(request.app.state, "repo_dir", None)
    data_dir = getattr(request.app.state, "data_dir", None) or repo_dir
    config_manager = getattr(request.app.state, "config_manager", None)

    env = _parse_env(Path(data_dir) / ".env") if data_dir else {}
    net, serve, cinfo = await asyncio.gather(
        _network_info(), _serve_map(), _container_info()
    )
    containers = {name: c["state"] for name, c in cinfo.items()}

    def loopback_only(container: str, port: int) -> bool:
        """True when the container publishes `port` on loopback only."""
        binds = (cinfo.get(container) or {}).get("binds") or {}
        ips = binds.get(port)
        return bool(ips) and all(ip in _LOOPBACK for ip in ips)

    tailnet_host = net["dns_name"] or net["tailscale_ip"]
    host = tailnet_host or net["lan_ip"] or "localhost"

    # Exposure is a policy per service, not something inferred from whatever
    # address happens to answer. Two tiers:
    #
    #   tailnet()  — the client lives on another device, so the only URL worth
    #                printing is the tailnet one. No LAN or localhost fallback:
    #                handing out "localhost" to someone on a laptop is a lie.
    #   internal() — the only callers are on this box (or on gateway-net), so
    #                the service is deliberately never published to the tailnet.
    #
    # local_url stays localhost in both cases: probe() falls back to it to tell
    # "the service is down" apart from "it's up but not reachable remotely".

    def tailnet(port: int) -> tuple[str, str, str]:
        local = f"http://localhost:{port}"
        if port in serve:
            # A serve front door wins even over a loopback-bound backend —
            # proxying the tailnet to 127.0.0.1 is the whole point of it — and
            # it terminates TLS with a real cert, which the Open WebUI mic needs.
            return serve[port], local, "tailscale serve"
        if tailnet_host:
            return f"http://{tailnet_host}:{port}", local, "tailnet"
        return local, local, "tailnet down"

    def internal(port: int) -> tuple[str, str, str]:
        local = f"http://localhost:{port}"
        return local, local, "internal only"

    endpoints: list[dict[str, Any]] = []

    def add(
        id: str, label: str, group: str, description: str,
        *, url: str | None, local_url: str | None, via: str,
        state: str, probe: dict[str, Any], params: list[dict] | None = None,
        note: str = "", note_level: str = "info",
    ) -> None:
        # note_level is set here rather than inferred from the prose in the
        # dashboard — "not exposed to the tailnet" is a deliberate design
        # choice for Redis and a limitation for Hermes, and no keyword match
        # can tell those apart.
        endpoints.append({
            "id": id, "label": label, "group": group, "description": description,
            "url": url, "local_url": local_url, "via": via, "state": state,
            "probe": probe, "params": params or [], "note": note,
            "note_level": note_level if note else "info",
        })

    # ── Gateway management UI (this dashboard) ──
    gw_port, gw_host = 8080, "127.0.0.1"
    if config_manager is not None:
        try:
            gw_cfg = config_manager.config.get("gateway", {})
            gw_port = int(gw_cfg.get("port", 8080))
            gw_host = str(gw_cfg.get("host", "127.0.0.1"))
        except Exception:
            pass
    gw_loopback = gw_host in _LOOPBACK and gw_port not in serve
    pub, loc, via = tailnet(gw_port)
    add(
        "management", "Management dashboard", "Gateway",
        "This UI, plus the read-only REST API under /api.",
        url=pub, local_url=loc, via=via, state="running",
        probe={"kind": "http", "path": "/api/health"},
        params=[_param("REST API", f"{pub}/api/status", note="GET, no auth — read-only")],
        note=("Bound to %s, so the tailnet URL above will not answer. Set "
              "gateway.host to 0.0.0.0, or put it behind `tailscale serve`."
              % gw_host) if gw_loopback else "",
        note_level="warn" if gw_loopback else "info",
    )

    # ── LiteLLM proxy ──
    litellm_state = containers.get("llm-gateway", "absent")
    if litellm_state != "absent":
        pub, loc, via = tailnet(4000)
        master = env.get("LITELLM_MASTER_KEY", "")
        add(
            "litellm", "LiteLLM proxy", "LiteLLM",
            "OpenAI-compatible routing front door for every model.",
            url=pub, local_url=loc, via=via, state=litellm_state,
            probe={"kind": "http", "path": "/health/liveliness"},
            params=[
                _param("OpenAI base URL", f"{pub}/v1", note="set as OPENAI_BASE_URL / api_base"),
                _param("API key", master, secret=True,
                       note="LITELLM_MASTER_KEY from .env — sent as Authorization: Bearer"),
                _param("Admin UI", f"{pub}/ui", note="sign in with the master key"),
            ],
        )

    # ── Postgres (spend/keys DB) ──
    pg_state = containers.get("llm-postgres", "absent")
    if pg_state != "absent":
        add(
            "postgres", "PostgreSQL", "LiteLLM",
            "Virtual keys, spend tracking and the model DB behind LiteLLM.",
            url="postgresql://localhost:5432/litellm",
            local_url="postgresql://localhost:5432/litellm",
            via="internal only", state=pg_state,
            probe={"kind": "tcp", "host": "127.0.0.1", "port": 5432},
            params=[
                _param("In-network host", "postgres:5432", note="as the LiteLLM container sees it"),
                _param("Database", "litellm"),
                _param("User", "litellm"),
                _param("Password", "litellm", secret=True,
                       note="compose default — change POSTGRES_PASSWORD to harden"),
                _param("Connection URI", "postgresql://litellm:litellm@localhost:5432/litellm",
                       secret=True),
            ],
        )

    # ── Redis (LiteLLM response cache) ──
    redis_state = containers.get("llm-redis", "absent")
    if redis_state != "absent":
        add(
            "redis", "Redis cache", "LiteLLM",
            "LiteLLM response cache. No published port — reachable only from "
            "other containers on gateway-net.",
            url="redis://redis:6379", local_url="redis://redis:6379",
            via="internal only", state=redis_state,
            probe={"kind": "exec", "container": "llm-redis",
                   "cmd": ["redis-cli", "ping"], "expect": "PONG"},
            params=[
                _param("In-network host", "redis:6379", note="as LiteLLM's cache config sees it"),
            ],
        )

    # ── Open WebUI ──
    owui_state = containers.get("open-webui", "absent")
    if owui_state != "absent":
        pub, loc, via = tailnet(3001)
        mic_note = (
            "microphone works — HTTPS origin"
            if via == "tailscale serve"
            else "microphone is blocked: browsers require an HTTPS origin. "
                 "Run `tailscale serve --bg --https 8443 http://127.0.0.1:3001`."
        )
        add(
            "open-webui", "Open WebUI", "Other Services",
            "Browser chat front-end wired to LiteLLM, Kokoro TTS and Whisper STT.",
            url=pub, local_url=loc, via=via, state=owui_state,
            probe={"kind": "http", "path": "/health"},
            params=[_param("Sign-in", "local account", note="first account created becomes admin")],
            note=mic_note,
            note_level="info" if via == "tailscale serve" else "warn",
        )

    # ── Hermes dashboard (standalone container, loopback-bound) ──
    hermes_state = containers.get("hermes-dashboard", "absent")
    if hermes_state != "absent":
        hermes_loopback = loopback_only("hermes-dashboard", 9119) and 9119 not in serve
        pub, loc, via = tailnet(9119)
        add(
            "hermes-dashboard", "Hermes dashboard", "Other Services",
            "Hermes agent dashboard — a standalone container, not part of compose.",
            url=pub, local_url=loc, via=via, state=hermes_state,
            probe={"kind": "http", "path": "/"},
            note="Published on 127.0.0.1:9119, so the tailnet URL above will not "
                 "answer. Re-publish on 0.0.0.0 to expose it." if hermes_loopback else "",
            note_level="warn" if hermes_loopback else "info",
        )

    # ── Observability (only when the containers exist) ──
    obs = [
        ("grafana", "Grafana", 3000, "/api/health", "Dashboards over Prometheus + Loki.", tailnet),
        ("prometheus", "Prometheus", 9090, "/-/ready", "Metrics scraped from LiteLLM.", internal),
        ("loki", "Loki", 3100, "/ready", "Log aggregation fed by Alloy.", internal),
    ]
    for cid, label, port, path, desc, expose in obs:
        state = containers.get(cid, "absent")
        if state == "absent":
            continue
        pub, loc, via = expose(port)
        params = []
        if cid == "grafana":
            params = [
                _param("User", env.get("GF_SECURITY_ADMIN_USER") or "admin"),
                _param("Password", env.get("GF_SECURITY_ADMIN_PASSWORD") or "llmgateway",
                       secret=True, note="GF_SECURITY_ADMIN_PASSWORD in .env"),
            ]
        add(cid, label, "Observability", desc,
            url=pub, local_url=loc, via=via, state=state,
            probe={"kind": "http", "path": path}, params=params)

    # ── Gateway-managed local services (llama-server, whisper, kokoro) ──
    # Mirrors SVC_TITLES in dashboard.html so a service reads the same in both
    # sections — "local (local)" helps nobody.
    svc_titles = {
        "local": "LLM — local (llama-server)",
        "kokoro": "TTS — kokoro",
        "whisper-fast": "STT — whisper-fast",
        "whisper-large": "STT — whisper-large",
    }
    # Local inference is reached through LiteLLM, never directly, so it stays
    # host-internal. Speech is the exception: Open WebUI calls STT/TTS straight
    # from the browser, which is on the tailnet.
    svc_internal = {"local"}
    if registry is not None:
        try:
            statuses = registry.all_status()
        except Exception:
            statuses = []
        for svc in statuses:
            port = svc.get("port")
            state = (svc.get("state") or "unknown").lower()
            # A disabled service has no endpoint to speak of — listing it just
            # pads the section with rows that can never be tested.
            if not port or state == "disabled":
                continue
            health = svc.get("health_url") or f"http://localhost:{port}/health"
            path = "/" + health.split("://", 1)[-1].partition("/")[2]
            name = svc["name"]
            expose = internal if name in svc_internal else tailnet
            pub, loc, via = expose(int(port))
            params = []
            if svc.get("model"):
                params.append(_param("Model", str(svc["model"])))
            if name in ("kokoro", "whisper-fast"):
                params.append(_param("OpenAI base URL", f"{pub}/v1",
                                     note="mlx_audio.server speaks the OpenAI audio API"))
            add(f"svc:{name}", svc_titles.get(name, name), "Local services",
                svc.get("description") or "",
                url=pub, local_url=loc, via=via, state=state,
                probe={"kind": "http", "path": path or "/health"},
                params=params)

    # Hostnames this box can't resolve itself but every other tailnet device
    # can — probes connect by IP and keep the name for SNI/Host.
    resolve: dict[str, str] = {}
    if net["dns_name"] and net["tailscale_ip"]:
        resolve[net["dns_name"]] = net["tailscale_ip"]

    return {
        "endpoints": endpoints,
        "host": host,
        "network": net,
        "resolve": resolve,
        "tailscale_serve": {str(k): v for k, v in serve.items()},
    }


# ── Probes ──────────────────────────────────────────────────────────────────

def _http_probe(url: str, timeout: float, resolve_ip: str | None = None) -> tuple[bool, str, str]:
    """
    GET `url` and classify the result as (ok, code, detail).

    2xx/3xx is healthy. 401/403/404/405 still counts as reachable — the
    service answered, it just declined an unauthenticated GET, which is what
    LiteLLM and Grafana do on some paths.

    `resolve_ip` connects to that address while keeping the original
    hostname for SNI, certificate validation and the Host header. MagicDNS
    names routinely fail to resolve *on the host itself* even though every
    other tailnet device resolves them, so without this the probe would
    report a working tailscale-serve endpoint as down. This is the same
    override `gw health` gets from `curl --resolve`.
    """
    parts = urllib.parse.urlsplit(url)
    host = parts.hostname or ""
    https = parts.scheme == "https"
    port = parts.port or (443 if https else 80)
    path = parts.path or "/"
    if parts.query:
        path += "?" + parts.query

    if https:
        conn = http.client.HTTPSConnection(
            host, port, timeout=timeout, context=ssl.create_default_context()
        )
    else:
        conn = http.client.HTTPConnection(host, port, timeout=timeout)
    if resolve_ip:
        conn._create_connection = (  # noqa: SLF001 — documented-stable hook
            lambda address, tmo, src, ip=resolve_ip: socket.create_connection((ip, address[1]), tmo, src)
        )

    try:
        conn.request("GET", path, headers={"User-Agent": "llmgateway-dashboard", "Host": host})
        resp = conn.getresponse()
        code, reason = resp.status, (resp.reason or "")
        resp.read(1024)  # drain enough to release the connection
        if 200 <= code < 400:
            return True, str(code), reason
        if code in (401, 403, 404, 405):
            return True, str(code), "responding (auth required)"
        return False, str(code), reason
    except ssl.SSLError as exc:
        return False, "tls", str(exc)
    except socket.timeout:
        return False, "---", f"timed out after {timeout:.0f}s"
    except OSError as exc:
        return False, "---", str(exc)
    except Exception as exc:
        return False, "---", str(exc)
    finally:
        try:
            conn.close()
        except Exception:
            pass


def _tcp_probe(host: str, port: int, timeout: float) -> tuple[bool, str, str]:
    try:
        with socket.create_connection((host, port), timeout=timeout):
            return True, "open", f"TCP connect to {host}:{port} succeeded"
    except OSError as exc:
        return False, "---", str(exc)


async def _exec_probe(container: str, cmd: list[str], expect: str, timeout: float
                      ) -> tuple[bool, str, str]:
    rc, out, err = await _run("docker", "exec", container, *cmd, timeout=timeout)
    text = (out or err or b"").decode(errors="replace").strip()
    if rc != 0:
        return False, "---", text or f"exit {rc}"
    return (expect.lower() in text.lower()), "ok" if expect.lower() in text.lower() else "---", text


# States in which a probe is guaranteed to fail for a boring reason. Reporting
# these as "down" would be true but useless, so they come back marked skipped
# and the dashboard greys the dot instead of reddening it.
_NOT_RUNNING = {"exited", "dead", "created", "paused", "stopped", "disabled", "failed", "absent"}


async def probe(ep: dict[str, Any], timeout: float = 6.0,
                resolve: dict[str, str] | None = None) -> dict[str, Any]:
    """
    Probe one catalog entry. Returns the primary result and, when the public
    URL fails, a secondary localhost result — that pair distinguishes "the
    service is down" from "the service is up but not reachable remotely".

    `resolve` maps hostname → IP for names this host can't resolve itself
    (see _http_probe).
    """
    p = ep.get("probe") or {}
    kind = p.get("kind")
    started = time.monotonic()

    if (ep.get("state") or "").lower() in _NOT_RUNNING:
        return {"id": ep["id"], "ok": False, "skipped": True, "code": "---",
                "detail": f"{ep.get('state')} — not probed", "ms": 0.0, "target": ""}

    if kind == "tcp":
        ok, code, detail = await asyncio.to_thread(
            _tcp_probe, p.get("host", "127.0.0.1"), int(p.get("port", 0)), timeout
        )
        return {"id": ep["id"], "ok": ok, "code": code, "detail": detail,
                "ms": round((time.monotonic() - started) * 1000, 1),
                "target": f"{p.get('host')}:{p.get('port')}"}

    if kind == "exec":
        ok, code, detail = await _exec_probe(
            p["container"], p.get("cmd") or [], p.get("expect", ""), timeout
        )
        return {"id": ep["id"], "ok": ok, "code": code, "detail": detail,
                "ms": round((time.monotonic() - started) * 1000, 1),
                "target": f"docker exec {p['container']}"}

    if kind != "http":
        return {"id": ep["id"], "ok": False, "code": "---", "detail": "no probe defined",
                "ms": 0.0, "target": ""}

    path = p.get("path") or "/"
    base = ep.get("url") or ep.get("local_url") or ""
    primary = base.rstrip("/") + path
    hostname = urllib.parse.urlsplit(primary).hostname or ""
    ip = (resolve or {}).get(hostname)
    ok, code, detail = await asyncio.to_thread(_http_probe, primary, timeout, ip)
    result = {"id": ep["id"], "ok": ok, "code": code, "detail": detail,
              "ms": round((time.monotonic() - started) * 1000, 1), "target": primary}

    # Public URL failed — is the service itself up? Probe loopback to say so.
    local_base = ep.get("local_url") or ""
    if not ok and local_base and local_base.startswith("http"):
        fallback = local_base.rstrip("/") + path
        if fallback != primary:
            lok, lcode, ldetail = await asyncio.to_thread(_http_probe, fallback, timeout)
            result["fallback"] = {"ok": lok, "code": lcode, "detail": ldetail, "target": fallback}
    return result
