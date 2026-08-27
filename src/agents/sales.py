"""Sales agent — product discovery and price comparison.

Uses CrewAI to coordinate two tools:
- search_catalog: semantic search over the product catalog
- compare_price: real-time price comparison via browser-use in Fargate
"""

from __future__ import annotations

from typing import Any

from crewai import Agent, Crew, Process, Task


SALES_AGENT = None  # lazy init


def get_sales_agent() -> Agent:
    """Lazy-init the Sales agent to avoid cold-start cost when not needed."""
    global SALES_AGENT
    if SALES_AGENT is None:
        from src.tools.catalog import search_catalog_tool
        from src.tools.price_compare import compare_price_tool

        SALES_AGENT = Agent(
            role="Retail Sales Associate",
            goal=(
                "Help customers find the right product at the right price. "
                "Be specific about availability, sizing, and value. "
                "Use the price comparison tool when customers ask about value or compare prices."
            ),
            backstory=(
                "You are an experienced retail sales associate with deep knowledge of "
                "apparel, electronics, home goods, and beauty products. You help customers "
                "make confident buying decisions. You never oversell or pressure. "
                "If a product is out of stock, you suggest alternatives."
            ),
            tools=[search_catalog_tool(), compare_price_tool()],
            llm="bedrock/anthropic.claude-sonnet-4-5-20250929-v1:0",
            allow_delegation=False,  # Sales doesn't delegate
            verbose=False,
        )
    return SALES_AGENT


SALES_TASK_TEMPLATE = """You are a retail sales associate helping a customer with this request:

Customer: {customer_id}
Request: {transcript}
Context: {context}

Your job:
1. Understand what the customer wants
2. Search the catalog for matching products
3. If they ask about value or compare prices, use the price comparison tool
4. Recommend the best option with a clear reason
5. Be concise — voice responses should be under 30 seconds

If the product is out of stock, suggest 1-2 alternatives.
If the request is unclear, ask one clarifying question.
If the request is about something other than shopping (return, complaint), 
politely redirect: "I'll connect you with our support team."

Respond as if speaking directly to the customer. Be friendly and specific.
"""


def run_sales_agent(customer_id: str | None, transcript: str, context: dict[str, Any]) -> str:
    """Run the Sales agent and return the response text."""
    agent = get_sales_agent()
    task = Task(
        description=SALES_TASK_TEMPLATE.format(
            customer_id=customer_id or "anonymous",
            transcript=transcript,
            context=context or {},
        ),
        expected_output="A concise response to the customer (under 200 words).",
        agent=agent,
    )
    crew = Crew(agents=[agent], tasks=[task], process=Process.sequential, verbose=False)
    result = crew.kickoff()
    return str(result)
