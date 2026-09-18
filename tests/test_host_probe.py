"""Tests for host_probe — Docker diagnosis, container listing, Tailscale parsing."""
import json

import host_probe as probe


def _fake_run(responses):
    """Build a _run replacement keyed on the command's leading words."""
    def run(cmd, timeout=10, env=None):
        for prefix, result in responses.items():
            if tuple(cmd[:len(prefix)]) == prefix:
                return result(env) if callable(result) else result
        return (1, "", "")
    return run


# ── Docker diagnosis ─────────────────────────────────────────────────────────

def test_docker_ok(monkeypatch):
    monkeypatch.setattr(probe.shutil, "which", lambda _: "/usr/bin/docker")
    monkeypatch.setattr(probe, "_run", _fake_run({("docker", "info"): (0, "27.0\n", "")}))
    assert probe.docker_status().state == "ok"


def test_docker_running_as_other_user(monkeypatch):
    monkeypatch.setattr(probe.shutil, "which", lambda _: "/usr/bin/docker")
    monkeypatch.setattr(probe.os.path, "exists", lambda _: False)
    monkeypatch.setenv("USER", "llmuser")
    monkeypatch.delenv("DOCKER_HOST", raising=False)
    monkeypatch.setattr(probe, "_run", _fake_run({
        ("docker", "info"): (1, "", "dial unix /Users/llmuser/.docker/run/docker.sock: no such file"),
        ("pgrep",): (0, "7343\n", ""),
        ("ps",): (0, "llmadmin\n", ""),
    }))
    ds = probe.docker_status()
    assert ds.state == "no_access"
    assert ds.owner == "llmadmin"
    assert "llmadmin" in ds.detail


def test_docker_fallback_socket_sets_docker_host(monkeypatch):
    monkeypatch.setattr(probe.shutil, "which", lambda _: "/usr/bin/docker")
    monkeypatch.setattr(probe.os.path, "exists", lambda _: True)
    monkeypatch.delenv("DOCKER_HOST", raising=False)
    monkeypatch.setattr(probe, "_run", _fake_run({
        ("docker", "info"): lambda env: (0, "27.0", "") if env else (1, "", "no such file"),
    }))
    ds = probe.docker_status()
    assert ds.state == "ok"
    assert probe.os.environ["DOCKER_HOST"] == "unix:///var/run/docker.sock"


def test_docker_not_running(monkeypatch):
    monkeypatch.setattr(probe.shutil, "which", lambda _: "/usr/bin/docker")
    monkeypatch.setattr(probe.os.path, "exists", lambda _: False)
    monkeypatch.setattr(probe, "_run", _fake_run({("docker", "info"): (1, "", "no such file")}))
    assert probe.docker_status().state == "not_running"


def test_docker_not_installed(monkeypatch):
    monkeypatch.setattr(probe.shutil, "which", lambda _: None)
    assert probe.docker_status().state == "not_installed"


# ── Containers ───────────────────────────────────────────────────────────────

def test_list_containers(monkeypatch):
    rows = [
        {"Names": "llm-gateway", "State": "running", "Status": "Up 2 hours (healthy)",
         "Image": "ghcr.io/berriai/litellm:main-latest",
         "Ports": "0.0.0.0:4000->4000/tcp, [::]:4000->4000/tcp"},
        {"Names": "open-webui", "State": "running", "Status": "Up 1 hour (health: starting)",
         "Image": "ghcr.io/open-webui/open-webui:main", "Ports": "0.0.0.0:3001->8080/tcp"},
        {"Names": "old", "State": "exited", "Status": "Exited (0) 3 days ago",
         "Image": "busybox", "Ports": ""},
    ]
    out = "\n".join(json.dumps(r) for r in rows)
    monkeypatch.setattr(probe, "_run", _fake_run({("docker", "ps"): (0, out, "")}))
    by_name = {c.name: c for c in probe.list_containers()}
    assert by_name["llm-gateway"].state == "running"
    assert by_name["llm-gateway"].ports == [4000]
    assert by_name["open-webui"].state == "starting"
    assert by_name["open-webui"].ports == [3001]
    assert by_name["old"].state == "stopped"
    assert by_name["old"].ports == []


# ── Tailscale ────────────────────────────────────────────────────────────────

def test_tailnet_info_parses_serve(monkeypatch):
    status = {"BackendState": "Running",
              "Self": {"DNSName": "llmgateway.tailb2d65a.ts.net.",
                       "TailscaleIPs": ["100.113.119.69", "fd7a:115c:a1e0::834:7746"]}}
    serve = {"TCP": {"443": {"HTTPS": True}, "8443": {"HTTPS": True}},
             "Web": {
                 "llmgateway.tailb2d65a.ts.net:443": {"Handlers": {"/": {"Proxy": "http://127.0.0.1:4000"}}},
                 "llmgateway.tailb2d65a.ts.net:8443": {"Handlers": {"/": {"Proxy": "http://127.0.0.1:3001"}}},
             }}
    monkeypatch.setattr(probe.shutil, "which", lambda _: "/usr/bin/tailscale")
    monkeypatch.setattr(probe, "_run", _fake_run({
        ("tailscale", "status"): (0, json.dumps(status), ""),
        ("tailscale", "serve"): (0, json.dumps(serve), ""),
    }))
    tn = probe.tailnet_info()
    assert tn.up
    assert tn.dns_name == "llmgateway.tailb2d65a.ts.net"
    assert tn.ip == "100.113.119.69"
    assert tn.serve == {
        4000: ["https://llmgateway.tailb2d65a.ts.net"],
        3001: ["https://llmgateway.tailb2d65a.ts.net:8443"],
    }


def test_tailnet_down(monkeypatch):
    monkeypatch.setattr(probe.shutil, "which", lambda _: "/usr/bin/tailscale")
    monkeypatch.setattr(probe, "_run", _fake_run({
        ("tailscale", "status"): (0, json.dumps({"BackendState": "Stopped"}), ""),
    }))
    assert not probe.tailnet_info().up
