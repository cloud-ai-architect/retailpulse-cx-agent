"""Sales agent: product discovery and value questions."""

from __future__ import annotations

from typing import Any

from src.agent import BaseAgent
from src.tools.catalog import TOOL as CATALOG_TOOL
from src.tools.price_compare import TOOL as PRICE_TOOL


class SalesAgent(BaseAgent):
    NAME = "sales"

    TOOLS = {
        "search_catalog": CATALOG_TOOL,
        "compare_price": PRICE_TOOL,
    }

    SYSTEM_PROMPT = """You are a retail sales associate. You help customers find \
the right product and decide whether it is good value.

Rules you do not break:

- Never name a product, price, or stock status that did not come back from \
search_catalog. If the catalog returns nothing, say you could not find it and \
ask one clarifying question.
- Only quote a competitor price from compare_price, and never when the result \
is marked stale. If it is stale, say you cannot confirm competitor pricing \
right now.
- If something is out of stock, say so plainly and offer one or two \
alternatives from the catalog.
- Do not pressure, upsell, or invent urgency.

Keep replies under about 60 words. These are often read aloud."""

    def handle(self, customer_id: str, transcript: str, context: dict[str, Any]) -> str:
        prompt = (
            f"Customer id: {customer_id}\n"
            f"They said: {transcript}\n"
            f"What we already know: {context}\n\n"
            "Help them."
        )
        return self.converse(prompt)


def run_sales_agent(
    customer_id: str, transcript: str, context: dict[str, Any] | None = None
) -> tuple[str, list[dict[str, Any]]]:
    """Run the sales agent and return its reply plus the tools it used."""
    agent = SalesAgent()
    reply = agent.run(customer_id, transcript, context or {})
    return reply, agent.tool_calls
