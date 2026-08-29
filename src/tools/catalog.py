"""Catalog tool: semantic search over the product catalog.

The catalog is small enough to hold in memory for the life of a warm Lambda,
so search runs locally over cached embeddings rather than through a vector
store. At a few thousand products that is faster than a network round trip
and costs nothing to keep.

If the catalog outgrows that, the swap is to S3 Vectors: the tool contract
below does not change.
"""

from __future__ import annotations

import json
import math
import os
from functools import lru_cache
from typing import Any

CATALOG_BUCKET = os.environ.get("CATALOG_BUCKET", "")
CATALOG_KEY = os.environ.get("CATALOG_KEY", "catalog/master.json")
EMBED_MODEL = os.environ.get("EMBED_MODEL_ID", "amazon.titan-embed-text-v2:0")
EMBED_DIMENSIONS = int(os.environ.get("EMBEDDING_DIMENSIONS", "1024"))

SPEC: dict[str, Any] = {
    "name": "search_catalog",
    "description": (
        "Search the product catalog for items matching a customer's description. "
        "Returns name, price in INR, category, sizes and stock status. Use this "
        "before recommending anything, so that recommendations are real products "
        "at real prices."
    ),
    "inputSchema": {
        "json": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "What the customer is looking for, in their own words.",
                },
                "top_k": {
                    "type": "integer",
                    "description": "How many products to return. Defaults to 5.",
                },
            },
            "required": ["query"],
        }
    },
}


@lru_cache(maxsize=1)
def _load_catalog() -> tuple[dict[str, Any], ...]:
    """Load the catalog once per warm Lambda.

    Returns a tuple so the lru_cache entry cannot be mutated by a caller and
    silently corrupt every later request on the same container.
    """
    if not CATALOG_BUCKET:
        return ()
    import boto3

    s3 = boto3.client("s3")
    try:
        obj = s3.get_object(Bucket=CATALOG_BUCKET, Key=CATALOG_KEY)
        products = json.loads(obj["Body"].read().decode("utf-8"))
    except Exception:
        # An unreachable catalog is reported to the model as an empty result,
        # not raised: the agent can still answer policy or order questions.
        return ()
    return tuple(products) if isinstance(products, list) else ()


def _embed(text: str) -> list[float]:
    import boto3

    bedrock = boto3.client("bedrock-runtime")
    response = bedrock.invoke_model(
        modelId=EMBED_MODEL,
        contentType="application/json",
        accept="application/json",
        body=json.dumps({"inputText": text, "dimensions": EMBED_DIMENSIONS}),
    )
    embedding: list[float] = json.loads(response["body"].read())["embedding"]
    return embedding


def _cosine(a: list[float], b: list[float]) -> float:
    if not a or not b or len(a) != len(b):
        return 0.0
    dot = sum(x * y for x, y in zip(a, b, strict=True))
    na = math.sqrt(sum(x * x for x in a))
    nb = math.sqrt(sum(y * y for y in b))
    if na == 0.0 or nb == 0.0:
        return 0.0
    return dot / (na * nb)


# Words this short ("a", "of", "to") match everything and rank nothing.
_MIN_TERM_LENGTH = 2


def _keyword_score(query: str, product: dict[str, Any]) -> float:
    """Fallback ranking when a product carries no stored embedding.

    Deliberately crude -- overlapping words over query length. It exists so
    that a catalog which has not been through the embedding pipeline still
    returns something sensible instead of nothing.
    """
    terms = {t for t in query.lower().split() if len(t) > _MIN_TERM_LENGTH}
    if not terms:
        return 0.0
    haystack = " ".join(
        str(product.get(f, "")) for f in ("name", "description", "category", "brand")
    ).lower()
    return sum(1 for t in terms if t in haystack) / len(terms)


def search_catalog(query: str, top_k: int = 5) -> str:
    """Rank the catalog against a query and return the best matches."""
    products = _load_catalog()
    if not products:
        return json.dumps(
            {"query": query, "count": 0, "results": [], "note": "catalog unavailable"}
        )

    top_k = max(1, min(int(top_k), 20))

    embedded = [p for p in products if p.get("embedding")]
    if embedded:
        try:
            q = _embed(query)
            scored = [(_cosine(q, p["embedding"]), p) for p in embedded]
        except Exception:
            scored = [(_keyword_score(query, p), p) for p in products]
    else:
        scored = [(_keyword_score(query, p), p) for p in products]

    scored.sort(key=lambda pair: pair[0], reverse=True)

    results = []
    for score, p in scored[:top_k]:
        if score <= 0.0:
            continue
        results.append(
            {
                "sku": p.get("sku"),
                "name": p.get("name"),
                "category": p.get("category"),
                "price_inr": p.get("price_inr"),
                "sizes": p.get("sizes"),
                "in_stock": p.get("in_stock", True),
                "score": round(float(score), 4),
            }
        )

    return json.dumps({"query": query, "count": len(results), "results": results})


TOOL = (SPEC, search_catalog)
