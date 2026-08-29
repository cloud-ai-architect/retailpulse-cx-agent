# Cost Investigation Runbook

## Purpose

Step-by-step procedure to investigate a cost spike or unexpected charge. Use this when an AWS bill is higher than expected, or when a budget alarm fires.

## First 5 minutes

```bash
# 1. Check Cost Explorer for the current month
# Open: <https://console.aws.amazon.com/cost-management/home>

# 2. Check if any budget alarms fired
aws budgets describe-budgets --account-id $(aws sts get-caller-identity --query Account --output text)

# 3. Get a quick breakdown by service for the last 7 days
aws ce get-cost-and-usage \
  --time-period Start=$(date -u -d '7 days ago' +%Y-%m-%d),End=$(date -u +%Y-%m-%d) \
  --granularity DAILY \
  --metrics "UnblendedCost" \
  --group-by Type=DIMENSION,Key=SERVICE \
  --query "ResultsByTime[*].Groups[?Metrics.UnblendedCost.Amount>\`10\`]"
```

## Common cost spikes and fixes

### Bedrock spending spiking

**Symptom**: Bedrock line item dominates the bill.

**Diagnostic**:

```bash
# Check Bedrock usage in Cost Explorer
aws ce get-cost-and-usage \
  --time-period Start=$(date -u -d '7 days ago' +%Y-%m-%d),End=$(date -u +%Y-%m-%d) \
  --granularity DAILY \
  --metrics "UnblendedCost" \
  --group-by Type=DIMENSION,Key=USAGE_TYPE \
  --filter '{"Dimensions":{"Key":"SERVICE","Values":["Amazon Bedrock"]}}'
```

**Common causes**:

| Cause | Fix |
|---|---|
| Long conversations | Reduce max iterations per agent |
| Wrong model selected (Sonnet instead of Haiku for orchestrator) | Check IAM permissions + Lambda env vars |
| Token count much higher than expected | Check chunker config + agent prompt size |
| Concurrent users | Add Lambda concurrency limit |

**Fix**:

```bash
# Throttle the Lambda concurrency
aws lambda put-function-concurrency \
  --function-name retailpulse-dev-sales \
  --reserved-concurrent-executions 5 \
  --region ap-south-1
```

### Lambda runaway

**Symptom**: Lambda bill spikes; thousands of invocations.

**Diagnostic**:

```bash
# Get Lambda invocation metrics for last 24h
aws cloudwatch get-metric-statistics \
  --namespace AWS/Lambda \
  --metric-name Invocations \
  --dimensions Name=FunctionName,Value=retailpulse-dev-sales \
  --start-time $(date -u -d '24 hours ago' +%Y-%m-%dT%H:%M:%S) \
  --end-time $(date -u +%Y-%m-%dT%H:%M:%S) \
  --period 3600 \
  --statistics Sum
```

**Common causes**:

| Cause | Fix |
|---|---|
| Bug in code creates infinite loop | Patch code, redeploy |
| Recursive Step Function trigger (Lambda → S3 → Lambda) | Add `event_source_filter` or check `requestId` |
| Test script left running | Kill the script |
| API Gateway has no rate limit | Add throttling |

### Fargate Spot pricing spike

**Symptom**: Fargate bill increases.

**Diagnostic**:

```bash
# Check Fargate usage
aws ce get-cost-and-usage \
  --time-period Start=$(date -u -d '7 days ago' +%Y-%m-%d),End=$(date -u +%Y-%m-%d) \
  --granularity DAILY \
  --metrics "UnblendedCost" \
  --filter '{"Dimensions":{"Key":"SERVICE","Values":["Amazon Elastic Container Service"]}}'
```

**Common causes**:

| Cause | Fix |
|---|---|
| browser-use running for too long | Add timeout, optimize pages visited |
| Spot price increased | Switch to on-demand for critical times, Spot for dev |
| Fargate task memory too high | Right-size to 512MB or 1GB |

### DynamoDB throughput

**Symptom**: DynamoDB line item high.

**Diagnostic**:

```bash
# Check consumed WCU/RCU
aws cloudwatch get-metric-statistics \
  --namespace AWS/DynamoDB \
  --metric-name ConsumedWriteCapacityUnits \
  --dimensions Name=TableName,Value=retailpulse-dev-orders \
  --start-time $(date -u -d '24 hours ago' +%Y-%m-%dT%H:%M:%S) \
  --end-time $(date -u +%Y-%m-%dT%H:%M:%S) \
  --period 3600 \
  --statistics Sum
```

**Common causes**:

