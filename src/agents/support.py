"""Support agent: order status and how-things-work questions."""

from __future__ import annotations

from typing import Any

from src.agent import BaseAgent
from src.tools.faq import TOOL as FAQ_TOOL
from src.tools.orders import TOOL as ORDERS_TOOL


class SupportAgent(BaseAgent):
    NAME = "support"

    TOOLS = {
        "lookup_orders": ORDERS_TOOL,
        "search_faq": FAQ_TOOL,
    }

    SYSTEM_PROMPT = """You are a retail customer support agent. You answer \
questions about orders that have already been placed, and about how the \
business operates.

Rules you do not break:

- Never state an order status, date, or amount that did not come back from \
lookup_orders. If you cannot find the order, say so and ask the customer to \
confirm the order number.
- Answer policy and how-to questions from search_faq. If the FAQ does not \
cover it, say you will need to check rather than guessing.
- You cannot issue refunds. If the customer wants one, tell them you are \
handing them to the returns team and stop there.
- If a customer is upset, acknowledge it once, briefly, then deal with the \
problem. Do not repeat apologies.

Keep replies under about 60 words. These are often read aloud."""

    def handle(self, customer_id: str, transcript: str, context: dict[str, Any]) -> str:
        prompt = (
            f"Customer id: {customer_id}\n"
            f"They said: {transcript}\n"
            f"What we already know: {context}\n\n"
            "Help them."
        )
        return self.converse(prompt)


def run_support_agent(
    customer_id: str, transcript: str, context: dict[str, Any] | None = None
) -> tuple[str, list[dict[str, Any]]]:
    """Run the support agent and return its reply plus the tools it used."""
    agent = SupportAgent()
    reply = agent.run(customer_id, transcript, context or {})
    return reply, agent.tool_calls
