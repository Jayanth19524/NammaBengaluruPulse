import json

import httpx
import pytest
from pydantic import BaseModel

from agentkit import LLMReply, OpenRouterClient, ScriptedLLM, Tool, ToolCall, run_agent
from agentkit.llm import LLMError


class Add(BaseModel):
    a: int
    b: int


class Done(BaseModel):
    answer: int


def tools(log):
    def add(p):
        log.append(("add", p.a, p.b))
        return {"sum": p.a + p.b}

    def done(p):
        if p.answer < 0:
            raise ValueError("answer must be non-negative")
        return p
    return [Tool("add", "add numbers", Add, add), Tool("final_answer", "finish", Done, done, terminal=True)]


def call(name, args, id="1"):
    return ToolCall(id, name, json.dumps(args))


def test_loop_uses_tools_then_finishes_and_passes_results_back():
    log, events = [], []
    llm = ScriptedLLM([LLMReply("thinking", [call("add", {"a": 2, "b": 3})]),
                       LLMReply(None, [call("final_answer", {"answer": 5}, "2")])])
    r = run_agent(llm, "sys", "task", tools(log), emit=lambda k, m, d: events.append(k))
    assert r.ok and r.final.answer == 5 and log == [("add", 2, 3)]
    assert events == ["reasoning", "tool_call", "tool_result", "tool_call", "final"]
    tool_msg = [m for m in llm.calls[1] if m["role"] == "tool"][0]
    assert json.loads(tool_msg["content"]) == {"sum": 5}


def test_invalid_args_and_unknown_tool_are_returned_to_model_not_crashed():
    llm = ScriptedLLM([LLMReply(None, [call("add", {"a": "x"}), call("nope", {}, "2")]),
                       LLMReply(None, [call("final_answer", {"answer": 1}, "3")])])
    r = run_agent(llm, "s", "t", tools([]))
    assert r.ok
    errs = [json.loads(m["content"]) for m in llm.calls[1] if m["role"] == "tool"]
    assert "invalid arguments" in errs[0]["error"] and "unknown tool" in errs[1]["error"]


def test_guardrail_rejection_lets_model_retry():
    llm = ScriptedLLM([LLMReply(None, [call("final_answer", {"answer": -1})]),
                       LLMReply(None, [call("final_answer", {"answer": 4}, "2")])])
    r = run_agent(llm, "s", "t", tools([]))
    assert r.ok and r.final.answer == 4


def test_no_final_answer_fails_cleanly():
    llm = ScriptedLLM([LLMReply("just chatting"), LLMReply("still chatting")])
    r = run_agent(llm, "s", "t", tools([]))
    assert not r.ok and "without calling" in r.error


def test_step_and_tool_budgets():
    forever = [LLMReply(None, [call("add", {"a": 1, "b": 1}, str(i))]) for i in range(10)]
    r = run_agent(ScriptedLLM(forever), "s", "t", tools([]), max_steps=3)
    assert "no conclusion" in r.error
    r2 = run_agent(ScriptedLLM([LLMReply(None, [call("add", {"a": 1, "b": 1}, str(i)) for i in range(5)])]), "s", "t", tools([]), max_tool_calls=2)
    assert "budget" in r2.error


def test_llm_failure_is_reported():
    r = run_agent(ScriptedLLM([]), "s", "t", tools([]))
    assert not r.ok and "script exhausted" in r.error


def or_client(handler, **kw):
    return OpenRouterClient("k", "m/x", client=httpx.Client(transport=httpx.MockTransport(handler)), sleep=lambda s: None, **kw)


def test_openrouter_parses_tool_calls_and_sends_tools():
    seen = {}

    def handler(req):
        seen["body"], seen["auth"] = json.loads(req.content), req.headers["authorization"]
        return httpx.Response(200, json={"choices": [{"message": {"content": None, "tool_calls": [
            {"id": "c1", "type": "function", "function": {"name": "add", "arguments": "{\"a\":1,\"b\":2}"}}]}}]})
    reply = or_client(handler).chat([{"role": "user", "content": "hi"}], [tools([])[0].spec()])
    assert reply.tool_calls[0].name == "add" and json.loads(reply.tool_calls[0].arguments) == {"a": 1, "b": 2}
    assert seen["auth"] == "Bearer k" and seen["body"]["tools"][0]["function"]["name"] == "add" and seen["body"]["temperature"] == 0


def test_openrouter_retries_then_succeeds_and_errors_become_llmerror():
    n = {"i": 0}

    def flaky(req):
        n["i"] += 1
        return httpx.Response(503) if n["i"] == 1 else httpx.Response(200, json={"choices": [{"message": {"content": "ok"}}]})
    assert or_client(flaky).chat([], []).content == "ok" and n["i"] == 2
    with pytest.raises(LLMError):
        or_client(lambda r: httpx.Response(401)).chat([], [])
