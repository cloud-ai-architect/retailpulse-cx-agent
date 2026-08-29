# Incident Response Runbook

## Purpose

When something is broken **right now** and the agent is down, the API is returning 500s, or Bedrock is rejecting requests, this is the runbook. It prioritizes **fast detection, fast mitigation, post-mortem later**.

## Before you start

The commands below use `$ACCOUNT_ID` rather than a literal account number, so
this runbook can be read and copied without publishing which account it
operates on. Resolve it once at the start of an incident:

```bash
export ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text)
export AWS_REGION=ap-south-1
```

## Severity levels

| Level | Impact | Response time | Examples |
|---|---|---|---|
| **SEV-1** | Total outage | < 15 min | All agent requests failing; voice channel down |
| **SEV-2** | Degraded | < 1 hour | > 50% agent requests failing; search broken |
| **SEV-3** | Minor | < 4 hours | < 10% of conversations failing; specific tool not working |
| **SEV-4** | Cosmetic | < 1 week | Doc typo, minor UX issue |

## First 60 seconds

```mermaid
flowchart TD
    A[Page received] --> B{What's broken?}
    B -->|Agent| C[Check Step Function executions]
    B -->|Voice| D[Check Polly + Transcribe]
    B -->|API| E[Check API Gateway + CloudWatch]
    B -->|Bedrock| F[Check Bedrock availability]
    B -->|AWS auth| G[Check IAM role + OIDC]

    C --> H[CloudWatch logs]
    D --> H
    E --> H
    F --> H
    G --> H

    H --> I{Known error?}
    I -->|Yes| J[See "Common errors" below]
    I -->|No| K[Page on-call / file sev-1]
```

## Common errors and fixes

### Agent failing in `Orchestrator` state

**Symptom**: Step Function execution status `FAILED`, error in `Orchestrator` state.

**Diagnostic**:

```bash
# Get the failed execution
aws stepfunctions list-executions \
  --state-machine-arn arn:aws:states:ap-south-1:$ACCOUNT_ID:stateMachine:retailpulse-dev-pipeline \
  --status-filter FAILED \
  --max-items 1 \
  --region ap-south-1

# Get the failure event
aws stepfunctions get-execution-history \
  --execution-arn <exec-arn> \
  --region ap-south-1

# Check CloudWatch logs
aws logs tail /aws/lambda/retailpulse-dev-orchestrator --follow --region ap-south-1
```

**Common causes**:

| Error message | Cause | Fix |
|---|---|---|
| `AccessDenied` on `bedrock:InvokeModel` | IAM role missing Bedrock permission | Re-apply Terraform |
| `AccessDenied` on `dynamodb:Query` | IAM role missing DDB permission | Re-apply Terraform |
| `ThrottlingException` on Bedrock | Bedrock rate limit | Reduce Lambda concurrency, add backoff |
| `ValidationException` on input | Bad tool input | Check tool implementation |

### Voice channel failing in `Synthesize` (Polly)

**Symptom**: Step Function succeeds, but no audio returned to customer.

**Diagnostic**:

```bash
aws logs tail /aws/lambda/retailpulse-dev-polly --follow --region ap-south-1
```

**Common causes**:

| Error message | Cause | Fix |
|---|---|---|
| `AccessDenied` on `polly:SynthesizeSpeech` | IAM role missing Polly permission | Re-apply Terraform |
| `TextLengthExceededException` | Response > 3000 chars | Truncate response in agent |
| `ServiceUnavailable` | Polly temporarily down | Retry, check AWS status |

### Voice channel failing in `Transcribe`

**Symptom**: Customer audio not converted to text.

**Diagnostic**:

```bash
aws logs tail /aws/lambda/retailpulse-dev-transcribe --follow --region ap-south-1
```

**Common causes**:

| Error message | Cause | Fix |
|---|---|---|
| `AccessDenied` on `transcribe:StartTranscriptionJob` | IAM role missing Transcribe permission | Re-apply Terraform |
| `BadRequestException` on audio | Bad audio format | Validate audio format in client |
| `LimitExceededException` | Concurrent transcriptions limit | Reduce concurrency |

### Price comparison failing

**Symptom**: `compare_price` tool returns error.

**Diagnostic**:

