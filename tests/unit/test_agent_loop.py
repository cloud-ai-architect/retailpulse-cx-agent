"""Tests for the Converse tool-use loop.

The loop is the part of this system most likely to fail in a way nobody
notices: a tool result fed back in the wrong shape does not raise, it just
makes the model answer worse. These tests pin the wire format and the
termination behaviour against a fake Bedrock client, so the assertions are
about our code rather than about a model's mood.
"""

from __future__ import annotations

import copy
import json
from typing import Any

import pytest
from src.agent import MAX_TOOL_TURNS, BaseAgent, ModelError


class FakeBedrock:
    """Returns a scripted sequence of Converse responses and records calls."""

    def __init__(self, responses: list[dict[str, Any]]) -> None:
        self._responses = list(responses)
        self.calls: list[dict[str, Any]] = []

    def converse(self, **kwargs: Any) -> dict[str, Any]:
        # Deep-copied on the way in. The loop appends to the same messages
        # list across turns, so storing the reference would make every
        # recorded call show the final state rather than what was sent at
        # the time. boto3 serialises immediately, so production is unaffected.
        self.calls.append(copy.deepcopy(kwargs))
        if not self._responses:
            raise AssertionError("the agent made more model calls than the test scripted")
        return self._responses.pop(0)


def text_reply(text: str) -> dict[str, Any]:
    return {
        "output": {"message": {"role": "assistant", "content": [{"text": text}]}},
        "stopReason": "end_turn",
        "usage": {"inputTokens": 1, "outputTokens": 1},
    }


def tool_reply(name: str, args: dict[str, Any], use_id: str = "tu-1") -> dict[str, Any]:
    return {
        "output": {
            "message": {
                "role": "assistant",
                "content": [{"toolUse": {"toolUseId": use_id, "name": name, "input": args}}],
            }
        },
        "stopReason": "tool_use",
        "usage": {"inputTokens": 1, "outputTokens": 1},
    }


def build(agent_cls: type[BaseAgent], responses: list[dict[str, Any]]) -> BaseAgent:
    agent = agent_cls()
    agent.bedrock = FakeBedrock(responses)
    agent._setup_done = True  # bypass the boto3 client build
    return agent


ECHO_SPEC = {
    "name": "echo",
    "description": "echo",
    "inputSchema": {"json": {"type": "object", "properties": {}}},
}


class EchoAgent(BaseAgent):
    NAME = "echo-agent"
    SYSTEM_PROMPT = "system"
    TOOLS = {"echo": (ECHO_SPEC, lambda **kw: json.dumps({"echoed": kw}))}


class ExplodingAgent(BaseAgent):
    NAME = "exploding-agent"

    @staticmethod
    def _boom(**_kw: Any) -> str:
        raise RuntimeError("tool exploded")

    TOOLS = {"echo": (ECHO_SPEC, _boom)}


class TestPlainReply:
    def test_returns_text_without_calling_tools(self) -> None:
        agent = build(EchoAgent, [text_reply("hello")])
        assert agent.converse("hi") == "hello"
        assert agent.tool_calls == []

    def test_sends_system_prompt_and_tool_config(self) -> None:
        agent = build(EchoAgent, [text_reply("hello")])
        agent.converse("hi")
        sent = agent.bedrock.calls[0]
        assert sent["system"] == [{"text": "system"}]
        assert sent["toolConfig"] == {"tools": [{"toolSpec": ECHO_SPEC}]}

    def test_agent_without_tools_sends_no_tool_config(self) -> None:
        class Bare(BaseAgent):
            NAME = "bare"

        agent = build(Bare, [text_reply("hello")])
        agent.converse("hi")
        assert "toolConfig" not in agent.bedrock.calls[0]


class TestToolUse:
    def test_runs_the_tool_and_feeds_the_result_back(self) -> None:
        agent = build(
            EchoAgent,
            [tool_reply("echo", {"value": 42}), text_reply("done")],
        )
        assert agent.converse("hi") == "done"

        # The result must go back as a user turn carrying a toolResult block
        # whose toolUseId matches the request. Anything else and the model
        # silently loses the connection between question and answer.
        second_call_messages = agent.bedrock.calls[1]["messages"]
        result_block = second_call_messages[-1]["content"][0]["toolResult"]
        assert second_call_messages[-1]["role"] == "user"
        assert result_block["toolUseId"] == "tu-1"
        assert json.loads(result_block["content"][0]["text"]) == {"echoed": {"value": 42}}

    def test_records_the_call_for_the_response_payload(self) -> None:
        agent = build(EchoAgent, [tool_reply("echo", {"value": 1}), text_reply("done")])
        agent.converse("hi")
        assert agent.tool_calls == [
            {"tool": "echo", "args": {"value": 1}, "ok": True, "error": None}
        ]

    def test_tool_failure_is_reported_to_the_model_not_raised(self) -> None:
        agent = build(ExplodingAgent, [tool_reply("echo", {}), text_reply("sorry")])
        assert agent.converse("hi") == "sorry"

        sent_back = agent.bedrock.calls[1]["messages"][-1]["content"][0]["toolResult"]
        assert "tool exploded" in sent_back["content"][0]["text"]
        assert agent.tool_calls[0]["ok"] is False

    def test_unknown_tool_is_reported_rather_than_raising(self) -> None:
        agent = build(EchoAgent, [tool_reply("nope", {}), text_reply("sorry")])
        agent.converse("hi")
        sent_back = agent.bedrock.calls[1]["messages"][-1]["content"][0]["toolResult"]
        assert "unknown tool" in sent_back["content"][0]["text"]

    def test_tool_calls_reset_between_conversations(self) -> None:
        agent = build(
            EchoAgent,
            [tool_reply("echo", {}), text_reply("one"), text_reply("two")],
        )
        agent.converse("first")
        assert len(agent.tool_calls) == 1
        agent.converse("second")
        assert agent.tool_calls == []


class TestTermination:
    def test_tools_are_withheld_on_the_final_turn(self) -> None:
        # Every response asks for a tool. The last call must go out without a
        # toolConfig, so the model is forced to answer from what it has.
        agent = build(EchoAgent, [tool_reply("echo", {})] * MAX_TOOL_TURNS)
        with pytest.raises(ModelError, match="did not converge"):
            agent.converse("hi")
        assert "toolConfig" not in agent.bedrock.calls[-1]
        assert len(agent.bedrock.calls) == MAX_TOOL_TURNS

    def test_reply_with_no_text_is_an_error(self) -> None:
        empty = {
            "output": {"message": {"role": "assistant", "content": []}},
            "stopReason": "end_turn",
        }
        agent = build(EchoAgent, [empty])
        with pytest.raises(ModelError, match="no text"):
            agent.converse("hi")


class TestInvokeJson:
    def test_extracts_json_from_surrounding_prose(self) -> None:
        agent = build(EchoAgent, [text_reply('Sure!\n```json\n{"intent": "sales"}\n```')])
        assert agent.invoke_json("hi") == {"intent": "sales"}

    def test_reply_without_json_raises(self) -> None:
        agent = build(EchoAgent, [text_reply("no json here")])
        with pytest.raises(ModelError, match="no JSON object"):
            agent.invoke_json("hi")

    def test_malformed_json_raises(self) -> None:
        agent = build(EchoAgent, [text_reply('{"intent": }')])
        with pytest.raises(ModelError, match="malformed JSON"):
            agent.invoke_json("hi")


class TestConstruction:
    def test_agent_without_a_name_is_rejected(self) -> None:
        class Nameless(BaseAgent):
            pass

        with pytest.raises(ValueError, match="must set NAME"):
            Nameless()
