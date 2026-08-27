"""Policy tool — check return policy for a given order/product."""

from __future__ import annotations

import json
from typing import Any

from crewai_tools import tool


# Static policy for v1; in v2, this loads from S3 / catalog
RETURN_POLICY = {
    "standard": {
        "window_days": 30,
        "conditions": [
            "Item must be unused and in original packaging",
            "Receipt or proof of purchase required",
            "Final sale items not returnable",
        ],
    },
    "electronics": {
        "window_days": 15,
        "conditions": [
            "Item must be in original packaging with all accessories",
            "Defective items: full refund regardless of window",
            "Changed-mind returns: 15% restocking fee",
        ],
    },
    "apparel": {
        "window_days": 30,
        "conditions": [
            "Tags must be attached",
            "Unworn, unwashed condition",
            "Original receipt required",
        ],
    },
}


@tool("Check Return Policy")
def check_return_policy_tool(category: str, days_since_purchase: int) -> str:
    """Check if a return is eligible under our policy.

    Use this when a customer asks about returning an item. The agent should
    have the category from the order lookup. Returns a JSON object with
    the policy details and eligibility.
    """
    policy_key = category.lower() if category else "standard"
    if "electron" in policy_key:
        policy = RETURN_POLICY["electronics"]
    elif "apparel" in policy_key or "shirt" in policy_key or "pant" in policy_key:
        policy = RETURN_POLICY["apparel"]
    else:
        policy = RETURN_POLICY["standard"]

    window = policy["window_days"]
    eligible = days_since_purchase <= window

    return json.dumps({
        "category": category,
        "days_since_purchase": days_since_purchase,
        "window_days": window,
        "eligible": eligible,
        "conditions": policy["conditions"],
    })


def check_return_policy_tool_bound():
    return check_return_policy_tool
