"""Order tools — lookup order history for a customer."""

from __future__ import annotations

import json
from typing import Any

import boto3
from crewai_tools import tool


@tool("Lookup Orders")
def lookup_orders_tool(customer_id: str, limit: int = 5) -> str:
    """Look up a customer's recent orders.

    Use this when a customer asks about their order, shipment, or history.
    Returns a JSON list of orders with order_id, items, status, total, and dates.
    """
    try:
        dynamodb = boto3.client("dynamodb", region_name="ap-south-1")
        table = "retailpulse-dev-orders"

        response = dynamodb.query(
            TableName=table,
            KeyConditionExpression="customer_id = :cid",
            ExpressionAttributeValues={":cid": {"S": customer_id}},
            Limit=limit,
            ScanIndexForward=False,  # most recent first
        )
        orders = []
        for item in response.get("Items", []):
            orders.append({
                "order_id": item["order_id"]["S"],
                "status": item.get("status", {}).get("S", "unknown"),
                "total_inr": float(item.get("total_inr", {}).get("N", 0)),
                "created_at": item.get("created_at", {}).get("S", ""),
                "delivered_at": item.get("delivered_at", {}).get("S", ""),
                "items": json.loads(item.get("items", {}).get("S", "[]")),
            })
        return json.dumps({"customer_id": customer_id, "count": len(orders), "orders": orders})
    except Exception as exc:
        return json.dumps({"error": str(exc), "customer_id": customer_id})


def lookup_orders_tool_bound():
    return lookup_orders_tool
