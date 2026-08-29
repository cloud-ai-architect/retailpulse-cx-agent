# ADR-0005: Use Amazon Titan Embed Text v2 for embeddings

- **Status**: Accepted
- **Date**: 2026-08-27
- **Deciders**: Vijay Madhu, Mavis
- **Tags**: ml, embeddings, cost

## Context and problem statement

RetailPulse needs embeddings for:

- RAG over the product catalog (so Sales can find similar items)
- RAG over FAQ + return policies (for Support and Returns)
- Long-term memory of customer interactions

Requirements:

- Available in `ap-south-1` (Mumbai, our target region)
- Cost ≤ $0.10 per 1M tokens
- 1024 dims or less (S3 Vectors sweet spot)
- Multilingual (for future Indian market expansion)
- Native AWS integration (no external API)

## Decision drivers

- Cost efficiency (per-token pricing)
- Multilingual support (future Indian market)
- AWS-native (no data egress, no external dependencies)
- Predictable latency for real-time search

## Considered options

### Option 1: Amazon Titan Embed Text v2 (chosen)

- ✅ **$0.02 per 1M input tokens** (cheapest in-region)
- ✅ 1024 / 512 / 256-dim options
- ✅ Multilingual (100+ languages)
- ✅ Native to S3 Vectors and Bedrock
- ⚠️ No domain-specific tuning out of the box

### Option 2: Cohere Embed v3

- ✅ Excellent quality benchmarks
- ⚠️ $0.10 per 1M tokens (5× more expensive)
- ✅ Strong domain performance

### Option 3: Amazon Titan Embed Image v1

- ❌ Wrong modality (we need text)

## Decision outcome

**Chosen option 1: Amazon Titan Embed Text v2 (1024-dim)** as the default embedder.

Cohere v3 remains available as a per-source alternative (e.g., for code-heavy FAQs) configured via `config/embedders/cohere-multilingual.yaml`.

### Consequences

**Positive**

- $0.02/1M tokens → $0.02 to embed 1M chunks
- Multilingual without extra configuration
- Same-region, no egress cost

**Negative**

- Quality may lag Cohere on some domain-specific benchmarks
- No batch API — call per chunk, parallelize via Lambda concurrency

### Confirmation

- Embedding quality: retrieval precision@10 > 0.80 on held-out test set
- Total embedding cost per million chunks < $0.10

## Pros and cons of the options

| Model | Cost/1M tok | Dims | Multilingual | Quality | In-region |
|---|---|---|---|---|---|
| **Titan v2** | **$0.02** | 1024/512/256 | ✅ | Good | ✅ |
| Cohere v3 | $0.10 | 1024 | ✅ (v3-mul) | Excellent | ✅ |
| Titan Image v1 | $0.08 | 1024 | n/a | (images) | ✅ |

## References

- [Amazon Titan Embeddings](https://docs.aws.amazon.com/bedrock/latest/userguide/titan-embedding-models.html)
- [Bedrock pricing](https://aws.amazon.com/bedrock/pricing/)
