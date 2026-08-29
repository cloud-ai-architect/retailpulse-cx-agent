"""Returns agent: eligibility, and the refund itself.

This is the only agent with a tool that changes state, so its prompt is the
strictest of the three. The order of operations below is not a style
preference -- it is what stops a refund being issued on an order that was
never eligible, or twice on one that was.
"""

from __future__ import annotations

from typing import Any

from src.agent import BaseAgent
from src.tools.orders import TOOL as ORDERS_TOOL
from src.tools.policy import TOOL as POLICY_TOOL
from src.tools.refund import TOOL as REFUND_TOOL


class ReturnsAgent(BaseAgent):
    NAME = "returns"

    TOOLS = {
        "lookup_orders": ORDERS_TOOL,
        "check_return_policy": POLICY_TOOL,
        "initiate_refund": REFUND_TOOL,
    }

    SYSTEM_PROMPT = """You handle returns and refunds for a retailer.

Work in this order, every time:

1. lookup_orders to find the order and its category, total and date.
2. check_return_policy with that category and the days since purchase.
3. Tell the customer the outcome and the relevant conditions.
4. Only if the return is eligible AND the customer has asked to go ahead, \
call initiate_refund.

Rules you do not break:

- Never call initiate_refund before check_return_policy has returned \
eligible. If it returns ineligible, explain why and stop.
- Never refund more than the order total.
- If initiate_refund reports the order was already refunded, tell the \
customer that and give them the existing refund id. Do not try again.
- Never promise a timeline other than the estimated_days the tool returns.
- Do not offer goodwill refunds, discounts or exceptions. You do not have \
the authority; say a human will follow up.

Keep replies under about 70 words. These are often read aloud."""

    def handle(self, customer_id: str, transcript: str, context: dict[str, Any]) -> str:
        prompt = (
            f"Customer id: {customer_id}\n"
            f"They said: {transcript}\n"
            f"What we already know: {context}\n\n"
            "Handle their return."
        )
        return self.converse(prompt)


def run_returns_agent(
    customer_id: str, transcript: str, context: dict[str, Any] | None = None
) -> tuple[str, list[dict[str, Any]]]:
    """Run the returns agent and return its reply plus the tools it used."""
    agent = ReturnsAgent()
    reply = agent.run(customer_id, transcript, context or {})
    return reply, agent.tool_calls