| Cause | Fix |
|---|---|
| Hot partition key (sequential UUIDs are fine; timestamp-based is bad) | Switch PK to UUID |
| Scan instead of query | Add GSI; use Query |
| No TTL on items | Enable TTL |

### CloudWatch logs

**Symptom**: CloudWatch Logs line item higher than expected.

**Diagnostic**:

```bash
# Find log groups by size
aws logs describe-log-groups \
  --query "logGroups[?storedBytes>\`100000000\`].[logGroupName,storedBytes]" \
  --output table
```

**Common causes**:

| Cause | Fix |
|---|---|
| Lambda logging full payload | Add `print` filter to remove sensitive fields |
| Log retention too long | Reduce to 30 days |
| Verbose logging in production | Set `LOG_LEVEL=WARN` in prod |

### Polly/Transcribe costs

**Symptom**: Voice line item is high.

**Diagnostic**:

```bash
# Check voice usage
aws ce get-cost-and-usage \
  --time-period Start=$(date -u -d '7 days ago' +%Y-%m-%d),End=$(date -u +%Y-%m-%d) \
  --granularity DAILY \
  --metrics "UnblendedCost" \
  --group-by Type=DIMENSION,Key=USAGE_TYPE \
  --filter '{"Dimensions":{"Key":"SERVICE","Values":["Amazon Polly"]}}'
```

**Common causes**:

| Cause | Fix |
|---|---|
| Long TTS responses | Truncate responses to <1000 chars |
| Long voice calls | Limit call duration to 5 min |
| High-quality voice | Switch to standard voice for non-critical |

## Cost reduction techniques

### Quick wins (no code change)

1. **Bedrock Haiku for orchestrator** — 12× cheaper than Sonnet
2. **S3 Vectors over OpenSearch** — 1000× cheaper idle
3. **Lambda concurrency limits** — prevent runaway cost
4. **S3 lifecycle policies** — auto-expire old raw files after 30 days
5. **CloudWatch log retention** — 30 days, not forever
6. **HTTP API over REST API** — 70% cheaper per request
7. **Fargate Spot for browser-use** — 70% cheaper than on-demand

### Medium effort (some code change)

1. **Provisioned concurrency** for high-traffic Lambdas — saves ~30% on sustained traffic
2. **S3 Intelligent-Tiering** for catalog bucket — auto-move to Infrequent Access after 30 days
3. **Reserved capacity for DynamoDB** if traffic is predictable
4. **Caching layer** (DAX or ElastiCache) for frequently-searched queries
5. **Batch API for Bedrock** — up to 100 messages per call
6. **DSPy prompt optimization** — reduce token usage over time

### Bigger changes (architectural)

1. **Reserved capacity for predictable workloads**
2. **S3 Vectors tiered storage** (when available)
3. **Multi-region with intelligent routing** — only run in cheaper region when latency allows
4. **Self-hosted Llama 3 for orchestrator** — open-source, no per-token cost

## Cost allocation tags

Make sure the `Project=retailpulse` tag is applied to all resources. The Terraform modules do this automatically, but verify in the AWS Console:

```bash
# Check that all retailpulse resources have the tag
aws resourcegroupstaggingapi get-resources \
  --tag-filters Key=Project,Values=retailpulse \
  --output table
```

If any resources are missing the tag, the IAM policy will deny access to the deploy role — and that's a feature, not a bug. But it would prevent the deploy from working.

## When to escalate

If you find:

- A single resource costing >$100/day unexpectedly
- Unrecognized services in the bill
- Resources in a region you don't use
- A security incident (resources you didn't create)

**Stop the bleeding first**:

```bash
# Disable the runaway Lambda
aws lambda update-function-configuration \
  --function-name retailpulse-dev-sales \
  --reserved-concurrent-executions 0 \
  --region ap-south-1

# Or delete it entirely
aws lambda delete-function \
  --function-name retailpulse-dev-sales \
  --region ap-south-1
```

Then investigate root cause and add guardrails.

## See also

- [Cost model](../architecture/07-cost-model.md) — Expected costs
- [ADR-0002: Use CrewAI](../adr/0002-use-crewai-as-primary-framework.md) — Framework cost
- [ADR-0006: Use S3 Vectors](../adr/0006-use-s3-vectors-not-opensearch.md) — Why cheap
- [ADR-0009: Use Voice Polly vs LiveKit](../adr/0009-use-voice-polly-vs-livekit.md) — Voice cost
- [Deploy runbook](deploy.md) — Forward deploys
- [Incident response runbook](incident-response.md) — Live incidents
