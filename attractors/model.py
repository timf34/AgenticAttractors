"""LiteLLM model adapter: native tool-calling with a text-format fallback for
weak tool-callers (self-hosted LoRAs). Pins the OpenRouter provider and logs
the served provider per call as a covariate. No compaction ever — long-context
cost is handled by observation truncation + Anthropic prompt caching."""

from __future__ import annotations

import json
import re
import time
from dataclasses import dataclass, field
from typing import Any

import litellm

from attractors.config import ModelSpec
from attractors.tools import Tool

RETRYABLE = (
    litellm.exceptions.RateLimitError,
    litellm.exceptions.InternalServerError,
    litellm.exceptions.ServiceUnavailableError,
    litellm.exceptions.APIConnectionError,
    litellm.exceptions.Timeout,
)
MAX_ATTEMPTS = 6

_TOOL_BLOCK = re.compile(r"```tool\s*\n(.*?)```", re.DOTALL)


@dataclass
class ToolCallReq:
    call_id: str
    name: str
    args: dict
    parse_error: str | None = None


@dataclass
class Turn:
    text: str | None
    tool_calls: list[ToolCallReq] = field(default_factory=list)
    provider: str | None = None
    usage: dict = field(default_factory=dict)
    cost_usd: float = 0.0
    finish_reason: str | None = None
    latency_ms: int = 0
    attempts: int = 1
    raw_message: dict = field(default_factory=dict)  # assistant msg to append


