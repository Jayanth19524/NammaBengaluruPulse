"""LLM access behind a tiny interface. OpenRouter speaks the OpenAI chat-completions format,
so any OpenRouter model with tool calling works (set OPENROUTER_MODEL)."""
from __future__ import annotations

import os
import time
from dataclasses import dataclass, field
from typing import Callable, Protocol

import httpx

DEFAULT_MODEL = "meta-llama/llama-3.3-70b-instruct"  # open-weights model with tool calling; override with OPENROUTER_MODEL
BASE_URL = "https://openrouter.ai/api/v1"


class LLMError(Exception):
    pass


@dataclass
class ToolCall:
    id: str
    name: str
    arguments: str  # raw JSON string, as models return it


@dataclass
class LLMReply:
    content: str | None = None
    tool_calls: list[ToolCall] = field(default_factory=list)

    def as_message(self) -> dict:
        msg: dict = {"role": "assistant", "content": self.content or ""}
        if self.tool_calls:
            msg["tool_calls"] = [{"id": t.id, "type": "function", "function": {"name": t.name, "arguments": t.arguments}}
                                 for t in self.tool_calls]
        return msg


class LLMClient(Protocol):
    model: str

    def chat(self, messages: list[dict], tools: list[dict]) -> LLMReply: ...


class OpenRouterClient:
    def __init__(self, api_key: str, model: str = DEFAULT_MODEL, base_url: str = BASE_URL,
                 client: httpx.Client | None = None, timeout: float = 90.0, retries: int = 2,
                 sleep: Callable[[float], None] = time.sleep):
        self.api_key, self.model, self.base_url = api_key, model, base_url.rstrip("/")
        self._client, self.timeout, self.retries, self._sleep = client, timeout, retries, sleep

    def chat(self, messages: list[dict], tools: list[dict]) -> LLMReply:
        body = {"model": self.model, "messages": messages, "temperature": 0}
        if tools:
            body["tools"], body["tool_choice"] = tools, "auto"
        last = "unknown error"
        for attempt in range(self.retries + 1):
            try:
                c = self._client or httpx.Client(timeout=self.timeout)
                r = c.post(f"{self.base_url}/chat/completions", json=body,
                           headers={"Authorization": f"Bearer {self.api_key}", "X-Title": "NammaPulse"})
                if r.status_code in (429, 500, 502, 503, 504) and attempt < self.retries:
                    last = f"HTTP {r.status_code}"
                    self._sleep(1.5 * (attempt + 1))
                    continue
                r.raise_for_status()
                msg = r.json()["choices"][0]["message"]
                calls = [ToolCall(id=t["id"], name=t["function"]["name"], arguments=t["function"].get("arguments") or "{}")
                         for t in (msg.get("tool_calls") or [])]
                return LLMReply(content=msg.get("content"), tool_calls=calls)
            except (httpx.HTTPError, KeyError, IndexError, ValueError) as exc:
                last = str(exc)
                if attempt < self.retries and isinstance(exc, httpx.TransportError):
                    self._sleep(1.5 * (attempt + 1))
                    continue
                break
        raise LLMError(f"OpenRouter request failed: {last}")


def from_env() -> OpenRouterClient | None:
    """None when no key is configured, so callers can fall back to deterministic behaviour."""
    key = os.environ.get("OPENROUTER_API_KEY")
    if not key:
        return None
    return OpenRouterClient(key, os.environ.get("OPENROUTER_MODEL", DEFAULT_MODEL))


class ScriptedLLM:
    """Deterministic stand-in for tests: replays prepared replies (or callables of the messages)."""
    model = "scripted"

    def __init__(self, replies: list):
        self.replies, self.calls = list(replies), []

    def chat(self, messages, tools):
        self.calls.append(list(messages))
        if not self.replies:
            raise LLMError("script exhausted")
        r = self.replies.pop(0)
        return r(messages) if callable(r) else r
