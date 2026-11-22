"""LLM access behind a tiny interface.

Two backends are supported — both speak the OpenAI chat-completions format:

* **BobClient** (preferred) — IBM Bob inference gateway.  Set BOB_API_KEY and
  BOB_BASE_URL (e.g. https://api.bob.example.com/v1) to use your Bob AI credits.
  Create an *Inference*-scoped API key in the Bob web portal so no extra headers
  are needed.

* **OpenRouterClient** (fallback) — set OPENROUTER_API_KEY.  Any OpenRouter model
  that supports tool calling works; override the default with OPENROUTER_MODEL.

``from_env()`` returns a BobClient when BOB_API_KEY is present, otherwise an
OpenRouterClient when OPENROUTER_API_KEY is present, otherwise None (runs fall
back to deterministic checks).
"""
from __future__ import annotations

import os
import time
from dataclasses import dataclass, field
from typing import Callable, Protocol

import httpx

DEFAULT_MODEL = "meta-llama/llama-3.3-70b-instruct"  # override with OPENROUTER_MODEL / BOB_MODEL
OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1"


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


def _openai_chat(base_url: str, api_key: str, extra_headers: dict,
                 model: str, messages: list[dict], tools: list[dict],
                 client: httpx.Client | None, timeout: float, retries: int,
                 sleep: Callable[[float], None], provider: str) -> LLMReply:
    """Shared OpenAI-compatible chat-completions call used by both clients."""
    body: dict = {"model": model, "messages": messages, "temperature": 0}
    if tools:
        body["tools"], body["tool_choice"] = tools, "auto"
    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json", **extra_headers}
    last = "unknown error"
    for attempt in range(retries + 1):
        try:
            c = client or httpx.Client(timeout=timeout)
            r = c.post(f"{base_url}/chat/completions", json=body, headers=headers)
            if r.status_code in (429, 500, 502, 503, 504) and attempt < retries:
                last = f"HTTP {r.status_code}"
                sleep(1.5 * (attempt + 1))
                continue
            r.raise_for_status()
            msg = r.json()["choices"][0]["message"]
            calls = [ToolCall(id=t["id"], name=t["function"]["name"], arguments=t["function"].get("arguments") or "{}")
                     for t in (msg.get("tool_calls") or [])]
            return LLMReply(content=msg.get("content"), tool_calls=calls)
        except (httpx.HTTPError, KeyError, IndexError, ValueError) as exc:
            last = str(exc)
            if attempt < retries and isinstance(exc, httpx.TransportError):
                sleep(1.5 * (attempt + 1))
                continue
            break
    raise LLMError(f"{provider} request failed: {last}")


class BobClient:
    """IBM Bob inference gateway (OpenAI-compatible).

    Prerequisites:
    - Create an *Inference*-scoped API key in the Bob web portal.
    - Set BOB_API_KEY to that key.
    - Set BOB_BASE_URL to your gateway endpoint, e.g. https://api.bob.example.com/v1
    - Set BOB_MODEL to the model_name configured in your Bob model gateway
      (defaults to the same open-weights default as OpenRouter).
    """

    def __init__(self, api_key: str, model: str = DEFAULT_MODEL, base_url: str = "",
                 client: httpx.Client | None = None, timeout: float = 90.0, retries: int = 2,
                 sleep: Callable[[float], None] = time.sleep):
        if not base_url:
            raise ValueError("BOB_BASE_URL must be set to your Bob gateway endpoint (e.g. https://api.bob.example.com/v1)")
        self.api_key, self.model, self.base_url = api_key, model, base_url.rstrip("/")
        self._client, self.timeout, self.retries, self._sleep = client, timeout, retries, sleep

    def chat(self, messages: list[dict], tools: list[dict]) -> LLMReply:
        return _openai_chat(self.base_url, self.api_key, {}, self.model, messages, tools,
                            self._client, self.timeout, self.retries, self._sleep, "Bob")


class OpenRouterClient:
    def __init__(self, api_key: str, model: str = DEFAULT_MODEL, base_url: str = OPENROUTER_BASE_URL,
                 client: httpx.Client | None = None, timeout: float = 90.0, retries: int = 2,
                 sleep: Callable[[float], None] = time.sleep):
        self.api_key, self.model, self.base_url = api_key, model, base_url.rstrip("/")
        self._client, self.timeout, self.retries, self._sleep = client, timeout, retries, sleep

    def chat(self, messages: list[dict], tools: list[dict]) -> LLMReply:
        return _openai_chat(self.base_url, self.api_key, {"X-Title": "NammaPulse"}, self.model,
                            messages, tools, self._client, self.timeout, self.retries, self._sleep, "OpenRouter")


def from_env() -> BobClient | OpenRouterClient | None:
    """Return the best available LLM client based on environment variables.

    Priority:
    1. BobClient  — when BOB_API_KEY is set (uses your IBM Bob AI credits)
    2. OpenRouterClient — when OPENROUTER_API_KEY is set
    3. None — both absent; callers fall back to deterministic checks
    """
    bob_key = os.environ.get("BOB_API_KEY")
    if bob_key:
        return BobClient(bob_key,
                         model=os.environ.get("BOB_MODEL", DEFAULT_MODEL),
                         base_url=os.environ.get("BOB_BASE_URL", ""))
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
