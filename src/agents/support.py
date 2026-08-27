"""Support agent — customer questions, troubleshooting, FAQs.

Uses CrewAI to coordinate:
- lookup_order: fetch customer's order history
- search_faq: RAG over FAQ + policy docs
- handoff_to_returns: delegate to Returns agent if issue is a return
"""

from __future__ import annotations

from typing import Any

from crewai import Agent, Crew, Process, Task


SUPPORT_AGENT = None


def get_support_agent() -> Agent:
    global SUPPORT_AGENT
    if SUPPORT_AGENT is None:
        from src.tools.orders import lookup_orders_tool
        from src.tools.faq import search_faq_tool

        SUPPORT_AGENT = Agent(
            role="Customer Support Specialist",
            goal=(
                "Resolve customer questions and issues with empathy and efficiency. "
                "Look up order details when needed. Search the FAQ for common answers. "
                "Hand off to Returns agent for return/refund issues."
            ),
            backstory=(
                "You are a patient, empathetic customer support specialist. You listen "
                "carefully, acknowledge the customer's frustration, and provide clear "
                "solutions. You never make promises you can't keep. If a customer asks "
                "for a return or refund, you delegate to the Returns specialist."
            ),
            tools=[lookup_orders_tool(), search_faq_tool()],
            llm="bedrock/anthropic.claude-sonnet-4-5-20250929-v1:0",
            allow_delegation=True,  # Support can delegate to Returns
            verbose=False,
        )
    return SUPPORT_AGENT


SUPPORT_TASK_TEMPLATE = """You are a customer support specialist helping a customer with this request:

Customer: {customer_id}
Request: {transcript}
Context: {context}

Your job:
1. Understand the customer's issue
2. Look up their orders if relevant
3. Search the FAQ for common answers
4. If this is a return/refund request, hand off to the Returns agent
5. Otherwise, provide a clear, helpful answer

If you need to delegate to Returns, do so cleanly with full context.
Be concise — voice responses under 30 seconds.
"""


def run_support_agent(customer_id: str | None, transcript: str, context: dict[str, Any]) -> str:
    agent = get_support_agent()
    task = Task(
        description=SUPPORT_TASK_TEMPLATE.format(
            customer_id=customer_id or "anonymous",
            transcript=transcript,
            context=context or {},
        ),
        expected_output="A concise, helpful response to the customer (under 200 words).",
        agent=agent,
    )
    crew = Crew(agents=[agent], tasks=[task], process=Process.sequential, verbose=False)
    result = crew.kickoff()
    return str(result)
