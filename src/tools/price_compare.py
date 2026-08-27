"""Price comparison tool — uses browser-use in Fargate to check competitor prices.

Workflow:
1. Agent calls compare_price(product_name, our_price)
2. Tool starts an ECS Run Task with browser-use container
3. Fargate task launches headless Chromium, navigates Amazon/Walmart/Target
4. Extracts structured price data
5. Returns comparison + recommendation

The Fargate task definition + task are in `infra/terraform/modules/ecs-browser-use/`.
"""

from __future__ import annotations

import json
import time
from typing import Any

import boto3
from crewai_tools import tool


def _start_browser_use_task(product_name: str) -> str:
    """Start an ECS Fargate task that runs browser-use."""
    ecs = boto3.client("ecs", region_name="ap-south-1")
    response = ecs.run_task(
        cluster="retailpulse-dev-browser-use",
        taskDefinition="retailpulse-dev-browser-use:1",
        launchType="FARGATE_SPOT",
        networkConfiguration={
            "awsvpcConfiguration": {
                "subnets": ["subnet-xxx"],  # populated by Terraform output
                "securityGroups": ["sg-xxx"],
                "assignPublicIp": "ENABLED",
            }
        },
        overrides={
            "containerOverrides": [
                {
                    "name": "browser-use",
                    "command": ["python", "-m", "browser_use.compare", product_name],
                }
            ]
        },
    )
    return response["tasks"][0]["taskArn"]


def _wait_for_task(task_arn: str, timeout: int = 60) -> dict[str, Any]:
    """Wait for Fargate task to complete, return result."""
    ecs = boto3.client("ecs", region_name="ap-south-1")
    start = time.time()
    while time.time() - start < timeout:
        response = ecs.describe_tasks(cluster="retailpulse-dev-browser-use", tasks=[task_arn])
        status = response["tasks"][0]["lastStatus"]
        if status in ("STOPPED", "DEAD"):
            # Read result from S3 output bucket
            s3 = boto3.client("s3", region_name="ap-south-1")
            try:
                obj = s3.get_object(
                    Bucket="retailpulse-dev-browser-use-output",
                    Key=f"results/{task_arn.split('/')[-1]}.json",
                )
                return json.loads(obj["Body"].read().decode("utf-8"))
            except Exception:
                return {"error": "Task stopped but no result found"}
        time.sleep(2)
    return {"error": "Task timeout"}


@tool("Compare Price")
def compare_price_tool(product_name: str, our_price: float) -> str:
    """Compare our price for a product against Amazon, Walmart, and Target.

    Use this when the customer asks "is this a good price" or "can I find it
    cheaper elsewhere". Returns a JSON object with competitor prices and
    a recommendation (competitively priced, slightly above market, or below market).
    """
    try:
        task_arn = _start_browser_use_task(product_name)
        result = _wait_for_task(task_arn, timeout=60)
        result["our_price"] = our_price

        # Compute recommendation
        competitor_prices = [
            v for k, v in result.items()
            if k.endswith("_price") and isinstance(v, (int, float))
        ]
        if competitor_prices:
            avg = sum(competitor_prices) / len(competitor_prices)
            if our_price < avg * 0.9:
                result["recommendation"] = "below market — great value"
            elif our_price < avg * 1.05:
                result["recommendation"] = "competitively priced"
            else:
                result["recommendation"] = "above market — consider a discount"
        return json.dumps(result)
    except Exception as exc:
        return json.dumps({"error": str(exc), "product": product_name, "our_price": our_price})


def compare_price_tool_bound():
    return compare_price_tool
