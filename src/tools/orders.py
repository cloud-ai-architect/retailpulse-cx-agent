"""Order tools: read a customer's order history.

Read-only. Nothing here changes an order -- that is the refund tool's job,
and keeping the two apart means an agent that only needs to look something up
cannot accidentally be given the ability to move money.
"""

from __future__ import annotations

import json
import os
from decimal import Decimal
from typing import Any

ORDERS_TABLE = os.environ.get("ORDERS_TABLE", "")
ORDERS_CUSTOMER_INDEX = os.environ.get("ORDERS_CUSTOMER_INDEX", "customer-index")

SPEC: dict[str, Any] = {
    "name": "lookup_orders",
    "description": (
        "Look up a customer's recent orders, most recent first. Use this whenever "
        "a customer refers to an order, a delivery, or something they bought, "
        "before answering from assumption. Returns order_id, status, total in INR, "
        "the items, and the order and delivery dates."
    ),
    "inputSchema": {
        "json": {
            "type": "object",
            "properties": {
                "customer_id": {
                    "type": "string",
                    "description": "The customer whose orders to read.",
                },
                "limit": {
                    "type": "integer",
                    "description": "How many recent orders to return. Defaults to 5.",
                },
            },
            "required": ["customer_id"],
        }
    },
}


def _plain(value: Any) -> Any:
    """DynamoDB returns Decimal; json.dumps does not know what to do with it."""
    if isinstance(value, Decimal):
        return int(value) if value == value.to_integral_value() else float(value)
    if isinstance(value, list):
        return [_plain(v) for v in value]
    if isinstance(value, dict):
        return {k: _plain(v) for k, v in value.items()}
    return value


def lookup_orders(customer_id: str, limit: int = 5) -> str:
    """Query the orders table for one customer."""
    if not ORDERS_TABLE:
        return json.dumps({"error": "orders table is not configured"})

    limit = max(1, min(int(limit), 25))

    import boto3

    table = boto3.resource("dynamodb").Table(ORDERS_TABLE)
    try:
        from boto3.dynamodb.conditions import Key

        # The table is keyed on order_id, so a customer's history is only
        # reachable through the customer-index GSI (customer_id / created_at).
        # Querying the base table by customer_id raises ValidationException.
        response = table.query(
            IndexName=ORDERS_CUSTOMER_INDEX,
            KeyConditionExpression=Key("customer_id").eq(customer_id),
            Limit=limit,
            ScanIndexForward=False,  # created_at descending: newest first
        )
    except Exception as exc:
        return json.dumps({"error": str(exc), "customer_id": customer_id})

    orders = []
    for item in response.get("Items", []):
        raw_items = item.get("items", [])
        # Tolerate both a native list and a JSON string, since the seed data
        # and the application write it differently.
        if isinstance(raw_items, str):
            try:
                raw_items = json.loads(raw_items)
            except json.JSONDecodeError:
                raw_items = []
        orders.append(
            {
                "order_id": item.get("order_id"),
                "status": item.get("status", "unknown"),
                "total_inr": _plain(item.get("total_inr", 0)),
                "created_at": item.get("created_at", ""),
                "delivered_at": item.get("delivered_at", ""),
                "category": item.get("category", ""),
                "items": _plain(raw_items),
            }
        )

    return json.dumps({"customer_id": customer_id, "count": len(orders), "orders": _plain(orders)})


TOOL = (SPEC, lookup_orders)
