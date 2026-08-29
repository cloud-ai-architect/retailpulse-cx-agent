"""Tests for the HTTP envelope and the handlers.

These cover the parts every request passes through: how a request body is
found regardless of how the Lambda was invoked, how missing inputs are
reported, and how a failure is mapped to a status code. A bug here affects
every endpoint at once.
"""

from __future__ import annotations

import json
from typing import Any

import pytest
from src.common import RetailPulseError
from src.lambdas import _base


class TestParseEvent:
    def test_api_gateway_json_string_body(self) -> None:
        assert _base.parse_event({"body": '{"query": "shoes"}'}) == {"query": "shoes"}

    def test_direct_dict_body(self) -> None:
        assert _base.parse_event({"body": {"query": "shoes"}}) == {"query": "shoes"}

    def test_query_string_parameters(self) -> None:
        event = {"queryStringParameters": {"query": "shoes"}}
        assert _base.parse_event(event) == {"query": "shoes"}

    def test_step_function_passes_the_payload_directly(self) -> None:
        assert _base.parse_event({"query": "shoes"}) == {"query": "shoes"}

    def test_malformed_json_body_is_empty_not_an_exception(self) -> None:
        # A truncated body should produce a 400 from the missing-parameter
        # check, not a 500 from a JSONDecodeError.
        assert _base.parse_event({"body": "{not json"}) == {}

    def test_non_dict_event(self) -> None:
        assert _base.parse_event("nonsense") == {}
        assert _base.parse_event(None) == {}


class TestRunStage:
    def test_missing_parameters_are_named_in_a_400(self) -> None:
        response = _base.run_stage({}, required=["customer_id", "transcript"], fn=dict)
        assert response["statusCode"] == 400
        body = json.loads(response["body"])
        assert body["error"] == "MISSING_PARAMETERS"
        assert "customer_id" in body["message"]
        assert "transcript" in body["message"]

    def test_success_wraps_the_result(self) -> None:
        response = _base.run_stage({"a": 1}, required=["a"], fn=lambda d: {"got": d["a"]})
        assert response["statusCode"] == 200
        assert json.loads(response["body"]) == {"result": {"got": 1}}

    def test_domain_error_is_a_502(self) -> None:
        def boom(_data: dict[str, Any]) -> Any:
            raise RetailPulseError("model unavailable")

        response = _base.run_stage({"a": 1}, required=["a"], fn=boom)
        assert response["statusCode"] == 502

    def test_unexpected_error_is_a_500(self) -> None:
        def boom(_data: dict[str, Any]) -> Any:
            raise RuntimeError("something else")

        response = _base.run_stage({"a": 1}, required=["a"], fn=boom)
        assert response["statusCode"] == 500
        assert json.loads(response["body"])["error"] == "INTERNAL_ERROR"

    def test_response_is_json_content_type(self) -> None:
        response = _base.respond(200, {"ok": True})
        assert response["headers"]["Content-Type"] == "application/json"


class TestOrchestrator:
    """The router decides which agent answers; a wrong answer here is a
    confidently wrong reply from the wrong specialist."""

    @staticmethod
    def _orchestrator(reply: dict[str, Any]) -> Any:
        from src.lambdas.orchestrator_handler import Orchestrator

        agent = Orchestrator()
        agent._setup_done = True
        agent.invoke_json = lambda *_a, **_k: reply  # type: ignore[method-assign]
        return agent

    def test_valid_intent_passes_through(self) -> None:
        agent = self._orchestrator({"intent": "returns", "confidence": 0.9, "reasoning": "r"})
        assert agent.handle("I want to send this back")["intent"] == "returns"

    def test_unknown_intent_is_rejected(self) -> None:
        from src.agent import ModelError

        agent = self._orchestrator({"intent": "billing", "confidence": 0.9})
        with pytest.raises(ModelError, match="unknown intent"):
            agent.handle("hello")

    def test_confidence_is_clamped(self) -> None:
        # A model reporting 1.4 is not telling us anything useful; a value
        # outside [0, 1] must not reach a caller that treats it as one.
        assert (
            self._orchestrator({"intent": "sales", "confidence": 1.4}).handle("x")["confidence"]
            == 1.0
        )
        assert (
            self._orchestrator({"intent": "sales", "confidence": -3}).handle("x")["confidence"]
            == 0.0
        )

    def test_non_numeric_confidence_becomes_zero(self) -> None:
        agent = self._orchestrator({"intent": "sales", "confidence": "high"})
        assert agent.handle("x")["confidence"] == 0.0

    def test_intent_is_case_insensitive(self) -> None:
        agent = self._orchestrator({"intent": "  SALES ", "confidence": 0.5})
        assert agent.handle("x")["intent"] == "sales"


class TestFeedbackValidation:
    @pytest.mark.parametrize("rating", [0, 6, -1, 99])
    def test_out_of_range_rating_is_a_400(
        self, rating: int, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        from src.lambdas import feedback_handler

        monkeypatch.setattr(feedback_handler, "FEEDBACK_TABLE", "feedback")
        response = feedback_handler.handler({"session_id": "s-1", "rating": rating}, context=None)
        # rating 0 is falsy, so it is caught as missing rather than invalid;
        # either way the caller gets a 400 and nothing is written.
        assert response["statusCode"] == 400

    def test_non_numeric_rating_is_a_400(self, monkeypatch: pytest.MonkeyPatch) -> None:
        from src.lambdas import feedback_handler

        monkeypatch.setattr(feedback_handler, "FEEDBACK_TABLE", "feedback")
        response = feedback_handler.handler({"session_id": "s-1", "rating": "five"}, context=None)
        assert response["statusCode"] == 400
