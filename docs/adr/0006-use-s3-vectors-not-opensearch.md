# ADR-0006: Use S3 Vectors for vector storage, not OpenSearch

- **Status**: Accepted
- **Date**: 2026-08-27
- **Deciders**: Vijay Madhu, Mavis
- **Tags**: storage, cost, vectors

## Context and problem statement

RetailPulse needs a vector store for embeddings of:

- Product catalog (~10K-100K items for a mid-size retailer)
- FAQ + return policies (~1K-5K docs)
- Customer interaction memory

Requirements:

- p95 query latency < 200ms
- Idle cost near zero (side-project economics)
- Native AWS (ap-south-1)
- $50-80/mo total budget

## Decision drivers

- Cost: side-project economics, near-zero idle
- Performance: real-time search UX
- AWS-native, no external services
- Simplicity: minimal ops burden

## Considered options

### Option 1: S3 Vectors (chosen)

- ✅ **$0.04/GB-month storage + $0.004/1K queries**
- ✅ Zero idle cost (no always-on compute)
- ✅ Native AWS, IAM-scoped
- ✅ Purpose-built for this workload

### Option 2: OpenSearch Serverless

- ❌ **$0.30/hour per OCU × 2 OCUs min = $432/month idle**
- ✅ Mature, well-documented
- ❌ Significant cost for side-project

### Option 3: Aurora pgvector

- ⚠️ $43/month minimum (0.5 ACU)
- ✅ Strong SQL semantics
- ⚠️ Degrades above 1M vectors

## Decision outcome

**Chosen option 1: S3 Vectors** for the knowledge base.

- Index: `retailpulse-chunks-v1`
- Dimensions: 1024 (matches Titan v2 default)
- Distance metric: cosine

### Consequences

**Positive**

- ~$0.50/month idle (fits budget)
- Zero cluster management
- IAM-scoped, no separate auth
- Backed by S3 durability (11 9s)

**Negative**

- Less mature; some operations slower than OpenSearch
- No built-in hybrid search
- Limited query expressiveness (top-K only)

### Confirmation

- p95 query latency < 200ms for top-10 over 10K vectors
- Total monthly cost stays under $5 at projected usage

## Pros and cons of the options

| Option | Idle cost/mo | Query cost | Latency | Maturity |
|---|---|---|---|---|
| **S3 Vectors** | **$0.04/GB** | **$0.004/1K** | Low | Medium |
| OpenSearch Serverless | $432 | Included | Very low | High |
| Aurora pgvector | $43+ | Included | Low | High |

## References

- [S3 Vectors](https://aws.amazon.com/s3/vectors/)
- [S3 Vectors pricing](https://aws.amazon.com/s3/pricing/)
- [OpenSearch Serverless](https://docs.aws.amazon.com/opensearch-service/latest/developerguide/serverless.html)
