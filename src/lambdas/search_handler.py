"""Search Lambda — semantic search over the catalog/FAQ KB."""

from __future__ import annotations

import json
import os

import boto3
from src.common import (
    BaseLambda,
    DataCuratorModel,
    JobContext,
    stage,
)


@dataclass_like_search_request := None  # avoid forward ref issues; see real class below


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


from dataclasses import dataclass, field
from typing import Any


@dataclass
class SearchRequest(DataCuratorModel):
    query: str
    top_k: int = 10
    source_filter: str | None = None  # "catalog" | "faq" | "policy"
    format_filter: str | None = None  # "pdf" | "json" | "md"


@dataclass
class SearchHit(DataCuratorModel):
    chunk_id: str
    score: float
    text_preview: str
    source: str
    format: str
    category: str | None = None
    tags: list[str] = field(default_factory=list)


@dataclass
class SearchResponse(DataCuratorModel):
    query: str
    results: list[SearchHit] = field(default_factory=list)
    total_results: int = 0
    query_duration_ms: int = 0


@stage(name="search", input_model=SearchRequest, output_model=SearchResponse)
class SearchLambda(BaseLambda):
    def setup(self) -> None:
        pass

    def handle(self, ctx: JobContext, inp: SearchRequest) -> SearchResponse:  # type: ignore[override]
        import time
        start = time.perf_counter()
        try:
            query_vector = _embed_query(inp.query)
            s3vectors = boto3.client("s3vectors", region_name="ap-south-1")
            response = s3vectors.query_vectors(
                vectorBucketName="retailpulse-dev-vectors",
                indexName="retailpulse-chunks-v1",
                queryVector={"float32": query_vector},
                topK=inp.top_k,
                returnMetadata=True,
            )
            results = []
            for v in response.get("vectors", []):
                meta = v.get("metadata", {})
                hit = SearchHit(
                    chunk_id=v["key"],
                    score=round(1.0 - v.get("distance", 0.0), 4),
                    text_preview=meta.get("text_preview", "")[:200],
                    source=meta.get("source", "unknown"),
                    format=meta.get("format", "unknown"),
                    category=meta.get("category"),
                )
                results.append(hit)
            return SearchResponse(
                query=inp.query,
                results=results,
                total_results=len(results),
                query_duration_ms=int((time.perf_counter() - start) * 1000),
            )
        except Exception as exc:
            return SearchResponse(query=inp.query, results=[], total_results=0, query_duration_ms=0)


def handler(event: dict, context: object) -> dict:
    from src.common import JobContext
    ctx = JobContext(session_id=event.get("session_id", "unknown"), environment=os.environ.get("ENVIRONMENT", "dev"))
    inp = SearchRequest.from_dict(event) if isinstance(event, dict) else event
    fn = SearchLambda()
    return fn.handle(ctx, inp).to_dict()
