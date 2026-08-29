"""Support agent Lambda: order status and how-things-work questions."""

from __future__ import annotations

from typing import Any

from src.agent import ModelError
from src.agents.support import run_support_agent
from src.lambdas._base import respond, run_stage


def _run(data: dict[str, Any]) -> dict[str, Any]:
    context = data.get("context_for_agent") or data.get("context") or {}
    reply, tool_calls = run_support_agent(
        customer_id=str(data["customer_id"]),
        transcript=str(data["transcript"]),
        context=context,
    )
    return {"agent": "support", "response": reply, "tool_calls": tool_calls}


def handler(event: dict[str, Any], context: object) -> dict[str, Any]:
    try:
        return run_stage(event, required=["customer_id", "transcript"], fn=_run)
    except ModelError as exc:
        return respond(502, {"error": "AGENT_FAILED", "message": str(exc)})
