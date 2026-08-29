"""Orchestrator: route a customer message to the agent that should handle it.

Runs on the cheap model tier. Routing is a short classification, and paying
standard-tier prices for it on every message is the difference between a
system that is affordable at volume and one that is not.
"""

from __future__ import annotations

from typing import Any

from src.agent import MODEL_FAST, BaseAgent, ModelError
from src.lambdas._base import respond, run_stage

INTENTS = ("sales", "support", "returns")


class Orchestrator(BaseAgent):
    NAME = "orchestrator"
    MODEL = MODEL_FAST

    SYSTEM_PROMPT = """You route retail customer messages to one of three teams.

sales    - finding a product, availability, sizing, price, whether something \
is good value.
support  - an order already placed: where it is, when it arrives, what was \
charged. Also how the business works: shipping, payment, accounts.
returns  - returning, refunding, exchanging or cancelling something.

If a message spans two, choose the one the customer most needs resolved. \
Someone who is angry about a late delivery and mentions returning it wants \
support unless they explicitly ask to return it.

Reply with JSON only, no prose:
{"intent": "sales|support|returns", "confidence": 0.0-1.0, "reasoning": "one short sentence"}"""

    def handle(self, transcript: str) -> dict[str, Any]:
        data = self.invoke_json(f"Customer message: {transcript}", max_tokens=200)

        intent = str(data.get("intent", "")).lower().strip()
        if intent not in INTENTS:
            raise ModelError(f"orchestrator returned an unknown intent: {intent!r}")

        try:
            confidence = float(data.get("confidence", 0.0))
        except (TypeError, ValueError):
            confidence = 0.0

        return {
            "intent": intent,
            # A model that reports 1.4 or -0.2 is not telling us anything
            # useful; clamp rather than propagate a nonsense number.
            "confidence": round(min(max(confidence, 0.0), 1.0), 3),
            "reasoning": str(data.get("reasoning", "")),
        }


def _run(data: dict[str, Any]) -> dict[str, Any]:
    decision = Orchestrator().run(data["transcript"])
    decision["context_for_agent"] = {
        "customer_id": data.get("customer_id"),
        "session_id": data.get("session_id"),
        "channel": data.get("channel", "web"),
        **(data.get("context") or {}),
    }
    return decision


def handler(event: dict[str, Any], context: object) -> dict[str, Any]:
    try:
        return run_stage(event, required=["transcript"], fn=_run)
    except ModelError as exc:
        # Routing failed. Rather than guessing, say so: a message sent to the
        # wrong agent produces a confidently wrong answer, which is worse
        # than asking the customer to rephrase.
        return respond(502, {"error": "ROUTING_FAILED", "message": str(exc)})
