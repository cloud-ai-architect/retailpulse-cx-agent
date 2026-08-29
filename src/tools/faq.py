"""FAQ tool: retrieval over the FAQ corpus via S3 Vectors.

The support agent answers policy and how-to questions from this rather than
from the model's own recollection, so that what a customer is told matches
what the business actually publishes.
"""

from __future__ import annotations

import json
import os
from typing import Any

VECTORS_BUCKET = os.environ.get("VECTORS_BUCKET", "")
VECTOR_INDEX = os.environ.get("VECTOR_INDEX", "")
EMBED_MODEL = os.environ.get("EMBED_MODEL_ID", "amazon.titan-embed-text-v2:0")
EMBED_DIMENSIONS = int(os.environ.get("EMBEDDING_DIMENSIONS", "1024"))

SPEC: dict[str, Any] = {
    "name": "search_faq",
    "description": (
        "Search the published FAQ and policy documents. Use this for how-to "
        "questions, shipping and payment questions, and anything a customer "
        "asks about how the business operates. Prefer this over answering from "
        "memory, and quote what it returns rather than paraphrasing loosely."
    ),
    "inputSchema": {
        "json": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "The customer's question."},
                "top_k": {
                    "type": "integer",
                    "description": "How many passages to return. Defaults to 3.",
                },
            },
            "required": ["query"],
        }
    },
}


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


def search_faq(query: str, top_k: int = 3) -> str:
    """Embed the question and return the nearest FAQ passages."""
    if not VECTORS_BUCKET or not VECTOR_INDEX:
        return json.dumps({"error": "FAQ index is not configured", "query": query})

    top_k = max(1, min(int(top_k), 10))

    import boto3

    try:
        vectors = boto3.client("s3vectors")
        response = vectors.query_vectors(
            vectorBucketName=VECTORS_BUCKET,
            indexName=VECTOR_INDEX,
            queryVector={"float32": _embed(query)},
            topK=top_k,
            returnMetadata=True,
            returnDistance=True,
        )
    except Exception as exc:
        return json.dumps({"error": str(exc), "query": query})

    results = []
    for v in response.get("vectors", []):
        metadata = v.get("metadata", {}) or {}
        results.append(
            {
                "text": metadata.get("text", ""),
                "source": metadata.get("source", ""),
                "distance": v.get("distance"),
            }
        )

    return json.dumps({"query": query, "count": len(results), "results": results})


TOOL = (SPEC, search_faq)
