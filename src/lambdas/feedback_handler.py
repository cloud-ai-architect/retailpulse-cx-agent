"""Feedback Lambda: record how a conversation actually went.

Every agent reply is a guess about what the customer needed. Without this
there is no signal at all about which guesses were right, and no basis for
changing a prompt other than intuition.
"""

from __future__ import annotations

import os
import time
import uuid
from typing import Any

from src.lambdas._base import parse_event, respond, run_stage

FEEDBACK_TABLE = os.environ.get("FEEDBACK_TABLE", "")

MIN_RATING = 1
MAX_RATING = 5


def _validate_rating(raw: Any) -> tuple[int | None, str | None]:
    """Return (rating, error). Checked before run_stage, not inside it.

    run_stage maps any exception from its callable to a 5xx, which is the
    right default for an unexpected failure but wrong for a bad rating: that
    is the caller's mistake and has to come back as a 400. So validation
    happens here, where the status code can still be chosen.
    """
    try:
        rating = int(raw)
    except (TypeError, ValueError):
        return None, "rating must be a whole number"
    if not MIN_RATING <= rating <= MAX_RATING:
        return None, f"rating must be between {MIN_RATING} and {MAX_RATING}"
    return rating, None


def _run(data: dict[str, Any]) -> dict[str, Any]:
    if not FEEDBACK_TABLE:
        raise RuntimeError("feedback table is not configured")

    rating = int(data["rating"])

    import boto3

    feedback_id = f"FB-{uuid.uuid4().hex[:12].upper()}"
    created_at = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())

    item = {
        "feedback_id": feedback_id,
        "session_id": str(data["session_id"]),
        "created_at": created_at,
        "agent": str(data.get("agent", "unknown")),
        "rating": rating,
        "resolved": bool(data.get("resolved", True)),
        "comments": str(data.get("comments", ""))[:2000],
    }

    boto3.resource("dynamodb").Table(FEEDBACK_TABLE).put_item(Item=item)
    return {"feedback_id": feedback_id, "session_id": item["session_id"], "status": "recorded"}


def handler(event: dict[str, Any], context: object) -> dict[str, Any]:
    data = parse_event(event)

    missing = [k for k in ("session_id", "rating") if not data.get(k)]
    if missing:
        return respond(
            400,
            {
                "error": "MISSING_PARAMETERS",
                "message": "required: {}".format(", ".join(missing)),
            },
        )

    _, error = _validate_rating(data["rating"])
    if error:
        return respond(400, {"error": "INVALID_RATING", "message": error})

    return run_stage(event, required=["session_id", "rating"], fn=_run)
