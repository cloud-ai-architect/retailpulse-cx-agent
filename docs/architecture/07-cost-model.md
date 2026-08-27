# Cost Model

## Purpose

This document is the **single source of truth** for RetailPulse's cost — what each component costs, what a typical workload costs, and how the architecture decisions keep cost low. Use this to forecast spend, justify architecture choices, and identify optimization opportunities.

## TL;DR

| Scenario | Monthly cost |
|---|---|
| **Idle** (no traffic) | **~$2 / month** |
| **Light usage** (100 conversations, 1K searches) | **~$15 / month** |
| **Moderate usage** (1K conversations, 10K searches) | **~$50 / month** |
| **Heavy usage** (10K conversations, 100K searches) | **~$300 / month** |

## Cost by component

### Compute (Lambda + Step Functions)

| Component | Pricing | Per-conversation cost |
|---|---|---|
| Lambda invocations (8 agents) | $0.20 / 1M requests | ~$0.002 |
| Step Function transitions | $0.025 / 1K transitions | ~$0.005 |
| Fargate Spot (browser-use, ~30s per call) | $0.0125 / hour | ~$0.10 (when invoked) |
| **Per-conversation compute** | | **~$0.10** |

### AI / ML (Bedrock)

| Component | Pricing | Per-conversation cost |
|---|---|---|
| Bedrock Sonnet 4.5 (input) | $3 / 1M tokens | ~$0.15 (5K tokens) |
| Bedrock Sonnet 4.5 (output) | $15 / 1M tokens | ~$0.30 (2K tokens) |
| Titan v2 Embeddings | $0.02 / 1M tokens | ~$0.01 |
| Bedrock Haiku 4 (orchestrator) | $0.25 / 1M input | ~$0.005 |
| **Per-conversation AI** | | **~$0.45** |

### Voice (Polly + Transcribe)

| Component | Pricing | Per-conversation cost |
|---|---|---|
| Polly (neural, 5K chars response) | $4 / 1M chars | ~$0.02 |
| Transcribe (5 min call) | $1.44 / hour | ~$0.12 |
| **Per-conversation voice** | | **~$0.14** |

### Storage

| Component | Pricing | Per-month cost |
|---|---|---|
| S3 catalog (1 GB) | $0.023 / GB | $0.023 |
| S3 Vectors (1 GB) | $0.04 / GB | $0.04 |
| DynamoDB orders (1 GB) | $1.25 / M WCU/RCU | ~$0.10 (1K ops/day) |
| DynamoDB feedback | included | ~$0.05 |
| **Storage for 1 GB corpus** | | **~$0.20** |

### API and CDN

| Component | Pricing | Per-request cost |
|---|---|---|
| API Gateway HTTP | $1.00 / million requests | $0.000001 |
| Lambda (search) | $0.20 / 1M | $0.0000002 |
| Bedrock Titan (query) | $0.02 / 1M tokens | $0.0000002 |
| S3 Vectors query | $0.004 / 1K queries | $0.000004 |
| **Per search request** | | **~$0.00001** |
| CloudFront (10 GB transfer) | $0.085 / GB | $0.85 / month |
| CloudFront (1M requests) | $0.01 / 10K | $1.00 / month |

### Other

| Component | Pricing | Per-month cost |
|---|---|---|
| CloudWatch logs (1 GB) | $0.50 / GB | $0.50 |
| CloudWatch metrics (10 custom) | $0.30 / metric | $3.00 |
| SNS (1K notifications) | $0.50 / million | $0.0005 |
| Budgets (1 budget) | $0.01 / budget / day | $0.30 |
| KMS (1 key) | $1.00 / key / month | $1.00 |

## Per-conversation cost

A typical 5-minute voice conversation with 1 price-compare call:

| Stage | Cost |
|---|---|
| Transcribe (5 min) | $0.12 |
| Bedrock Sonnet 4.5 (5K input + 2K output) | $0.45 |
| Bedrock Haiku 4 (orchestrator) | $0.005 |
| Titan v2 (1K tokens for KB lookup) | $0.01 |
| Bedrock (Sales agent tools) | $0.20 |
| Fargate Spot (browser-use, 30s) | $0.10 |
| Bedrock (Returns agent) | $0.20 |
| Polly (5K chars response) | $0.02 |
| Lambda + Step Function | $0.01 |
| DynamoDB writes | $0.01 |
| **Total per voice conversation** | **~$1.10** |

A text-only conversation (no voice, no price-compare): **~$0.30**.

## Cost scaling

| Workload | Conversations/mo | AI cost | Storage | API + voice | **Total** |
|---|---|---|---|---|---|
| Idle | 0 | $0 | $2 | $0 | **$2** |
| Light | 100 | $45 | $2 | $15 | **$62** |
| Moderate | 1,000 | $450 | $5 | $100 | **$555** |
| Heavy | 10,000 | $4,500 | $25 | $500 | **$5,025** |

