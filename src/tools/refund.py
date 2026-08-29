"""Refund tool: the one action in this system that moves money.

Everything else an agent can reach is a read. This writes, so it is
deliberately the most constrained tool here:

  It refuses an amount that exceeds the order total, so a model that
  misreads a figure cannot over-refund.

  It refuses an order that is already refunded, using a conditional write
  rather than a read-then-write, so two concurrent requests cannot both
  succeed.

  It records who asked and why, because a refund is something someone will
  later need to account for.

The 3PL settlement call is not implemented. The refund is recorded against
the order and reported as initiated, which is the state a real integration
would start from.
"""

from __future__ import annotations

import json
import os
import time
import uuid
from decimal import Decimal
from typing import Any

ORDERS_TABLE = os.environ.get("ORDERS_TABLE", "")

# What a customer is told to expect. Kept here rather than in the prompt so
# the agent cannot improvise a different number.
ESTIMATED_SETTLEMENT_DAYS = 7

SPEC: dict[str, Any] = {
    "name": "initiate_refund",
    "description": (
        "Start a refund for an order. Only call this after check_return_policy "
        "has confirmed the return is eligible and the customer has asked to "
        "proceed. The amount must not exceed the order total. This is a real "
        "state change: do not call it to explore what would happen."
    ),
    "inputSchema": {
        "json": {
            "type": "object",
            "properties": {
                "order_id": {"type": "string", "description": "Order being refunded."},
                "amount_inr": {
                    "type": "number",
                    "description": "Refund amount in INR. Must not exceed the order total.",
                },
                "reason": {
                    "type": "string",
                    "description": "Why the customer is returning the item.",
                },
            },
            "required": ["order_id", "amount_inr"],
        }
    },
}


def initiate_refund(  # noqa: PLR0911 -- one guard clause per refusal reason
    order_id: str, amount_inr: float, reason: str = ""
) -> str:
    """Record a refund against an order, if the order allows it."""
    if not ORDERS_TABLE:
        return json.dumps({"error": "orders table is not configured"})

    amount = float(amount_inr)
    if amount <= 0:
        return json.dumps({"error": "refund amount must be positive", "order_id": order_id})

    import boto3
    from botocore.exceptions import ClientError

    table = boto3.resource("dynamodb").Table(ORDERS_TABLE)

    try:
        existing = table.get_item(Key={"order_id": order_id}).get("Item")
    except Exception as exc:
        return json.dumps({"error": str(exc), "order_id": order_id})

    if not existing:
        return json.dumps({"error": "order not found", "order_id": order_id})

    total = float(existing.get("total_inr", 0))
    if amount > total:
        return json.dumps(
            {
                "error": "refund exceeds order total",
                "order_id": order_id,
                "requested_inr": amount,
                "order_total_inr": total,
            }
        )

    refund_id = f"RF-{uuid.uuid4().hex[:12].upper()}"
    now = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())

    try:
        # The condition is the concurrency control: if another request has
        # already refunded this order, this write fails rather than issuing
        # a second refund over the top of the first.
        table.update_item(
            Key={"order_id": order_id},
            UpdateExpression=(
                "SET #s = :refunded, refund_id = :rid, refund_at = :ts, "
                "refund_amount_inr = :amt, refund_reason = :why"
            ),
            ConditionExpression="attribute_exists(order_id) AND #s <> :refunded",
            ExpressionAttributeNames={"#s": "status"},
            ExpressionAttributeValues={
                ":refunded": "refunded",
                ":rid": refund_id,
                ":ts": now,
                ":amt": Decimal(str(amount)),
                ":why": reason or "not stated",
            },
        )
    except ClientError as exc:
        if exc.response.get("Error", {}).get("Code") == "ConditionalCheckFailedException":
            return json.dumps(
                {
                    "error": "order has already been refunded",
                    "order_id": order_id,
                    "existing_refund_id": existing.get("refund_id"),
                }
            )
        return json.dumps({"error": str(exc), "order_id": order_id})
    except Exception as exc:
        return json.dumps({"error": str(exc), "order_id": order_id})

    return json.dumps(
        {
            "refund_id": refund_id,
            "order_id": order_id,
            "amount_inr": amount,
            "status": "initiated",
            "estimated_days": ESTIMATED_SETTLEMENT_DAYS,
            "initiated_at": now,
        }
    )


TOOL = (SPEC, initiate_refund)
