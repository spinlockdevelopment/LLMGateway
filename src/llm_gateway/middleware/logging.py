"""Structured JSON logging middleware."""

from __future__ import annotations

import logging
import time
import uuid

from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint

logger = logging.getLogger("llm_gateway.access")


class RequestLoggingMiddleware(BaseHTTPMiddleware):
    """Log every request/response with structured JSON fields."""

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        request_id = request.headers.get("x-request-id", str(uuid.uuid4())[:8])
        request.state.request_id = request_id
        start = time.monotonic()

        response = await call_next(request)

        duration_ms = (time.monotonic() - start) * 1000

        logger.info(
            "request",
            extra={
                "request_id": request_id,
                "method": request.method,
                "path": request.url.path,
                "status": response.status_code,
                "duration_ms": round(duration_ms, 2),
                "agent": getattr(request.state, "agent_name", ""),
                "client": request.client.host if request.client else "",
            },
        )

        response.headers["x-request-id"] = request_id
        return response
