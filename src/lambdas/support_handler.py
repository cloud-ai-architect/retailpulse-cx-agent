"""Support agent Lambda."""

from __future__ import annotations

import os

from src.agents.support import run_support_agent
from src.common import (
    AgentResponse,
    BaseLambda,
    JobContext,
    OrchestratorDecision,
    ToolCall,
    stage,
)


@stage(name="support-agent", input_model=OrchestratorDecision, output_model=AgentResponse)
class SupportAgentLambda(BaseLambda):
    def setup(self) -> None:
        pass

    def handle(self, ctx: JobContext, inp: OrchestratorDecision) -> AgentResponse:  # type: ignore[override]
        import time
        start = time.perf_counter()
        try:
            customer_id = inp.context_for_agent.get("customer_id")
            transcript = inp.context_for_agent.get("transcript", "")
            response_text = run_support_agent(customer_id, transcript, inp.context_for_agent)
            return AgentResponse(
                session_id=ctx.session_id,
                intent="support",
                agent="support",
                response=response_text,
                tool_calls=[],
                duration_ms=int((time.perf_counter() - start) * 1000),
            )
        except Exception as exc:
            return AgentResponse(
                session_id=ctx.session_id,
                intent="support",
                agent="support",
                response="I'm having trouble right now. Could you try again?",
                tool_calls=[ToolCall(tool="agent", args={}, ok=False, error=str(exc))],
            )


def handler(event: dict, context: object) -> dict:
    from src.common import JobContext
    ctx = JobContext(session_id=event.get("session_id", "unknown"), environment=os.environ.get("ENVIRONMENT", "dev"))
    inp = OrchestratorDecision.from_dict(event) if isinstance(event, dict) else event
    fn = SupportAgentLambda()
    return fn.handle(ctx, inp).to_dict()
