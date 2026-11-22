"""The agent loop: the model chooses tools, sees results, and ends by calling a terminal tool.

Guardrails: arguments are validated against pydantic schemas; tool errors go back to the model so it can
correct itself; there is a step and tool-call budget; the final answer is a schema-checked tool call.
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any, Callable

from pydantic import BaseModel, ValidationError

from .llm import LLMClient, LLMError

Emit = Callable[[str, str, dict], None]
MAX_RESULT_CHARS = 6000


@dataclass
class Tool:
    name: str
    description: str
    params: type[BaseModel]
    fn: Callable[[Any], Any]
    terminal: bool = False  # calling it ends the run; fn may raise ValueError to reject the answer

    def spec(self) -> dict:
        schema = self.params.model_json_schema()
        schema.pop("title", None)
        return {"type": "function", "function": {"name": self.name, "description": self.description, "parameters": schema}}


@dataclass
class AgentResult:
    final: Any = None
    error: str | None = None
    steps: int = 0
    tool_calls: list[dict] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return self.error is None


def _noop(kind: str, message: str, data: dict) -> None:
    pass


def run_agent(llm: LLMClient, system: str, task: str, tools: list[Tool], max_steps: int = 12,
              max_tool_calls: int = 24, emit: Emit = _noop) -> AgentResult:
    by_name = {t.name: t for t in tools}
    specs = [t.spec() for t in tools]
    messages: list[dict] = [{"role": "system", "content": system}, {"role": "user", "content": task}]
    result, nudged, calls = AgentResult(), False, 0
    for step in range(1, max_steps + 1):
        result.steps = step
        try:
            reply = llm.chat(messages, specs)
        except LLMError as exc:
            result.error = str(exc)
            emit("error", f"Model unavailable: {exc}", {})
            return result
        messages.append(reply.as_message())
        if reply.content and reply.content.strip():
            emit("reasoning", reply.content.strip(), {"model": getattr(llm, "model", "")})
        if not reply.tool_calls:
            if nudged:
                result.error = "model stopped without calling the final-answer tool"
                emit("error", result.error, {})
                return result
            nudged = True
            messages.append({"role": "user", "content": "Use your tools, then finish by calling the final-answer tool."})
            continue
        for tc in reply.tool_calls:
            calls += 1
            if calls > max_tool_calls:
                result.error = f"tool-call budget of {max_tool_calls} exceeded"
                emit("error", result.error, {})
                return result
            out, done = _call(by_name, tc.name, tc.arguments, emit, result)
            messages.append({"role": "tool", "tool_call_id": tc.id, "content": out[:MAX_RESULT_CHARS]})
            if done is not None:
                result.final = done
                return result
    result.error = f"no conclusion within {max_steps} steps"
    emit("error", result.error, {})
    return result


def _call(by_name: dict[str, Tool], name: str, raw: str, emit: Emit, result: AgentResult):
    """Returns (text for the model, final value or None)."""
    tool = by_name.get(name)
    if tool is None:
        emit("tool_error", f"Model asked for unknown tool '{name}'", {"tool": name})
        return json.dumps({"error": f"unknown tool '{name}'. Available: {sorted(by_name)}"}), None
    try:
        args = tool.params.model_validate(json.loads(raw or "{}"))
    except (ValueError, ValidationError) as exc:
        emit("tool_error", f"Invalid arguments for {name}: {exc}", {"tool": name})
        return json.dumps({"error": f"invalid arguments: {str(exc)[:500]}"}), None
    emit("tool_call", f"Calling {name}", {"tool": name, "args": args.model_dump(mode="json")})
    result.tool_calls.append({"tool": name, "args": args.model_dump(mode="json")})
    try:
        value = tool.fn(args)
    except ValueError as exc:  # guardrail rejection: tell the model why
        emit("tool_error", f"{name} rejected: {exc}", {"tool": name})
        return json.dumps({"error": str(exc)}), None
    except Exception as exc:  # a failing tool must not crash the run
        emit("tool_error", f"{name} failed: {exc}", {"tool": name})
        return json.dumps({"error": f"tool failed: {exc}"}), None
    if tool.terminal:
        emit("final", f"Agent concluded via {name}", {"tool": name})
        return json.dumps({"ok": True}), value if value is not None else True
    text = json.dumps(value, default=str)
    emit("tool_result", f"{name} returned", {"tool": name, "preview": text[:300]})
    return text, None