class ModelAdapter:
    def __init__(self, spec: ModelSpec):
        self.spec = spec
        self.total_cost = 0.0

    # ---- public ----------------------------------------------------------

    def query(self, messages: list[dict], tools: list[Tool]) -> Turn:
        if self.spec.tool_mode == "native":
            return self._query_native(messages, tools)
        return self._query_text(messages)

    def render_tool_messages(self, turn: Turn, observations: list[tuple[ToolCallReq, str]]) -> list[dict]:
        """Messages carrying tool observations back to the model."""
        if self.spec.tool_mode == "native":
            return [
                {"role": "tool", "tool_call_id": call.call_id, "content": obs}
                for call, obs in observations
            ]
        joined = "\n\n".join(obs for _, obs in observations)
        return [{"role": "user", "content": joined}]

    # ---- internals -------------------------------------------------------

    def _completion(self, messages: list[dict], tools_param: list[dict] | None) -> tuple[Any, int, int]:
        kwargs: dict[str, Any] = dict(
            model=self.spec.litellm_model,
            messages=self._maybe_cache(messages),
            max_tokens=self.spec.max_tokens,
            temperature=self.spec.temperature,
            num_retries=0,
        )
        if tools_param:
            kwargs["tools"] = tools_param
        if self.spec.provider_order:
            kwargs["extra_body"] = {
                "provider": {"order": self.spec.provider_order, "allow_fallbacks": False}
            }
        api_base = self.spec.resolved_api_base()
        if api_base:
            kwargs["api_base"] = api_base
        api_key = self.spec.resolved_api_key()
        if api_key:
            kwargs["api_key"] = api_key

        attempt = 0
        while True:
            attempt += 1
            t0 = time.monotonic()
            try:
                resp = litellm.completion(**kwargs)
                return resp, int((time.monotonic() - t0) * 1000), attempt
            except RETRYABLE:
                if attempt >= MAX_ATTEMPTS:
                    raise
                time.sleep(min(2 ** attempt, 60))

    def _maybe_cache(self, messages: list[dict]) -> list[dict]:
        """Anthropic prompt caching via cache_control breakpoints: one on the
        system prompt, one on the last message (cache write covers the whole
        prefix, so each call re-reads the prior conversation from cache)."""
        if not self.spec.prompt_caching:
            return messages
        out = [dict(m) for m in messages]

        def mark(msg: dict) -> None:
            content = msg.get("content")
            if isinstance(content, str):
                msg["content"] = [
                    {"type": "text", "text": content,
                     "cache_control": {"type": "ephemeral"}}
                ]
            elif isinstance(content, list) and content:
                content[-1] = {**content[-1], "cache_control": {"type": "ephemeral"}}

        if out and out[0].get("role") == "system":
            mark(out[0])
        # only user messages get the moving breakpoint: tool-role content has
        # provider-specific block shapes that cache_control could corrupt
        for msg in reversed(out):
            if msg.get("role") == "user" and msg.get("content"):
                mark(msg)
                break
        return out

    def _extract_meta(self, resp: Any, latency_ms: int, attempts: int) -> tuple[str | None, dict, float]:
        provider = getattr(resp, "provider", None)
        if provider is None:
            hidden = getattr(resp, "_hidden_params", {}) or {}
            provider = hidden.get("provider") or (
                hidden.get("additional_headers", {}) or {}
            ).get("x-openrouter-provider")
        usage = {}
        u = getattr(resp, "usage", None)
        if u:
            usage = {
                "prompt_tokens": getattr(u, "prompt_tokens", None),
                "completion_tokens": getattr(u, "completion_tokens", None),
            }
            details = getattr(u, "prompt_tokens_details", None)
            if details is not None:
                usage["cached_tokens"] = getattr(details, "cached_tokens", None)
        cost = 0.0
        try:
            cost = litellm.completion_cost(completion_response=resp) or 0.0
        except Exception:
            if self.spec.input_price_per_m is not None and usage.get("prompt_tokens"):
                cost = (
                    usage["prompt_tokens"] / 1e6 * self.spec.input_price_per_m
                    + (usage.get("completion_tokens") or 0) / 1e6
                    * (self.spec.output_price_per_m or 0.0)
                )
        self.total_cost += cost
        return provider, usage, cost

    def _query_native(self, messages: list[dict], tools: list[Tool]) -> Turn:
        tools_param = [
            {"type": "function",
             "function": {"name": t.name, "description": t.description,
                          "parameters": t.parameters}}
            for t in tools
        ]
        resp, latency_ms, attempts = self._completion(messages, tools_param)
        provider, usage, cost = self._extract_meta(resp, latency_ms, attempts)
        choice = resp.choices[0]
        msg = choice.message
        calls = []
        for tc in msg.tool_calls or []:
            try:
                args = json.loads(tc.function.arguments or "{}")
                err = None
            except json.JSONDecodeError as e:
                args, err = {}, f"bad json args: {e}"
            calls.append(ToolCallReq(tc.id, tc.function.name, args, err))
        raw = {"role": "assistant", "content": msg.content}
        if msg.tool_calls:
            raw["tool_calls"] = [
                {"id": tc.id, "type": "function",
                 "function": {"name": tc.function.name,
                              "arguments": tc.function.arguments}}
                for tc in msg.tool_calls
            ]
        return Turn(
            text=msg.content, tool_calls=calls, provider=provider, usage=usage,
            cost_usd=cost, finish_reason=choice.finish_reason,
            latency_ms=latency_ms, attempts=attempts, raw_message=raw,
        )

    def _query_text(self, messages: list[dict]) -> Turn:
        resp, latency_ms, attempts = self._completion(messages, tools_param=None)
        provider, usage, cost = self._extract_meta(resp, latency_ms, attempts)
        choice = resp.choices[0]
        text = choice.message.content or ""
        calls = []
        m = _TOOL_BLOCK.search(text)
        if m:
            try:
                payload = json.loads(m.group(1))
                calls.append(ToolCallReq(
                    call_id=f"text-{int(time.time() * 1000)}",
                    name=str(payload.get("tool", "")),
                    args=payload.get("args", {}) or {},
                ))
            except json.JSONDecodeError as e:
                calls.append(ToolCallReq(
                    call_id="text-parse-error", name="", args={},
                    parse_error=f"bad json in tool block: {e}",
                ))
        return Turn(
            text=text, tool_calls=calls, provider=provider, usage=usage,
            cost_usd=cost, finish_reason=choice.finish_reason,
            latency_ms=latency_ms, attempts=attempts,
            raw_message={"role": "assistant", "content": text},
        )
