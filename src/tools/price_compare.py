"""Price comparison against a stored competitor feed.

The original design launched a Fargate task per query that drove a headless
browser against Amazon, Walmart and Target. That was dropped, for three
reasons rather than one:

  Cost and latency. It needed its own VPC, image and endpoints -- the same
  roughly $21/month standing charge the CodeForge sandbox carries -- and put
  a 30-60 second browser session inside a request a customer is waiting on.

  Reliability. Scraped selectors break without warning, and the failure mode
  is a confidently wrong price quoted to a customer.

  Terms of use. Automated scraping of retail sites generally breaches them.
  A production retailer buys a competitor price feed; it does not scrape.

So this reads a feed instead: a JSON object in S3, refreshed out of band,
keyed by SKU. The tool contract is unchanged -- swapping the feed for a
commercial pricing API is a change to _load_feed and nothing else.

Because a stale price is worse than no price, entries carry the date they
were captured and anything past MAX_FEED_AGE_DAYS is reported as stale
rather than quoted.
"""

from __future__ import annotations

import json
import os
import time
from functools import lru_cache
from typing import Any

CATALOG_BUCKET = os.environ.get("CATALOG_BUCKET", "")
FEED_KEY = os.environ.get("COMPETITOR_FEED_KEY", "pricing/competitors.json")
MAX_FEED_AGE_DAYS = int(os.environ.get("COMPETITOR_FEED_MAX_AGE_DAYS", "7"))

SPEC: dict[str, Any] = {
    "name": "compare_price",
    "description": (
        "Compare our price for a product against competitor prices from the "
        "pricing feed. Use this when a customer asks whether something is good "
        "value, or how our price compares. Only quote a competitor price if the "
        "result is not marked stale."
    ),
    "inputSchema": {
        "json": {
            "type": "object",
            "properties": {
                "sku": {
                    "type": "string",
                    "description": "SKU from the catalog search result.",
                },
                "our_price_inr": {
                    "type": "number",
                    "description": "Our price for the product, in INR.",
                },
            },
            "required": ["sku", "our_price_inr"],
        }
    },
}


@lru_cache(maxsize=1)
def _load_feed() -> dict[str, Any]:
    if not CATALOG_BUCKET:
        return {}
    import boto3

    s3 = boto3.client("s3")
    try:
        obj = s3.get_object(Bucket=CATALOG_BUCKET, Key=FEED_KEY)
        feed = json.loads(obj["Body"].read().decode("utf-8"))
    except Exception:
        return {}
    return feed if isinstance(feed, dict) else {}


def _age_days(captured_at: str) -> float | None:
    """Age of a feed entry in days, or None if the timestamp is unusable."""
    try:
        captured = time.strptime(captured_at[:10], "%Y-%m-%d")
    except (ValueError, TypeError):
        return None
    return (time.time() - time.mktime(captured)) / 86400.0


def compare_price(sku: str, our_price_inr: float) -> str:
    """Return competitor prices for a SKU alongside our own."""
    feed = _load_feed()
    entry = feed.get(sku)
    our_price = float(our_price_inr)

    if not entry:
        return json.dumps(
            {
                "sku": sku,
                "our_price_inr": our_price,
                "comparisons": [],
                "note": "no competitor pricing on file for this SKU",
            }
        )

    age = _age_days(str(entry.get("captured_at", "")))
    stale = age is None or age > MAX_FEED_AGE_DAYS

    comparisons = []
    for retailer, price in (entry.get("prices") or {}).items():
        try:
            competitor_price = float(price)
        except (TypeError, ValueError):
            continue
        comparisons.append(
            {
                "retailer": retailer,
                "price_inr": competitor_price,
                "difference_inr": round(our_price - competitor_price, 2),
                "we_are_cheaper": our_price < competitor_price,
            }
        )

    comparisons.sort(key=lambda c: c["price_inr"])

    result: dict[str, Any] = {
        "sku": sku,
        "our_price_inr": our_price,
        "captured_at": entry.get("captured_at"),
        "stale": stale,
        "comparisons": comparisons,
    }
    if stale:
        result["note"] = (
            f"pricing data is older than {MAX_FEED_AGE_DAYS} days; "
            "do not quote these figures to the customer"
        )
    elif comparisons:
        cheapest = comparisons[0]
        result["summary"] = (
            "we are the cheapest"
            if our_price <= cheapest["price_inr"]
            else f"{cheapest['retailer']} is cheaper by "
            f"{round(our_price - cheapest['price_inr'], 2)} INR"
        )

    return json.dumps(result)


TOOL = (SPEC, compare_price)
