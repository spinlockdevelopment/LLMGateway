"""OpenAI-compatible /v1/chat/completions endpoint."""

from __future__ import annotations

import json
import logging
import time
from typing import Any

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import StreamingResponse

from llm_gateway.auth.tokens import AgentIdentity
from llm_gateway.providers.base import CompletionRequest
from llm_gateway.tracking.usage import UsageRecord, UsageTracker

logger = logging.getLogger(__name__)

router = APIRouter()


@router.post("/v1/chat/completions")
async def chat_completions(request: Request) -> Any:
    """OpenAI-compatible chat completions endpoint.

    Routes through pseudo-model resolution, provider adapter, and records usage.
    """
    body = await request.json()

    # Dependencies injected via app.state
    auth = request.app.state.auth
    routing_engine = request.app.state.routing_engine
    provider_registry = request.app.state.provider_registry
    usage_tracker: UsageTracker = request.app.state.usage_tracker
    gateway_metrics = request.app.state.metrics
    rate_limiter = request.app.state.rate_limiter

    # Authenticate
    agent: AgentIdentity = auth.authenticate(request)
    request.state.agent_name = agent.agent_name

    # Rate limit
    if not rate_limiter.check(agent.agent_id, agent.rate_limit_rpm):
        raise HTTPException(status_code=429, detail="Rate limit exceeded")

    # Resolve model
    requested_model = body.get("model", "")
    if not requested_model:
        raise HTTPException(status_code=400, detail="Missing 'model' field")

    if not auth.is_model_allowed(agent, requested_model):
        raise HTTPException(status_code=403, detail=f"Model '{requested_model}' not allowed for this agent")

    route = routing_engine.resolve(
        requested_model,
        agent=agent.agent_id,
        request_type=agent.metadata.get("x-request-type", ""),
    )

    logger.info(
        "Routing decision",
        extra={
            "agent": agent.agent_id,
            "pseudo_model": route.pseudo_model,
            "target_model": route.target.model,
            "provider": route.target.provider,
            "strategy": route.strategy,
        },
    )

    # Build completion request
    stream = body.get("stream", False)

    # Separate known params from extra pass-through params
    known_keys = {"model", "messages", "stream", "temperature", "max_tokens", "top_p", "stop"}
    extra = {k: v for k, v in body.items() if k not in known_keys}

    comp_request = CompletionRequest(
        model=route.target.model,
        messages=body.get("messages", []),
        stream=stream,
        temperature=body.get("temperature"),
        max_tokens=body.get("max_tokens"),
        top_p=body.get("top_p"),
        stop=body.get("stop"),
        extra=extra,
    )

    adapter = provider_registry.get_default()

    if stream:
        return StreamingResponse(
            _stream_response(
                adapter, comp_request, route, agent, usage_tracker, gateway_metrics
            ),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
                "X-Accel-Buffering": "no",
            },
        )

    # Non-streaming
    try:
        response = await adapter.complete(comp_request)
    except Exception as e:
        # Try fallbacks
        for fb in route.fallbacks:
            try:
                comp_request.model = fb.model
                response = await adapter.complete(comp_request)
                logger.info("Fallback succeeded: %s -> %s", route.target.model, fb.model)
                break
            except Exception:
                continue
        else:
            logger.error("All providers failed for %s: %s", requested_model, e)
            raise HTTPException(status_code=502, detail=f"Provider error: {e}")

    # Record usage
    cost = UsageTracker.estimate_cost(response.model, response.tokens_in, response.tokens_out)
    record = UsageRecord(
        timestamp=time.time(),
        agent_id=agent.agent_id,
        agent_name=agent.agent_name,
        request_type=agent.metadata.get("x-request-type", ""),
        pseudo_model=route.pseudo_model,
        selected_model=response.model,
        provider=response.provider,
        tokens_in=response.tokens_in,
        tokens_out=response.tokens_out,
        estimated_cost=cost,
        latency_ms=response.latency_ms,
        transaction_id=agent.metadata.get("x-transaction-id", ""),
    )
    await usage_tracker.record(record)

    # Record metrics
    if gateway_metrics:
        gateway_metrics.record_request(
            agent=agent.agent_id,
            pseudo_model=route.pseudo_model,
            provider=response.provider,
            model=response.model,
            strategy=route.strategy,
            tokens_in=response.tokens_in,
            tokens_out=response.tokens_out,
            cost=cost,
            latency_ms=response.latency_ms,
        )

    logger.info(
        "completion",
        extra={
            "agent": agent.agent_id,
            "pseudo_model": route.pseudo_model,
            "selected_model": response.model,
            "provider": response.provider,
            "tokens_in": response.tokens_in,
            "tokens_out": response.tokens_out,
            "estimated_cost": cost,
            "latency_ms": round(response.latency_ms, 2),
        },
    )

    return response.raw


async def _stream_response(
    adapter, request, route, agent, usage_tracker, gateway_metrics
):
    """Stream SSE chunks and record usage when complete."""
    total_tokens_in = 0
    total_tokens_out = 0
    start = time.monotonic()

    try:
        async for chunk in adapter.stream(request):
            if "error" in chunk:
                yield f"data: {json.dumps(chunk)}\n\n"
                return

            # Track token counts from streaming usage if available
            usage = chunk.get("usage")
            if usage:
                total_tokens_in = usage.get("prompt_tokens", total_tokens_in)
                total_tokens_out = usage.get("completion_tokens", total_tokens_out)

            yield f"data: {json.dumps(chunk)}\n\n"

        yield "data: [DONE]\n\n"

    finally:
        latency_ms = (time.monotonic() - start) * 1000
        cost = UsageTracker.estimate_cost(request.model, total_tokens_in, total_tokens_out)

        record = UsageRecord(
            timestamp=time.time(),
            agent_id=agent.agent_id,
            agent_name=agent.agent_name,
            request_type=agent.metadata.get("x-request-type", ""),
            pseudo_model=route.pseudo_model,
            selected_model=request.model,
            provider=route.target.provider,
            tokens_in=total_tokens_in,
            tokens_out=total_tokens_out,
            estimated_cost=cost,
            latency_ms=latency_ms,
            transaction_id=agent.metadata.get("x-transaction-id", ""),
        )
        await usage_tracker.record(record)

        if gateway_metrics:
            gateway_metrics.record_request(
                agent=agent.agent_id,
                pseudo_model=route.pseudo_model,
                provider=route.target.provider,
                model=request.model,
                strategy=route.strategy,
                tokens_in=total_tokens_in,
                tokens_out=total_tokens_out,
                cost=cost,
                latency_ms=latency_ms,
            )
