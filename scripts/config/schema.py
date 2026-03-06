"""
Configuration validation rules for LLM Gateway.

Validates:
  - Required top-level keys
  - Port numbers (valid range, no conflicts)
  - URL well-formedness
  - YAML structure (types of nested values)

Does NOT validate:
  - Model names (to allow future/custom models)
  - Binary paths (checked at runtime by service managers)
"""

from __future__ import annotations

from urllib.parse import urlparse


def validate_config(config: dict) -> tuple[list[str], list[str]]:
    """
    Validate a parsed config dict.

    Returns:
        (errors, warnings) — errors prevent saving; warnings are informational.
    """
    errors: list[str] = []
    warnings: list[str] = []

    if not isinstance(config, dict):
        return ["Config must be a YAML mapping (dict)"], []

    # ── gateway section ───────────────────────────────────────────────────────
    gateway = config.get("gateway")
    if gateway is not None:
        if not isinstance(gateway, dict):
            errors.append("'gateway' must be a mapping")
        else:
            _check_port(gateway.get("port"), "gateway.port", errors)
            log_level = gateway.get("log_level")
            if log_level and log_level not in ("DEBUG", "INFO", "WARNING", "ERROR"):
                warnings.append(
                    f"gateway.log_level '{log_level}' is not a standard level"
                )

    # ── services section ──────────────────────────────────────────────────────
    services = config.get("services")
    if services is not None:
        if not isinstance(services, dict):
            errors.append("'services' must be a mapping")
        else:
            seen_ports: dict[int, str] = {}
            for svc_name, svc in services.items():
                if not isinstance(svc, dict):
                    errors.append(f"services.{svc_name} must be a mapping")
                    continue

                # Port validation
                port = svc.get("port")
                if port is not None:
                    _check_port(port, f"services.{svc_name}.port", errors)
                    if isinstance(port, int) and 1 <= port <= 65535:
                        if port in seen_ports:
                            errors.append(
                                f"Port conflict: services.{svc_name}.port ({port}) "
                                f"is already used by services.{seen_ports[port]}"
                            )
                        seen_ports[port] = svc_name

                # Port in args dict (llama-server style)
                args = svc.get("args")
                if isinstance(args, dict):
                    arg_port = args.get("--port")
                    if arg_port is not None:
                        try:
                            arg_port_int = int(arg_port)
                            _check_port(
                                arg_port_int,
                                f"services.{svc_name}.args.--port",
                                errors,
                            )
                            if arg_port_int in seen_ports:
                                errors.append(
                                    f"Port conflict: services.{svc_name}.args.--port "
                                    f"({arg_port_int}) is already used by "
                                    f"services.{seen_ports[arg_port_int]}"
                                )
                            seen_ports[arg_port_int] = svc_name
                        except (ValueError, TypeError):
                            errors.append(
                                f"services.{svc_name}.args.--port must be a number"
                            )

                # Health check URL validation
                health_url = svc.get("health_check_url")
                if health_url and isinstance(health_url, str):
                    _check_url(health_url, f"services.{svc_name}.health_check_url", errors)

                # Enabled services with no binary get a warning
                if svc.get("enabled") and not svc.get("binary"):
                    warnings.append(
                        f"services.{svc_name} is enabled but has no 'binary' set"
                    )

            # Check gateway port doesn't conflict with services
            gw_port = (config.get("gateway") or {}).get("port")
            if isinstance(gw_port, int) and gw_port in seen_ports:
                errors.append(
                    f"Port conflict: gateway.port ({gw_port}) "
                    f"is already used by services.{seen_ports[gw_port]}"
                )

    # ── docker section ────────────────────────────────────────────────────────
    docker = config.get("docker")
    if docker is not None and not isinstance(docker, dict):
        errors.append("'docker' must be a mapping")

    # ── health_check section ──────────────────────────────────────────────────
    hc = config.get("health_check")
    if hc is not None:
        if not isinstance(hc, dict):
            errors.append("'health_check' must be a mapping")
        else:
            interval = hc.get("interval_sec")
            if interval is not None and (not isinstance(interval, (int, float)) or interval <= 0):
                errors.append("health_check.interval_sec must be a positive number")
            max_restarts = hc.get("max_restart_attempts")
            if max_restarts is not None and (not isinstance(max_restarts, int) or max_restarts < 0):
                errors.append("health_check.max_restart_attempts must be a non-negative integer")

    # ── memory section ────────────────────────────────────────────────────────
    mem = config.get("memory")
    if mem is not None:
        if not isinstance(mem, dict):
            errors.append("'memory' must be a mapping")
        else:
            threshold = mem.get("pressure_threshold")
            if threshold is not None:
                if not isinstance(threshold, (int, float)) or not (0 < threshold <= 1.0):
                    errors.append(
                        "memory.pressure_threshold must be between 0.0 and 1.0"
                    )

    return errors, warnings


# ── Validation helpers ────────────────────────────────────────────────────────

def _check_port(value: object, field: str, errors: list[str]) -> None:
    """Validate a port number is in 1–65535 range."""
    if value is None:
        return
    try:
        port = int(value)
    except (ValueError, TypeError):
        errors.append(f"{field} must be a number, got: {value!r}")
        return
    if not (1 <= port <= 65535):
        errors.append(f"{field} must be between 1 and 65535, got: {port}")


def _check_url(url: str, field: str, errors: list[str]) -> None:
    """Validate a URL has a scheme and host."""
    try:
        parsed = urlparse(url)
        if not parsed.scheme or not parsed.netloc:
            errors.append(f"{field} is not a well-formed URL: {url!r}")
    except Exception:
        errors.append(f"{field} is not a valid URL: {url!r}")
