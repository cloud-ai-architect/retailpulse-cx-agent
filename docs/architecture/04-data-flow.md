# Data Flow

## Purpose

This document shows the **end-to-end data movement** through RetailPulse — from customer voice/text input to agent response, with every transformation in between. It complements the [HLD](01-hld.md) and [LLD](02-lld.md) by showing **how data changes** as it flows through the system.

## Voice conversation end-to-end

```mermaid
sequenceDiagram
    actor Customer
    participant VC as Voice Client
    participant T as Transcribe Lambda
    participant GW as API Gateway
    participant SF as Step Function
    participant O as Orchestrator Lambda
    participant A as Agent Lambda (CrewAI)
    participant Tools as Tool Lambdas
    participant CAT as Catalog S3
    participant ORD as Orders DynamoDB
    participant FGT as Fargate browser-use
    participant Pol as Polly Lambda
    participant FB as Feedback DDB

    Customer->>VC: "I want to return my order #12345"
    VC->>T: POST audio (multipart)
    T->>T: Transcribe.startTranscriptionJob
    T-->>VC: transcript="I want to return my order #12345"
    VC->>GW: POST /v1/conversations
    GW->>SF: StartExecution(input={transcript, customer_id})
    SF->>O: Transcribe(state.Transcript)
    O->>O: Bedrock classify_intent(transcript)
    O-->>SF: intent="returns", context={customer_id}
    SF->>A: ReturnsAgent(transcript, context)
    A->>Tools: lookup_order(order_id="12345")
    Tools->>ORD: Query
    ORD-->>Tools: order
    Tools-->>A: order details
    A->>Tools: check_return_policy(order)
    Tools->>CAT: Get policy doc
    CAT-->>Tools: policy
    Tools-->>A: eligible=true
    A->>Tools: initiate_refund(order_id)
    Tools->>ORD: Update order status=refunded
    ORD-->>Tools: ok
    Tools-->>A: refund_id
    A-->>SF: response_text="Your refund has been processed..."
    SF->>Pol: Synthesize(text)
    Pol-->>SF: audio_url
    SF-->>GW: success
    GW-->>VC: {transcript, response_text, audio_url}
    VC->>FB: rate(rating=5)
    FB-->>VC: ok
    VC-->>Customer: audio plays "Your refund..."
```

## Sales flow (with price compare)

```mermaid
sequenceDiagram
    actor Customer
    participant Web as Web Client
    participant GW as API Gateway
    participant SF as Step Function
    participant SA as Sales Lambda
    participant CT as Catalog Tool
    participant CAT as Catalog S3
    participant PC as Price Compare Tool
    participant FGT as Fargate browser-use
    participant S1 as Amazon
    participant S2 as Walmart
    participant S3 as Target

    Customer->>Web: "is this shirt a good price?"
    Web->>GW: POST /v1/conversations
    GW->>SF: StartExecution
    SF->>SA: SalesAgent(transcript)
    SA->>CT: search_catalog("shirt")
    CT->>CAT: Load catalog
    CAT-->>CT: products
    CT-->>SA: top 3 shirts
    SA->>PC: compare_price(product_name="Oxford shirt blue M")
    PC->>FGT: ECS Run Task
    FGT->>S1: GET /s?k=oxford+shirt+blue+m
    S1-->>FGT: HTML
    FGT->>S2: GET /browse/...
    S2-->>FGT: HTML
    FGT->>S3: GET /s?...
    S3-->>FGT: HTML
    FGT->>FGT: extract prices
    FGT-->>PC: {amazon: 2599, walmart: 2499, target: null}
    PC-->>SA: comparison
    SA-->>SF: response="This Oxford shirt is competitively priced..."
    SF-->>GW: success
    GW-->>Web: {response_text, sources}
```

## Returns flow (with refund)

