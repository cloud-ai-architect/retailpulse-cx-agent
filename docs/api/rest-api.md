# REST API Reference

## Overview

RetailPulse exposes a small HTTP API for programmatic access. The API is **server-side IAM authenticated** (SigV4); client tools must use AWS credentials.

Base URL: `https://<api-id>.execute-api.ap-south-1.amazonaws.com` (printed by Terraform output)

## Authentication

The API uses IAM authentication via AWS Signature Version 4. To call it, you need AWS credentials with permission to invoke the API.

```python
import boto3
import requests
from botocore.auth import SigV4Auth
from botocore.awsrequest import AWSRequest

session = boto3.Session()
credentials = session.get_credentials()
api_url = "https://abc123.execute-api.ap-south-1.amazonaws.com"

def signed_post(path, body=None):
    url = f"{api_url}{path}"
    headers = {"Content-Type": "application/json"}
    body_str = json.dumps(body) if body else None
    request = AWSRequest(method="POST", url=url, data=body_str, headers=headers)
    SigV4Auth(credentials, "execute-api", "ap-south-1").add_auth(request)
    return requests.post(url, headers=dict(request.headers), data=body_str)
```

## Endpoints

### `POST /v1/conversations`

Send a message to the agent team. Returns the agent's response.

**Request body**:

```json
{
  "session_id": "uuid-or-null",
  "customer_id": "uuid-or-null",
  "channel": "voice" | "web" | "api",
  "transcript": "I want to return my order",
  "context": {
    "recent_orders": ["ORD-000123", "ORD-000122"]
  }
}
```

**Response**:

```json
{
  "session_id": "abc-123",
  "intent": "returns",
  "agent": "returns",
  "response": "I can help you with that. Which order would you like to return?",
  "audio_url": "https://...polly-output.mp3",
  "tool_calls": [
    {"tool": "lookup_order", "args": {...}, "result": {...}}
  ],
  "duration_ms": 1234
}
```

**Example**:
```bash
curl -X POST \
  -H "Content-Type: application/json" \
  -H "Authorization: AWS4-HMAC-SHA256 ..." \
  -d '{"transcript":"I want to return my order #12345"}' \
  https://abc123.execute-api.ap-south-1.amazonaws.com/v1/conversations
```

**Errors**:

| Status | Code | Description |
|---|---|---|
| 400 | `INVALID_REQUEST` | Missing required field |
| 401 | `UNAUTHORIZED` | SigV4 signature missing or invalid |
| 429 | `THROTTLED` | Rate limit exceeded |
| 500 | `INTERNAL_ERROR` | Upstream service error |
| 503 | `SERVICE_UNAVAILABLE` | Bedrock or S3 temporarily unavailable |

### `GET /v1/conversations/{id}`

Retrieve a past conversation by session ID.

**Path parameters**:
- `id` (string, required) — session ID

**Response**:
```json
{
  "session_id": "abc-123",
  "customer_id": "CUST-0042",
  "transcript": "I want to return my order #12345",
  "intent": "returns",
  "agent": "returns",
  "response": "...",
  "tool_calls": [...],
  "created_at": "2026-08-27T12:00:00Z",
  "duration_seconds": 45
}
```

### `GET /v1/catalog/search`

Search the product catalog semantically.

**Query parameters**:
- `q` (string, required) — search query
- `top_k` (int, default 10, max 100)
- `min_price` (decimal, optional)
- `max_price` (decimal, optional)
- `category` (string, optional)

**Response**:
```json
{
  "query": "blue oxford shirt",
  "results": [
    {
      "sku": "SHIRT-001",
      "name": "Oxford Shirt Blue M",
      "price_inr": 2499,
      "score": 0.892,
      "stock": 42
    }
  ]
}
```

### `POST /v1/orders/{id}/refund`

Initiate a refund for an order.

**Path parameters**:
- `id` (string, required) — order ID

**Request body**:
```json
{
  "reason": "Defective product",
  "amount_override": null
}
```

**Response**:
```json
{
  "refund_id": "RF-uuid",
  "order_id": "ORD-000123",
  "amount_inr": 4998,
  "status": "initiated",
  "estimated_days": 7
}
```

### `GET /v1/orders/{id}`

Get order details.

### `GET /v1/feedback`

Get feedback (admin only). Query params: `agent`, `from_date`, `to_date`, `rating`.

## Rate limits

| Endpoint | RPS limit | Burst |
|---|---|---|
| `POST /v1/conversations` | 20 | 40 |
| `GET /v1/conversations/{id}` | 100 | 200 |
| `GET /v1/catalog/search` | 50 | 100 |
| `POST /v1/orders/{id}/refund` | 5 | 10 |
| `GET /v1/orders/{id}` | 50 | 100 |
| `GET /v1/feedback` | 10 | 20 |

## CORS

CORS is configured to allow the KB UI origin. For external clients, add the origin to the Terraform `cors` config.

## Pagination

Search and list endpoints support `page_token` and `page_size` (default 20, max 100).

## Versioning

The API is versioned via the URL prefix: `/v1/...`. Current version: v1. Breaking changes will increment to v2.

## Voice channel

Voice is handled via Amazon Transcribe streaming. For real-time voice, see [ADR-0009](../adr/0009-use-voice-polly-vs-livekit.md).

## See also

- [LLD](../architecture/02-lld.md) — Data shapes
- [Security model](../architecture/06-security-model.md) — Authentication
- [Cost model](../architecture/07-cost-model.md) — Per-request cost
