"""Returns agent — process returns and refunds.

Uses CrewAI to coordinate:
- lookup_order: verify the order
- check_policy: RAG over return policies
- initiate_refund: call 3PL API (out of scope for v1)
"""

from __future__ import annotations

from typing import Any

from crewai import Agent, Crew, Process, Task


RETURNS_AGENT = None


def get_returns_agent() -> Agent:
    global RETURNS_AGENT
    if RETURNS_AGENT is None:
        from src.tools.orders import lookup_orders_tool
        from src.tools.policy import check_return_policy_tool
        from src.tools.refund import initiate_refund_tool

        RETURNS_AGENT = Agent(
            role="Returns Processing Specialist",
            goal=(
                "Process returns and refunds efficiently and fairly. "
                "Verify the order, check the return policy, and initiate refunds when eligible."
            ),
            backstory=(
                "You are a fair, efficient returns specialist. You verify orders, check "
                "return policies, and process refunds. You follow company policy but "
                "exercise judgment when a customer has a compelling reason. You explain "
                "the policy clearly so customers understand the outcome."
            ),
            tools=[lookup_orders_tool(), check_return_policy_tool(), initiate_refund_tool()],
            llm="bedrock/anthropic.claude-sonnet-4-5-20250929-v1:0",
            allow_delegation=False,  # Returns is terminal
            verbose=False,
        )
    return RETURNS_AGENT


RETURNS_TASK_TEMPLATE = """You are a returns specialist helping a customer with this request:

Customer: {customer_id}
Request: {transcript}
Context: {context}

Your job:
1. Identify which order they want to return
2. Verify the order exists and is eligible for return
3. Check the return policy for that order
4. If eligible, initiate the refund
5. Explain the outcome clearly

If the order is outside the return window, politely explain.
If there's a defect, exercise judgment per the policy.
If eligible, process the refund and confirm.
Be concise — voice responses under 30 seconds.
"""


def run_returns_agent(customer_id: str | None, transcript: str, context: dict[str, Any]) -> str:
    agent = get_returns_agent()
    task = Task(
        description=RETURNS_TASK_TEMPLATE.format(
            customer_id=customer_id or "anonymous",
            transcript=transcript,
            context=context or {},
        ),
        expected_output="A clear explanation of the return outcome (under 200 words).",
        agent=agent,
    )
    crew = Crew(agents=[agent], tasks=[task], process=Process.sequential, verbose=False)
    result = crew.kickoff()
    return str(result)
