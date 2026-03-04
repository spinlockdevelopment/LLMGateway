"""Anthropic-compatible /v1/messages endpoint.

Translates Anthropic-style requests to the internal format,
routes through the same engine, and returns Anthropic-compatible responses.
"""

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


def _anthropic_to_openai_messages(messages: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Convert Anthropic message format to OpenAI format for LiteLLM."""
    converted = []
    for msg in messages:
        content = msg.get("content", "")
        # Anthropic content can be a list of content blocks
        if isinstance(content, list):
            text_parts = []
            for block in content:
                if isinstance(block, dict) and block.get("type") == "text":
                    text_parts.append(block["text"])
                elif isinstance(block, str):
                    text_parts.append(block)
            content = "\n".join(text_parts)

        converted.append({
            "role": msg.get("role", "user"),
            "content": content,
        })
    return converted


def _openai_to_anthropic_response(raw: dict[str, Any], model: str) -> dict[str, Any]:
    """Convert an OpenAI-style response to Anthropic message format."""
    choices = raw.get("choices", [])
    content = ""
    stop_reason = "end_turn"
    if choices:
        message = choices[0].get("message", {})
        content = message.get("content", "")
        fr = choices[0].get("finish_reason", "stop")
        if fr == "length":
            stop_reason = "max_tokens"
        elif fr == "stop":
            stop_reason = "end_turn"

    usage = raw.get("usage", {})

    return {
        "id": raw.get("id", ""),
        "type": "message",
        "role": "assistant",
        "model": model,
        "content": [{"type": "text", "text": content}],
        "stop_reason": stop_reason,
        "usage": {
            "input_tokens": usage.get("prompt_tokens", 0),
            "output_tokens": usage.get("completion_tokens", 0),
        },
    }


@router.post("/v1/messages")
async def messages(request: Request) -> Any:
    """Anthropic-compatible messages endpoint."""
    body = await request.json()

    auth = request.app.state.auth
    routing_engine = request.app.state.routing_engine
    provider_registry = request.app.state.provider_registry
    usage_tracker: UsageTracker = request.app.state.usage_tracker
    gateway_metrics = request.app.state.metrics
    rate_limiter = request.app.state.rate_limiter

    agent: AgentIdentity = auth.authenticate(request)
    request.state.agent_name = agent.agent_name

    if not rate_limiter.check(agent.agent_id, agent.rate_limit_rpm):
        raise HTTPException(status_code=429, detail="Rate limit exceeded")

    requested_model = body.get("model", "")
    if not requested_model:
        raise HTTPException(status_code=400, detail="Missing 'model' field")

    if not auth.is_model_allowed(agent, requested_model):
        raise HTTPException(status_code=403, detail=f"Model '{requested_model}' not allowed")

    route = routing_engine.resolve(requested_model, agent=agent.agent_id)

    # Convert Anthropic messages to OpenAI format
    anthropic_messages = body.get("messages", [])
    openai_messages = _anthropic_to_openai_messages(anthropic_messages)

    # Handle system message (Anthropic puts it at top level)
    system = body.get("system")
    if system:
        openai_messages.insert(0, {"role": "system", "content": system})

    stream = body.get("stream", False)

    comp_request = CompletionRequest(
        model=route.target.model,
        messages=openai_messages,
        stream=stream,
        temperature=body.get("temperature"),
        max_tokens=body.get("max_tokens"),
        top_p=body.get("top_p"),
        stop=body.get("stop_sequences"),
    )

    adapter = provider_registry.get_default()

    if stream:
        return StreamingResponse(
            _stream_anthropic(adapter, comp_request, route, agent, usage_tracker, gateway_metrics),
            media_type="text/event-stream",
        )

    try:
        response = await adapter.complete(comp_request)
    except Exception as e:
        for fb in route.fallbacks:
            try:
                comp_request.model = fb.model
                response = await adapter.complete(comp_request)
                break
            except Exception:
                continue
        else:
            raise HTTPException(status_code=502, detail=f"Provider error: {e}")

    cost = UsageTracker.estimate_cost(response.model, response.tokens_in, response.tokens_out)
    await usage_tracker.record(UsageRecord(
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
    ))

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

    return _openai_to_anthropic_response(response.raw, response.model)


async def _stream_anthropic(adapter, request, route, agent, usage_tracker, gateway_metrics):
    """Convert OpenAI streaming chunks to Anthropic SSE format."""
    start = time.monotonic()
    total_tokens_in = 0
    total_tokens_out = 0
    block_idx = 0

    # Send message_start event
    yield f"event: message_start\ndata: {json.dumps({'type': 'message_start', 'message': {'id': '', 'type': 'message', 'role': 'assistant', 'model': request.model, 'content': [], 'usage': {'input_tokens': 0, 'output_tokens': 0}}})}\n\n"

    # Send content_block_start
    yield f"event: content_block_start\ndata: {json.dumps({'type': 'content_block_start', 'index': 0, 'content_block': {'type': 'text', 'text': ''}})}\n\n"

    try:
        async for chunk in adapter.stream(request):
            if "error" in chunk:
                yield f"event: error\ndata: {json.dumps(chunk)}\n\n"
                return

            choices = chunk.get("choices", [])
            if choices:
                delta = choices[0].get("delta", {})
                content = delta.get("content", "")
                if content:
                    yield f"event: content_block_delta\ndata: {json.dumps({'type': 'content_block_delta', 'index': 0, 'delta': {'type': 'text_delta', 'text': content}})}\n\n"

            usage = chunk.get("usage")
            if usage:
                total_tokens_in = usage.get("prompt_tokens", total_tokens_in)
                total_tokens_out = usage.get("completion_tokens", total_tokens_out)

        # content_block_stop
        yield f"event: content_block_stop\ndata: {json.dumps({'type': 'content_block_stop', 'index': 0})}\n\n"

        # message_delta
        yield f"event: message_delta\ndata: {json.dumps({'type': 'message_delta', 'delta': {'stop_reason': 'end_turn'}, 'usage': {'output_tokens': total_tokens_out}})}\n\n"

        # message_stop
        yield f"event: message_stop\ndata: {json.dumps({'type': 'message_stop'})}\n\n"

    finally:
        latency_ms = (time.monotonic() - start) * 1000
        cost = UsageTracker.estimate_cost(request.model, total_tokens_in, total_tokens_out)
        await usage_tracker.record(UsageRecord(
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
        ))
