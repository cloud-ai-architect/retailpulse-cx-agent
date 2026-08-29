"""Search Lambda: direct catalog and FAQ search, with no model in the path.

The agents reach these same tools through the model when a conversation needs
them. This endpoint exists for the cases that do not need a conversation at
all -- a search box, a "did you mean" list, a health check that proves the
catalog and vector index are actually reachable.

No model call means no per-request model cost and no latency beyond the
lookup itself.
"""

from __future__ import annotations

from typing import Any

from src.lambdas._base import run_stage
from src.tools.catalog import search_catalog
from src.tools.faq import search_faq

VALID_SOURCES = ("catalog", "faq", "both")


def _run(data: dict[str, Any]) -> dict[str, Any]:
    query = str(data["query"])
    source = str(data.get("source", "catalog")).lower()
    if source not in VALID_SOURCES:
        source = "catalog"

    try:
        top_k = int(data.get("top_k", 5))
    except (TypeError, ValueError):
        top_k = 5

    import json

    result: dict[str, Any] = {"query": query, "source": source}
    if source in ("catalog", "both"):
        result["catalog"] = json.loads(search_catalog(query, top_k))
    if source in ("faq", "both"):
        result["faq"] = json.loads(search_faq(query, top_k))
    return result


def handler(event: dict[str, Any], context: object) -> dict[str, Any]:
    return run_stage(event, required=["query"], fn=_run)
