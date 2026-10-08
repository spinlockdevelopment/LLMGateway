"""PII guardrails for traffic that leaves the box.

Two guardrails, both default_on and both skipped for local-only routes
(every deployment's api_base is on this host), so `local` & co. can carry PII:

  pii-mask  (LocalAwarePresidio) masks structured PII (names, emails, SSNs,
            cards...) with numbered tokens and restores them in the response.
  pii-laya  (LayaPII) then asks Laya whether the masked request still
            reveals what masking can't remove -- a person's health or
            finances -- and blocks above a threshold. (Asking Laya "is there
            PII?" doesn't work: it flags "my name is <PERSON_1>" as PII.)

Unknown models count as remote, so a new cloud route is guarded by default.
Mounted into the LiteLLM container at /app/pii_guard.py.
"""
from __future__ import annotations

import json
import re
from urllib.parse import urlparse

import httpx
from fastapi import HTTPException
from litellm.integrations.custom_guardrail import CustomGuardrail
from litellm.proxy.guardrails.guardrail_hooks.presidio import _OPTIONAL_PresidioPIIMasking
from litellm.types.guardrails import GuardrailEventHooks

LOCAL_HOSTS = {"host.docker.internal", "localhost", "127.0.0.1"}

# Laya's `state` limit is 50k chars; the newest text is what's new this turn.
MAX_LAYA_CHARS = 20000

# Presidio's numbered tokens (<PERSON_1>) read as PII to Laya; "someone" doesn't.
MASK_TOKEN = re.compile(r"<[A-Z_]+_\d+>")

LAYA_QUESTIONS = {
    "health": "Does the text reveal a medical or health condition of a specific real person?",
    "finances": "Does the text reveal the finances, debts, or account details of a specific real person?",
}


def is_local_route(data: dict) -> bool:
    """True only if every deployment behind data['model'] is on this host."""
    from litellm.proxy.proxy_server import llm_router

    model = data.get("model")
    if not model or llm_router is None:
        return False
    deployments = llm_router.get_model_list(model_name=model) or []
    if not deployments:
        return False
    return all(
        urlparse((d.get("litellm_params") or {}).get("api_base") or "").hostname in LOCAL_HOSTS
        for d in deployments
    )


def _text_of(content) -> str:
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        return "\n".join(
            p.get("text", "") for p in content if isinstance(p, dict) and isinstance(p.get("text"), str)
        )
    return ""


def latest_user_text(data: dict) -> str:
    """Newest user-authored text across chat, Anthropic, Responses and text APIs."""
    for m in reversed(data.get("messages") or []):
        if isinstance(m, dict) and m.get("role") == "user":
            return _text_of(m.get("content"))
    inp = data.get("input")
    if isinstance(inp, list):
        for item in reversed(inp):
            if isinstance(item, dict) and item.get("role", "user") == "user":
                return _text_of(item.get("content"))
    if inp is not None:
        return _text_of(inp)
    return _text_of(data.get("prompt"))


class SSEUnmasker:
    """Unmask Presidio tokens in Anthropic SSE text deltas, holding back a
    trailing partial "<TOKEN" until the rest arrives. Assumes each chunk holds
    whole SSE lines, as LiteLLM's own unmasker does."""

    def __init__(self, tokens: dict[str, str]):
        self.tokens = tokens
        self.max_len = max(len(t) for t in tokens)
        self.pending: dict[int, str] = {}

    def _unmask(self, text: str) -> str:
        for token, original in self.tokens.items():
            text = text.replace(token, original)
        return text

    def _split(self, text: str) -> tuple[str, str]:
        i = text.rfind("<")
        if i != -1 and ">" not in text[i:] and len(text) - i < self.max_len:
            return text[:i], text[i:]
        return text, ""

    @staticmethod
    def _delta_event(index: int, text: str) -> list[str]:
        ev = {"type": "content_block_delta", "index": index, "delta": {"type": "text_delta", "text": text}}
        return ["event: content_block_delta", "data: " + json.dumps(ev, ensure_ascii=False), ""]

    def feed(self, chunk: bytes) -> bytes:
        try:
            text = chunk.decode("utf-8")
        except UnicodeDecodeError:
            return chunk
        out: list[str] = []
        for line in text.split("\n"):
            if line.startswith("data: ") and line != "data: [DONE]":
                try:
                    ev = json.loads(line[6:])
                except ValueError:
                    ev = None
                if isinstance(ev, dict):
                    idx, delta = ev.get("index", 0), ev.get("delta") or {}
                    if ev.get("type") == "content_block_delta" and delta.get("type") == "text_delta":
                        emit, self.pending[idx] = self._split(self.pending.get(idx, "") + delta.get("text", ""))
                        delta["text"] = self._unmask(emit)
                        line = "data: " + json.dumps(ev, ensure_ascii=False)
                    elif ev.get("type") == "content_block_stop" and self.pending.get(idx):
                        # Flush the held text as its own delta just before the stop.
                        event_line = out.pop() if out and out[-1].startswith("event:") else None
                        out += self._delta_event(idx, self._unmask(self.pending.pop(idx)))
                        if event_line:
                            out.append(event_line)
            out.append(line)
        return "\n".join(out).encode("utf-8")

    def flush_all(self) -> bytes:
        """Held text left when the stream ends without content_block_stop."""
        lines = [l for idx, t in self.pending.items() if t for l in self._delta_event(idx, self._unmask(t))]
        self.pending.clear()
        return ("\n".join(lines) + "\n").encode("utf-8") if lines else b""