```mermaid
sequenceDiagram
    actor Customer
    participant SF as Step Function
    participant RA as Returns Agent
    participant OT as Order Tool
    participant ORD as Orders DynamoDB
    participant PT as Policy Tool
    participant RT as Refund Tool
    participant Ship as 3PL API
    participant FB as Feedback DDB

    Customer->>SF: "I want to return my order"
    SF->>RA: ReturnsAgent(intent=returns)
    RA->>OT: lookup_recent_orders(customer_id)
    OT->>ORD: Query
    ORD-->>OT: 3 orders
    OT-->>RA: orders
    RA-->>Customer: "Which order would you like to return?"
    Customer->>SF: "Order #12345"
    SF->>RA: ReturnsAgent(order_id=12345)
    RA->>PT: check_policy(order_id)
    PT->>PT: RAG over policies/
    PT-->>RA: eligible=true, refund_amount=4998
    RA-->>Customer: "You're eligible for a full refund. Confirm?"
    Customer->>SF: "Yes"
    SF->>RA: ReturnsAgent(confirm=true)
    RA->>RT: initiate_refund(order_id, amount)
    RT->>Ship: POST /api/refunds
    Ship-->>RT: refund_id
    RT->>ORD: Update status=refunded
    RT-->>RA: ok
    RA-->>SF: "Refund processed, you should see it in 5-7 business days"
    RA->>FB: save_interaction(...)
    SF-->>Customer: success
```

## Data transformations

| Field | Source | Stage | Stage | Stage | Stage |
|---|---|---|---|---|---|
| `customer_id` | Cognito / API auth | Auth | Pass through | Pass through | - |
| `transcript` | Transcribe | Classify | Agent | - | - |
| `intent` | - | Classify | - | - | - |
| `tool_calls` | - | - | Agent | Tools | - |
| `tool_results` | - | - | - | Tools | Agent |
| `response_text` | - | - | Agent | - | TTS |
| `audio_url` | - | - | - | - | TTS |
| `feedback_rating` | Customer | - | - | - | FB |

## Storage layout

### S3 catalog bucket

```
s3://retailpulse-dev-catalog/
├── master.json              # Full product list (master)
├── categories/              # Category-specific files
│   ├── apparel-men-shirts.json
│   ├── electronics.json
│   └── ...
└── images/                  # Product images (optional)
    ├── SHIRT-001.jpg
    └── ...
```

### DynamoDB tables

```
retailpulse-dev-orders
  PK: customer_id
  SK: order_id
  Attrs: items, total_inr, status, created_at, delivered_at, ...

retailpulse-dev-feedback
  PK: feedback_id
  GSI: session-index (PK: session_id, SK: created_at)
  Attrs: agent, rating, comments, resolved

retailpulse-dev-conversations
  PK: session_id
  GSI: customer-index (PK: customer_id, SK: created_at)
  Attrs: transcript, intent, agent, response, audio_url, duration
```

### S3 Vectors index

```
index: retailpulse-chunks-v1
dimensions: 1024
distance: cosine

vector[chunk_id] = {
  data: { float32: [...] },
  metadata: { source: "...", format: "...", category: "..." }
}
```

## What lives where (storage decision matrix)

| Data type | Store | Why |
|---|---|---|
| Catalog master | S3 | Cheap, durable, large objects |
| Orders | DynamoDB | ACID, queryable, fast lookups |
| Feedback | DynamoDB | ACID, queryable for DSPy training |
| Conversations | DynamoDB | Audit trail, queryable by customer |
| Product vectors | S3 Vectors | Fast similarity search, cheap |
| FAQ/policy vectors | S3 Vectors | Same as product |
| Voice audio (raw) | S3 (transient) | Discarded after transcription |
| TTS audio (cached) | S3 | Cache popular responses |

## See also

- [HLD](01-hld.md) — service boundaries
- [LLD](02-lld.md) — data shapes, code structure
- [Component diagram](03-component-diagram.md) — module dependencies
- [Deployment diagram](05-deployment-diagram.md) — AWS topology
- [API reference](../api/rest-api.md) — external HTTP API
- [Data model](../data-model.md) — entity relationships
