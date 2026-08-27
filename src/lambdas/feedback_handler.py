"""Feedback handler — records user ratings for the conversation."""

from __future__ import annotations

import json
import os
import time
import uuid
from dataclasses import dataclass, field
from typing import Any

import boto3
from src.common import (
    BaseLambda,
    DataCuratorModel,
    JobContext,
    stage,
)


@dataclass
class FeedbackRequest(DataCuratorModel):
    session_id: str
    agent: str
    rating: int  # 1-5
    comments: str = ""
    resolved: bool = True


@dataclass
class FeedbackResponse(DataCuratorModel):
    feedback_id: str
    session_id: str
    status: str = "recorded"


@stage(name="feedback", input_model=FeedbackRequest, output_model=FeedbackResponse)
class FeedbackLambda(BaseLambda):
    def setup(self) -> None:
        pass

    def handle(self, ctx: JobContext, inp: FeedbackRequest) -> FeedbackResponse:  # type: ignore[override]
        try:
            dynamodb = boto3.client("dynamodb", region_name="ap-south-1")
            feedback_id = f"FB-{uuid.uuid4().hex[:12].upper()}"
            dynamodb.put_item(
                TableName="retailpulse-dev-feedback",
                Item={
                    "feedback_id": {"S": feedback_id},
                    "session_id": {"S": inp.session_id},
                    "agent": {"S": inp.agent},
                    "rating": {"N": str(inp.rating)},
                    "comments": {"S": inp.comments},
                    "resolved": {"BOOL": inp.resolved},
                    "created_at": {"S": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())},
                },
            )
            return FeedbackResponse(feedback_id=feedback_id, session_id=inp.session_id)
        except Exception as exc:
            return FeedbackResponse(
                feedback_id="",
                session_id=inp.session_id,
                status=f"error: {exc}",
            )


def handler(event: dict, context: object) -> dict:
    from src.common import JobContext
    ctx = JobContext(session_id=event.get("session_id", "unknown"), environment=os.environ.get("ENVIRONMENT", "dev"))
    inp = FeedbackRequest.from_dict(event) if isinstance(event, dict) else event
    fn = FeedbackLambda()
    return fn.handle(ctx, inp).to_dict()