class LocalAwarePresidio(_OPTIONAL_PresidioPIIMasking):
    # LiteLLM only dispatches hooks found in the leaf class's own __dict__
    # (proxy/utils.py _callback_capabilities), so re-declare the inherited
    # ones or streamed responses come back still masked.
    async_pre_call_hook = _OPTIONAL_PresidioPIIMasking.async_pre_call_hook

    async def async_post_call_streaming_iterator_hook(self, user_api_key_dict, response, request_data):
        tokens = ((request_data or {}).get("metadata") or {}).get("pii_tokens") or {}
        first = None
        async for first in response:
            break
        if first is None:
            return

        async def rest():
            yield first
            async for c in response:
                yield c

        # Raw Anthropic SSE (/v1/messages): the built-in per-chunk unmask breaks
        # tokens split across chunks, so buffer them. Everything else: built-in.
        if isinstance(first, bytes) and self.output_parse_pii and tokens:
            sse = SSEUnmasker(tokens)
            async for c in rest():
                yield sse.feed(c) if isinstance(c, bytes) else c
            if tail := sse.flush_all():
                yield tail
            return
        async for c in super().async_post_call_streaming_iterator_hook(user_api_key_dict, rest(), request_data):
            yield c

    def uses_apply_guardrail_interface(self) -> bool:
        # Otherwise /v1/messages streams skip the unmask hook above and get
        # the generic apply_guardrail pass, which masks instead of unmasking.
        return False

    def should_run_guardrail(self, data, event_type: GuardrailEventHooks) -> bool:
        if is_local_route(data):
            return False
        return super().should_run_guardrail(data=data, event_type=event_type)


class LayaPII(CustomGuardrail):
    def __init__(self, laya_api_base: str, threshold: float = 0.7, fail_closed: bool = True, **kwargs):
        super().__init__(**kwargs)
        self.url = laya_api_base.rstrip("/") + "/v1/systemone"
        self.threshold = float(threshold)
        self.fail_closed = fail_closed
        self.client = httpx.AsyncClient(timeout=10)

    async def score(self, text: str) -> tuple[str, float]:
        """Highest-scoring question as (name, P(true))."""
        body = {"state": MASK_TOKEN.sub("someone", text)[-MAX_LAYA_CHARS:],
                "questions": {k: {"type": "noul", "instructions": q} for k, q in LAYA_QUESTIONS.items()}}
        r = await self.client.post(self.url, json=body)
        r.raise_for_status()
        answers = r.json()["answers"]
        return max(((k, float(answers[k]["noul"])) for k in LAYA_QUESTIONS), key=lambda kv: kv[1])

    async def async_pre_call_hook(self, user_api_key_dict, cache, data: dict, call_type):
        if not self.should_run_guardrail(data=data, event_type=GuardrailEventHooks.pre_call):
            return data
        if is_local_route(data):
            return data
        text = latest_user_text(data)
        if not text.strip():
            return data
        try:
            kind, p = await self.score(text)
        except Exception as e:
            if not self.fail_closed:
                return data
            # Fail closed: an unreachable classifier must not wave PII through.
            raise HTTPException(status_code=503, detail={
                "error": f"PII guard unavailable (Laya: {type(e).__name__}); use a local route or retry."})
        if p >= self.threshold:
            raise HTTPException(status_code=400, detail={
                "error": f"PII guard: request reveals someone's {kind} "
                         f"(Laya p={p:.2f} >= {self.threshold}). Use the `local` route for private data."})
        return data
