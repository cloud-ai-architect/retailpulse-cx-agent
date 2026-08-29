"""Return-policy tool.

The policy lives in code rather than behind a model call on purpose. Whether
a return falls inside its window is a rule, not a judgement, and a customer
who is told the wrong answer has been given a commitment the business has to
either honour or retract. The agent decides how to say it; this decides what
is true.
"""

from __future__ import annotations

import json
import os
from datetime import UTC, datetime
from typing import Any

ORDERS_TABLE = os.environ.get("ORDERS_TABLE", "")


def _age_in_days(created_at: str) -> int | None:
    """Whole days between an ISO-8601 purchase timestamp and now, or None."""
    if not created_at:
        return None
    try:
        stamp = datetime.fromisoformat(created_at.replace("Z", "+00:00"))
    except ValueError:
        return None
    if stamp.tzinfo is None:
        stamp = stamp.replace(tzinfo=UTC)
    return (datetime.now(UTC) - stamp).days


# Window in days, plus the conditions a customer is entitled to hear stated.
RETURN_POLICY: dict[str, dict[str, Any]] = {
    "standard": {
        "window_days": 30,
        "conditions": [
            "Item must be unused and in original packaging",
            "Receipt or proof of purchase required",
            "Final sale items are not returnable",
        ],
    },
    "electronics": {
        "window_days": 15,
        "conditions": [
            "Item must be in original packaging with all accessories",
            "Defective items: full refund regardless of the window",
            "Changed-mind returns: 15% restocking fee",
        ],
    },
    "apparel": {
        "window_days": 30,
        "conditions": [
            "Tags must be attached",
            "Unworn and unwashed",
            "Original receipt required",
        ],
    },
}

# Substrings that map a free-text category onto a policy. Ordered, because
# "electronics accessories" should match electronics rather than standard.
_CATEGORY_HINTS: tuple[tuple[tuple[str, ...], str], ...] = (
    (("electron", "laptop", "phone", "audio", "camera", "tv"), "electronics"),
    (("apparel", "clothing", "shirt", "pant", "dress", "shoe", "footwear"), "apparel"),
)

SPEC: dict[str, Any] = {
    "name": "check_return_policy",
    "description": (
        "Determine whether an order is still within its return window. Call "
        "this before telling a customer anything about whether they can "
        "return something -- never answer from memory, and never estimate "
        "the age of an order yourself. Takes the order id and works out the "
        "category and the elapsed days from the order record."
    ),
    "inputSchema": {
        "json": {
            "type": "object",
            "properties": {
                "order_id": {
                    "type": "string",
                    "description": "The order the customer wants to return.",
                },
            },
            "required": ["order_id"],
        }
    },
}


def _policy_for(category: str) -> tuple[str, dict[str, Any]]:
    key = (category or "").lower()
    for hints, name in _CATEGORY_HINTS:
        if any(h in key for h in hints):
            return name, RETURN_POLICY[name]
    return "standard", RETURN_POLICY["standard"]


def check_return_policy(order_id: str) -> str:
    """Decide eligibility from the order record, not from what it is told.

    The elapsed days used to be a parameter, supplied by the model from the
    order lookup. It got them wrong: asked about a 66-day-old electronics
    order it passed days_since_purchase=3, and the customer was told an
    ineligible return was eligible.

    A date subtraction is not a judgement call, so the model no longer makes
    it. The tool reads created_at from the order and computes the age
    itself; the model supplies only the order id, which it cannot invent
    because the lookup returned it.
    """
    if not ORDERS_TABLE:
        return json.dumps({"error": "orders table is not configured"})

    import boto3

    try:
        order = (
            boto3.resource("dynamodb")
            .Table(ORDERS_TABLE)
            .get_item(Key={"order_id": order_id})
            .get("Item")
        )
    except Exception as exc:
        return json.dumps({"error": str(exc), "order_id": order_id})

    if not order:
        return json.dumps({"error": "order not found", "order_id": order_id})

    created_at = str(order.get("created_at", ""))
    days = _age_in_days(created_at)
    if days is None:
        return json.dumps(
            {
                "error": "order has no usable purchase date",
                "order_id": order_id,
                "created_at": created_at,
            }
        )

    category = str(order.get("category", "") or "")
    name, policy = _policy_for(category)
    window = int(policy["window_days"])

    return json.dumps(
        {
            "order_id": order_id,
            "category": category,
            "policy": name,
            "purchased_at": created_at,
            "days_since_purchase": days,
            "window_days": window,
            "eligible": days <= window,
            "days_remaining": max(0, window - days),
            "order_total_inr": float(order.get("total_inr", 0)),
            "already_refunded": order.get("status") == "refunded",
            "conditions": policy["conditions"],
        }
    )


TOOL = (SPEC, check_return_policy)
