"""Orchestrator Lambda — classifies intent and dispatches to the right agent.

Entry point: API Gateway /v1/conversations
Exit point: Step Function with intent = sales | support | returns
"""

from __future__ import annotations

import json
import os
import time

import boto3
from src.common import (
    ConversationRequest,
    DataCuratorModel,
    JobContext,
    OrchestratorDecision,
    BaseLambda,
    IntentError,
    stage,
)


INTENT_CLASSIFICATION_PROMPT = """Classify the following customer message into one of these intents:
- sales: shopping, product search, price comparison, availability
- support: questions, troubleshooting, account help, general inquiries
- returns: return, refund, exchange, cancel order

Customer message: "{transcript}"

Respond with JSON: {{"intent": "sales|support|returns", "confidence": 0.0-1.0, "reasoning": "..."}}
"""


@stage(name="orchestrator", input_model=ConversationRequest, output_model=OrchestratorDecision)
class Orchestrator(BaseLambda):
    def setup(self) -> None:
        # Bedrock client already set up in BaseLambda
        pass

    def handle(self, ctx: JobContext, inp: ConversationRequest) -> OrchestratorDecision:  # type: ignore[override]
        start = time.perf_counter()
        try:
            # Use Bedrock Haiku for cheap, fast intent classification
            response = self.bedrock.invoke_model(
                modelId="anthropic.claude-haiku-4-5-20250929-v1:0",  # if not avail, fallback
                contentType="application/json",
                accept="application/json",
                body=json.dumps({
                    "anthropic_version": "bedrock-2023-05-31",
                    "max_tokens": 200,
                    "messages": [
                        {
                            "role": "user",
                            "content": INTENT_CLASSIFICATION_PROMPT.format(transcript=inp.transcript)
                        }
                    ]
                }),
            )
            result = json.loads(response["body"].read())
            text = result["content"][0]["text"]
            # Parse JSON from text (may have ```json ... ```)
            text = text.strip().strip("`").removeprefix("json").strip()
            data = json.loads(text)

            return OrchestratorDecision(
                intent=data["intent"],
                confidence=float(data.get("confidence", 0.8)),
                reasoning=data.get("reasoning", ""),
                context_for_agent={
                    "customer_id": inp.customer_id,
                    "session_id": inp.session_id,
                    "channel": inp.channel,
                    **(inp.context or {}),
                },
            )
        except Exception as exc:
            self.log.error("orchestrator.classify_failed", error=str(exc))
            # Fallback: default to support
            return OrchestratorDecision(
                intent="support",
                confidence=0.5,
                reasoning=f"classification failed: {exc}; defaulting to support",
                context_for_agent={"customer_id": inp.customer_id, "session_id": inp.session_id, "channel": inp.channel, **(inp.context or {})},
            )


def handler(event: dict, context: object) -> dict:
    """Step Function entry point."""
    from src.common import JobContext
    ctx = JobContext(
        session_id=event.get("session_id", "unknown"),
        customer_id=event.get("customer_id"),
        environment=os.environ.get("ENVIRONMENT", "dev"),
    )
    inp = ConversationRequest.from_dict(event) if isinstance(event, dict) else event
    orch = Orchestrator()
    result = orch.handle(ctx, inp)
    return result.to_dict()