```bash
aws logs tail /aws/lambda/retailpulse-dev-sales --follow --region ap-south-1
```

**Common causes**:

| Error message | Cause | Fix |
|---|---|---|
| `ECS Task failed` | Fargate task couldn't start | Check Fargate capacity, IAM role |
| `browser-use timeout` | Site too slow | Increase tool timeout |
| `Site blocked headless browser` | Detected as bot | Rotate user agent, add delay |

### API Gateway returning 500s

**Symptom**: HTTP 500 from `/v1/conversations`.

**Diagnostic**:

```bash
aws logs tail /aws/vendedlogs/apigateway/retailpulse-dev-api --follow --region ap-south-1
```

**Common causes**:

| Error | Cause | Fix |
|---|---|---|
| 502 Bad Gateway | Lambda failing | Check Lambda logs |
| 504 Gateway Timeout | Lambda timing out | Increase Lambda timeout |
| 403 Forbidden | IAM auth failing | Check SigV4 signature |

### KB UI completely down

**Symptom**: Browser shows 403, 502, or 504.

**Diagnostic**:

```bash
aws cloudfront get-distribution --id <distribution-id>

# Check S3 UI bucket
aws s3 ls s3://retailpulse-ui-dev/static/ --recursive

# Check CloudFront error rate
aws cloudwatch get-metric-statistics \
  --namespace AWS/CloudFront \
  --metric-name 4xxErrorRate \
  --start-time $(date -u -d '5 minutes ago' +%Y-%m-%dT%H:%M:%S) \
  --end-time $(date -u +%Y-%m-%dT%H:%M:%S) \
  --period 60 \
  --statistics Sum
```

**Common causes**:

| Error | Cause | Fix |
|---|---|---|
| 403 Forbidden | CloudFront OAC misconfigured | Re-apply Terraform; wait 5 min for CF propagation |
| 502 Bad Gateway | S3 bucket policy denies CF | Re-apply Terraform |
| 504 Gateway Timeout | Origin (S3) slow | Check S3 health |

### GitHub Actions deploy fails

**Symptom**: Apply workflow fails with AWS error.

**Diagnostic**:

- Check the Actions tab for the failed run
- Look at the `terraform apply` step output
- Most common: `sts:AssumeRoleWithWebIdentity` fails

**Common causes**:

| Error | Cause | Fix |
|---|---|---|
| `Not authorized to perform sts:AssumeRoleWithWebIdentity` | OIDC trust policy mismatch | Re-run bootstrap, check sub-claim |
| `Error: getting data.aws_caller_identity` | Wrong credentials in workflow | Check secrets |
| `Error: acquiring the state lock` | Stuck lock | Manually delete lock in DynamoDB console |

## Escalation

If you've spent 15 minutes and the issue is unresolved:

1. **Page on-call** (when applicable — for solo side-project, this is you)
2. **Open a SEV-1 incident** in the issue tracker
3. **Consider rolling back** — see [rollback runbook](rollback.md)
4. **Communicate** — post status updates in chat every 30 min

## Post-incident

Within 48 hours of resolution:

1. **Write a post-mortem** — even for SEV-3
2. **Add regression test** — to prevent recurrence
3. **Add an alarm** — to detect faster next time
4. **Update the runbook** — if the runbook was wrong

## Useful one-liners

```bash
# Find all failed executions in the last hour
aws stepfunctions list-executions \
  --state-machine-arn arn:aws:states:ap-south-1:$ACCOUNT_ID:stateMachine:retailpulse-dev-pipeline \
  --status-filter FAILED \
  --region ap-south-1 \
  --query "executions[?startDate>=\`$(date -u -d '1 hour ago' +%Y-%m-%dT%H:%M:%S)\`]"

# Tail all Lambda logs at once
for fn in orchestrator sales support returns catalog order refund transcribe polly; do
  aws logs tail "/aws/lambda/retailpulse-dev-$fn" --follow --region ap-south-1 &
done

# Get current Bedrock service health
aws health describe-events \
  --filter services=BEDROCK \
  --region us-east-1
```

## See also

- [Deploy runbook](deploy.md) — Forward deploys
- [Rollback runbook](rollback.md) — Recovery
- [Cost investigation runbook](cost-investigation.md) — For cost spikes
- [Security model](../architecture/06-security-model.md) — For security incidents
