# Low-Level Design (LLD)

## Purpose

This document drills into the **internal structure** of each component — data shapes, function signatures, state transitions, and inter-stage contracts. It is the most detailed level of design and is read alongside the source code.

## Data shapes (the contracts between stages)

### Voice gateway → Orchestrator

```json
{
  "session_id": "uuid",
  "customer_id": "uuid-or-anonymous",
  "channel": "voice",
  "audio_url": "s3://.../audio.wav",
  "transcript": "I'd like to return my order #12345",
  "language": "en-IN",
  "timestamp": "2026-08-27T12:00:00Z"
}
```

### Orchestrator → Agent

```json
{
  "session_id": "uuid",
  "intent": "returns",   // "sales" | "support" | "returns"
  "transcript": "...",
  "context": {
    "customer_id": "uuid",
    "recent_orders": [...]
  }
}
```

### Agent → Tool

```json
{
  "tool": "compare_price",   // or "lookup_order", "search_catalog", "initiate_refund"
  "args": {
    "product_name": "Oxford shirt blue size M"
  }
}
```

### Tool → Agent

```json
{
  "ok": true,
  "data": {
    "our_price": 2499,
    "amazon_price": 2599,
    "walmart_price": 2499,
    "target_price": null,
    "recommendation": "competitively priced"
  }
}
```

### Catalog

```json
{
  "sku": "SHIRT-001",
  "name": "Oxford Shirt Blue M",
  "category": "apparel/men/shirts",
  "brand": "Northwood",
  "price_inr": 2499,
  "stock": 42,
  "sizes": ["S","M","L","XL"],
  "description": "..."
}
```

### Order

```json
{
  "order_id": "ORD-000123",
  "customer_id": "CUST-0042",
  "items": [{"sku": "SHIRT-001", "qty": 2, "price": 2499}],
  "total_inr": 4998,
  "status": "delivered",
  "created_at": "2026-08-15T10:30:00Z",
  "delivered_at": "2026-08-17T14:20:00Z"
}
```

### Feedback

```json
{
  "feedback_id": "uuid",
  "session_id": "uuid",
  "agent": "returns",
  "rating": 5,
  "comments": "Quick and easy",
  "resolved": true
}
```

## CrewAI agent definitions (pseudocode)

```python
# src/agents/sales.py
from crewai import Agent
from src.tools.catalog import CatalogSearch
from src.tools.price_compare import PriceCompare

sales_agent = Agent(
    role="Retail Sales Associate",
    goal="Help customers find the right product at the right price",
    backstory="You are a knowledgeable retail sales associate...",
    tools=[CatalogSearch(), PriceCompare()],
    llm="bedrock/anthropic.claude-sonnet-4-5-20250929-v1:0",
    allow_delegation=False,  # Sales doesn't delegate
)

# src/agents/support.py
support_agent = Agent(
    role="Customer Support Specialist",
    goal="Resolve customer questions and issues",
    backstory="You are an empathetic customer support specialist...",
    tools=[OrderLookup(), FAQSearch()],
    llm="bedrock/anthropic.claude-sonnet-4-5-20250929-v1:0",
    allow_delegation=True,  # Support can delegate to Returns for return issues
)

# src/agents/returns.py
returns_agent = Agent(
    role="Returns Processing Specialist",
    goal="Process returns and refunds efficiently",
    backstory="You are a returns specialist...",
    tools=[OrderLookup(), RefundTool()],
    llm="bedrock/anthropic.claude-sonnet-4-5-20250929-v1:0",
    allow_delegation=False,
)
```

## Orchestrator task

```python
# src/lambdas/orchestrator.py
def handler(event, context):
    """Dispatch to Sales/Support/Returns based on intent."""
    intent = classify_intent(event["transcript"])  # Bedrock call
    
    task_config = {
        "sales":   {"agent": sales_agent,   "tools": [...]},
        "support": {"agent": support_agent, "tools": [...]},
        "returns": {"agent": returns_agent, "tools": [...]},
    }[intent]
    
    response = task_config["agent"].execute(
        task=event["transcript"],
        context=event.get("context", {})
    )
    return response
```

## Tool implementation pattern

```python
# src/tools/catalog.py
from strands_aws.tools import S3GetObject
from crewai_tools import tool

@tool("Search Catalog")
def search_catalog(query: str, max_results: int = 5) -> list[dict]:
    """Search the product catalog for items matching the query."""
    # Load catalog from S3 (cached in Lambda)
    catalog = load_catalog()  # S3 GetObject
    
    # Use embedding similarity (via Titan v2)
    query_embedding = embed(query)
    results = semantic_search(catalog, query_embedding, top_k=max_results)
    
    return [r.to_dict() for r in results]
```

## Step Function state machine

```json
{
  "StartAt": "Transcribe",
  "States": {
    "Transcribe": {
      "Type": "Task",
      "Resource": "arn:aws:states:::lambda:invoke",
      "Parameters": {"FunctionName": "...transcribe..."},
      "Next": "Classify"
    },
    "Classify": {
      "Type": "Task",
      "Resource": "arn:aws:states:::lambda:invoke",
      "Parameters": {"FunctionName": "...orchestrator..."},
      "Next": "Dispatch"
    },
    "Dispatch": {
      "Type": "Choice",
      "Choices": [
        {"Variable": "$.intent", "StringEquals": "sales",   "Next": "SalesAgent"},
        {"Variable": "$.intent", "StringEquals": "support", "Next": "SupportAgent"},
        {"Variable": "$.intent", "StringEquals": "returns", "Next": "ReturnsAgent"}
      ]
    },
    "SalesAgent":   {"Type": "Task", "Resource": "...sales...",   "Next": "Synthesize"},
    "SupportAgent": {"Type": "Task", "Resource": "...support...", "Next": "Synthesize"},
    "ReturnsAgent": {"Type": "Task", "Resource": "...returns...", "Next": "Synthesize"},
    "Synthesize": {
      "Type": "Task",
      "Resource": "arn:aws:states:::lambda:invoke",
      "Parameters": {"FunctionName": "...polly..."},
      "Next": "Done"
    },
    "Done": {"Type": "Succeed"}
  }
}
```

## Failure isolation

- **Transcribe fails** → fall back to text channel
- **Orchestrator fails** → retry 3×, then return "I didn't understand"
- **Agent fails** → retry 2× with different prompt, then escalate to human
- **Tool fails** → return error to agent, agent can try alternate tool
- **Polly fails** → return text only

## See also

- [HLD](01-hld.md) — service boundaries, deployment topology
- [Component diagram](03-component-diagram.md) — module dependencies
- [Data flow](04-data-flow.md) — sequence diagrams
- [API reference](../api/rest-api.md) — external HTTP API
- [Data model](../data-model.md) — entity relationships
