"""Refund tool — initiate refund and update order status."""

from __future__ import annotations

import json
import time
import uuid
from typing import Any

import boto3
from crewai_tools import tool


@tool("Initiate Refund")
def initiate_refund_tool(order_id: str, amount_inr: float, reason: str = "") -> str:
    """Initiate a refund for an order.

    Use this after confirming a return is eligible. Updates the order status
    to 'refunded' and creates a refund record. In v1, the actual 3PL API
    call is stubbed; in v2 it will call the real 3PL.

    Returns: refund_id, status, estimated_days
    """
    try:
        dynamodb = boto3.client("dynamodb", region_name="ap-south-1")
        refund_id = f"RF-{uuid.uuid4().hex[:12].upper()}"

        # Update order status
        dynamodb.update_item(
            TableName="retailpulse-dev-orders",
            Key={"order_id": {"S": order_id}},
            UpdateExpression="SET #s = :refunded, refund_id = :rid, refund_at = :ts",
            ExpressionAttributeNames={"#s": "status"},
            ExpressionAttributeValues={
                ":refunded": {"S": "refunded"},
                ":rid": {"S": refund_id},
                ":ts": {"S": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())},
            },
        )

        return json.dumps({
            "refund_id": refund_id,
            "order_id": order_id,
            "amount_inr": amount_inr,
            "status": "initiated",
            "estimated_days": 7,
        })
    except Exception as exc:
        return json.dumps({"error": str(exc), "order_id": order_id})


def initiate_refund_tool_bound():
    return initiate_refund_tool