For a portfolio demo (100 conversations/month), expect ~$60/month.

## Cost comparison: Bedrock Sonnet 4.5 vs alternatives

| Model | Input/1M | Output/1M | Quality | For RetailPulse |
|---|---|---|---|---|
| **Sonnet 4.5** | $3 | $15 | Excellent | ✅ Default |
| Haiku 4 | $0.25 | $1.25 | Good | ✅ Orchestrator (cheap) |
| Nova Pro | $0.80 | $3.20 | Good | Alternative |
| GPT-4o | $2.50 | $10 | Excellent | Alternative (external) |

We use **Sonnet 4.5 for the agents** (best quality for complex reasoning) and **Haiku 4 for the orchestrator** (fast + cheap for intent classification).

## Cost comparison: S3 Vectors vs alternatives

| Solution | Idle cost/month | 10K vectors, 100K queries |
|---|---|---|
| **S3 Vectors** | **$0.04** | **$0.40** |
| OpenSearch Serverless | $432 | $432 |
| Aurora pgvector | $43+ | $50 |
| Pinecone | $70 | $70 |

**S3 Vectors is 1000× cheaper than OpenSearch Serverless at idle.**

## Cost comparison: Polly + Transcribe vs LiveKit

| Solution | Per-conversation | Latency | AWS-native |
|---|---|---|---|
| **Polly + Transcribe** | **~$0.14** | ⚠️ ~2s | ✅ |
| LiveKit | ⚠️ ~$0.10 | ✅ <500ms | ❌ |
| OpenAI Realtime | ❌ ~$0.60 | ✅ <500ms | ❌ |

**Polly + Transcribe is cheapest but slightly higher latency.** Acceptable for portfolio scope.

## Cost optimization techniques

### Already applied

1. **S3 Vectors over OpenSearch** — 1000× cheaper idle
2. **Bedrock Haiku for orchestrator** — 12× cheaper than Sonnet for classification
3. **Lambda concurrency limits** — prevent runaway cost
4. **DynamoDB on-demand** — only pay for what you use
5. **S3 lifecycle policies** — auto-expire old raw files after 30 days
6. **CloudWatch log retention** — 30 days, not forever
7. **HTTP API over REST API** — 70% cheaper per request
8. **Fargate Spot for browser-use** — 70% cheaper than on-demand

### Future optimizations (Phase 5)

1. **Provisioned concurrency** for high-traffic Lambdas — saves ~30% on sustained traffic
2. **S3 Intelligent-Tiering** for raw bucket — auto-move to Infrequent Access after 30 days
3. **Reserved capacity for DynamoDB** if traffic is predictable
4. **Caching layer** (DAX or ElastiCache) for frequently-searched queries
5. **Batch API for Bedrock** — up to 100 messages per call
6. **DSPy prompt optimization** — reduce token usage over time

## Budgets and alarms

Three budget thresholds with automatic alerts:

```hcl
resource "aws_budgets_budget" "retailpulse_monthly" {
  budget_type  = "COST"
  limit_amount = "50"
  limit_unit   = "USD"
  time_unit    = "MONTHLY"

  notification {
    threshold                 = 25   # $12.50
    notification_type         = "ACTUAL"
    subscriber_email_addresses = ["vijaymadhu.india@gmail.com"]
  }
  notification {
    threshold                 = 100  # $50
    notification_type         = "ACTUAL"
    subscriber_email_addresses = ["vijaymadhu.india@gmail.com"]
  }
  notification {
    threshold                 = 250  # $125
    notification_type         = "ACTUAL"
    subscriber_email_addresses = ["vijaymadhu.india@gmail.com"]
  }
}
```

## What we're NOT optimizing for

- **Multi-AZ redundancy** — single AZ is acceptable for portfolio scope
- **Multi-region** — Phase 5 enhancement
- **Sub-100ms p99 latency** — p95 < 2s is sufficient
- **99.99% availability** — 99.9% (AWS-managed) is sufficient

If any of these become important, cost will increase 2–10×.

## See also

- [ADR-0002: Use CrewAI](../adr/0002-use-crewai-as-primary-framework.md) — Framework cost
- [ADR-0005: Use Titan v2](../adr/0005-use-titan-v2-embeddings.md) — Embedding cost
- [ADR-0006: Use S3 Vectors](../adr/0006-use-s3-vectors-not-opensearch.md) — Why cheap
- [ADR-0009: Use Voice Polly vs LiveKit](../adr/0009-use-voice-polly-vs-livekit.md) — Voice cost
- [Deployment diagram](05-deployment-diagram.md) — Resources
- [Cost investigation runbook](../runbooks/cost-investigation.md) — How to investigate spikes
