"""FAQ tool — RAG over FAQ documents using S3 Vectors."""

from __future__ import annotations

import json
from typing import Any

import boto3
from crewai_tools import tool


def _embed_query(query: str) -> list[float]:
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


@tool("Search FAQ")
def search_faq_tool(query: str, top_k: int = 3) -> str:
    """Search the FAQ for answers to common customer questions.

    Use this when the customer asks how-to questions, about policies, or anything
    that might be in the FAQ. Returns the top-k most relevant FAQ entries.
    """
    try:
        s3vectors = boto3.client("s3vectors", region_name="ap-south-1")
        query_vector = _embed_query(query)
        response = s3vectors.query_vectors(
            vectorBucketName="retailpulse-dev-vectors",
            indexName="retailpulse-chunks-v1",
            queryVector={"float32": query_vector},
            topK=top_k,
            returnMetadata=True,
        )
        results = []
        for v in response.get("vectors", []):
            results.append(v.get("metadata", {}))
        return json.dumps({"query": query, "count": len(results), "results": results})
    except Exception as exc:
        return json.dumps({"error": str(exc), "query": query})


def search_faq_tool_bound():
    return search_faq_tool
