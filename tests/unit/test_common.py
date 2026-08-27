"""Unit tests for the common base classes."""

from __future__ import annotations

import pytest

from src.common import (
    AgentError,
    AgentResponse,
    BaseLambda,
    CatalogError,
    ConversationRequest,
    DataCuratorModel,
    IntentError,
    JobContext,
    OrchestratorDecision,
    OrderError,
    RetailPulseError,
    ToolCall,
    ToolError,
    VoiceError,
    stage,
)


class TestExceptions:
    def test_inheritance(self):
        assert issubclass(AgentError, RetailPulseError)
        assert issubclass(CatalogError, RetailPulseError)
        assert issubclass(IntentError, RetailPulseError)
        assert issubclass(OrderError, RetailPulseError)
        assert issubclass(ToolError, RetailPulseError)
        assert issubclass(VoiceError, RetailPulseError)


class TestJobContext:
    def test_defaults(self):
        ctx = JobContext(session_id="s1")
        assert ctx.session_id == "s1"
        assert ctx.customer_id is None
        assert ctx.environment == "dev"
        assert ctx.cumulative_cost_usd == 0.0


class TestDataclassBase:
    def test_conversation_request_defaults(self):
        req = ConversationRequest(
            session_id="s1",
            channel="web",
            transcript="hello",
        )
        assert req.session_id == "s1"
        assert req.channel == "web"
        assert req.transcript == "hello"
        assert req.customer_id is None
        assert req.context == {}

    def test_orchestrator_decision(self):
        d = OrchestratorDecision(
            intent="sales",
            confidence=0.92,
            reasoning="clear buy intent",
        )
        assert d.intent == "sales"
        assert d.confidence == 0.92

    def test_tool_call(self):
        tc = ToolCall(tool="search", args={"q": "shirt"}, result={"hits": []}, ok=True)
        assert tc.tool == "search"
        assert tc.ok is True

    def test_agent_response(self):
        r = AgentResponse(
            session_id="s1",
            intent="sales",
            agent="sales",
            response="Here's our Oxford shirt.",
        )
        assert r.tool_calls == []
        assert r.audio_url is None

    def test_from_dict_and_to_dict(self):
        d = {"session_id": "s1", "channel": "web", "transcript": "hi"}
        req = ConversationRequest.from_dict(d)
        assert req.session_id == "s1"
        assert req.transcript == "hi"
        back = req.to_dict()
        assert back["session_id"] == "s1"
        assert back["channel"] == "web"

    def test_from_dict_ignores_unknown_keys(self):
        d = {"session_id": "s1", "channel": "web", "transcript": "hi", "extra_unknown": 42}
        req = ConversationRequest.from_dict(d)
        assert req.session_id == "s1"
        assert not hasattr(req, "extra_unknown") or "extra_unknown" not in req.to_dict()


class TestStageDecorator:
    def test_decorator_sets_class_attrs(self):
        @stage(name="test-stage", output_model=AgentResponse)
        class TestHandler(BaseLambda):
            NAME = ""
            INPUT_MODEL = None
            OUTPUT_MODEL = None

            def handle(self, ctx, inp):
                return AgentResponse(
                    session_id=ctx.session_id,
                    intent="sales",
                    agent="sales",
                    response="ok",
                )

        assert TestHandler.NAME == "test-stage"
        assert TestHandler.OUTPUT_MODEL == AgentResponse
