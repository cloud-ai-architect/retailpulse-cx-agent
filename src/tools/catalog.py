"""Catalog tool — semantic search over the product catalog.

Reads the catalog from S3, embeds the query with Titan v2,
and does a similarity search via S3 Vectors.
"""

from __future__ import annotations

import json
from functools import lru_cache
from typing import Any

from crewai_tools import tool


@lru_cache(maxsize=1)
def _load_catalog() -> list[dict[str, Any]]:
    """Load the catalog from S3 (cached for the Lambda's lifetime)."""
    import boto3
    s3 = boto3.client("s3", region_name="ap-south-1")
    bucket = "retailpulse-dev-catalog"
    key = "master.json"
    try:
        obj = s3.get_object(Bucket=bucket, Key=key)
        return json.loads(obj["Body"].read().decode("utf-8"))
    except Exception:
        return []


def _embed_query(query: str) -> list[float]:
    """Embed a query with Bedrock Titan v2."""
    import boto3
    bedrock = boto3.client("bedrock-runtime", region_name="ap-south-1")
    response = bedrock.invoke_model(
        modelId="amazon.titan-embed-text-v2:0",
        contentType="application/json",
        accept="application/json",
        body=json.dumps({
            "inputText": query,
            "dimensions": 1024,
            "normalize": True,
        }),
    )
    return json.loads(response["body"].read())["embedding"]


def _cosine_similarity(a: list[float], b: list[float]) -> float:
    """Cosine similarity between two vectors."""
    dot = sum(x * y for x, y in zip(a, b))
    na = sum(x * x for x in a) ** 0.5
    nb = sum(x * x for x in b) ** 0.5
    if na == 0 or nb == 0:
        return 0.0
    return dot / (na * nb)


@tool("Search Catalog")
def search_catalog_tool(query: str, max_results: int = 5) -> str:
    """Search the product catalog for items matching the query.

    Use this when the customer asks about products, categories, or availability.
    Returns a JSON list of matching products with SKU, name, price, and stock.
    """
    catalog = _load_catalog()
    if not catalog:
        return json.dumps({"error": "Catalog unavailable", "results": []})

    # For now, do a simple text-match since we don't have product embeddings yet
    # In Phase 2, replace with semantic search using Titan v2 + S3 Vectors
    q = query.lower()
    matches = []
    for item in catalog:
        text = f"{item.get('name', '')} {item.get('description', '')} {item.get('category', '')} {item.get('brand', '')}".lower()
        if any(word in text for word in q.split() if len(word) > 2):
            matches.append(item)
    matches = matches[:max_results]
    return json.dumps({"query": query, "count": len(matches), "results": matches})


# Eager-loaded agent-bound tool for CrewAI
def search_catalog_tool_bound():
    return search_catalog_tool
