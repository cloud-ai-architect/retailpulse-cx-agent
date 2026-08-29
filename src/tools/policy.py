"""Return-policy tool.

The policy lives in code rather than behind a model call on purpose. Whether
a return falls inside its window is a rule, not a judgement, and a customer
who is told the wrong answer has been given a commitment the business has to
either honour or retract. The agent decides how to say it; this decides what
is true.
"""

from __future__ import annotations

import json
from typing import Any

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
        "Determine whether an item is still within its return window. Call this "
        "before telling a customer anything about whether they can return "
        "something -- never answer from memory. Needs the product category and "
        "how many days ago it was purchased, both of which come from the order "
        "lookup."
    ),
    "inputSchema": {
        "json": {
            "type": "object",
            "properties": {
                "category": {
                    "type": "string",
                    "description": "Product category, e.g. electronics, apparel.",
                },
                "days_since_purchase": {
                    "type": "integer",
                    "description": "Whole days between the purchase and today.",
                },
            },
            "required": ["category", "days_since_purchase"],
        }
    },
}


def _policy_for(category: str) -> tuple[str, dict[str, Any]]:
    key = (category or "").lower()
    for hints, name in _CATEGORY_HINTS:
        if any(h in key for h in hints):
            return name, RETURN_POLICY[name]
    return "standard", RETURN_POLICY["standard"]


def check_return_policy(category: str, days_since_purchase: int) -> str:
    """Decide eligibility and return the policy that produced the decision."""
    name, policy = _policy_for(category)
    days = int(days_since_purchase)
    window = int(policy["window_days"])

    # A negative age means the caller has the dates the wrong way round.
    # Saying so is more useful than silently returning "eligible".
    if days < 0:
        return json.dumps(
            {
                "error": "days_since_purchase cannot be negative",
                "category": category,
                "days_since_purchase": days,
            }
        )

    return json.dumps(
        {
            "category": category,
            "policy": name,
            "days_since_purchase": days,
            "window_days": window,
            "eligible": days <= window,
            "days_remaining": max(0, window - days),
            "conditions": policy["conditions"],
        }
    )


TOOL = (SPEC, check_return_policy)
