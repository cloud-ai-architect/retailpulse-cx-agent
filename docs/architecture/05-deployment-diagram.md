# Deployment Diagram

## Purpose

This document shows the **AWS topology** of a deployed RetailPulse instance — what resources exist in which region/account, how they connect, and the network paths data takes.

## Single-account, single-region deployment

```mermaid
graph TB
    subgraph Internet[Public Internet]
        C[Customer]
        D[3PL / Shipping API]
    end

    subgraph CF[CloudFront edge]
        CDN[CloudFront<br/>retailpulse-ui-cdn]
    end

    subgraph Region[AWS Region: ap-south-1]
        subgraph Public[Public-facing]
            UI[S3: retailpulse-ui-dev<br/>static website]
        end

        subgraph API[API layer]
            GW[API Gateway<br/>retailpulse-api-dev]
            OA[Orchestrator Lambda]
            SA[Sales Lambda]
            SU[Support Lambda]
            RA[Returns Lambda]
        end

        subgraph Async[Async processing]
            SF[Step Function<br/>retailpulse-pipeline]
            EB[EventBridge rule]
            FGT[Fargate Spot<br/>browser-use]
        end

        subgraph Tools[Tool layer]
            CT[Catalog Tool]
            PT[Price Compare]
            OT[Order Tool]
            RT[Refund Tool]
            TT[Transcribe + Polly]
        end

        subgraph Storage[Storage]
            CAT[(Catalog S3)]
            ORD[(Orders DDB)]
            KB[(KB Vectors)]
            FB[(Feedback DDB)]
            CO[(Conversations DDB)]
        end

        subgraph IAM[IAM + OIDC]
            IDP[OIDC Provider]
            ROLE[Deploy Role]
        end

        subgraph Ops[Operations]
            CW[CloudWatch]
            SNS[SNS: failures]
            BGT[Budget alarm]
        end
    end

    C --> CDN
    CDN --> UI
    C --> GW
    GW --> OA
    OA --> SF
    SF --> SA
    SF --> SU
    SF --> RA
    SF --> TT
    SA --> CT
    SU --> OT
    RA --> OT
    RA --> RT
    CT --> CAT
    OT --> ORD
    RT --> ORD
    PT --> FGT
    FGT --> D
    SA & SU & RA --> KB
    SA & SU & RA --> FB
    SA & SU & RA --> CO
    EB --> SF
    BGT -.->|alerts| CW
    SNS -.->|alerts| CW
    ROLE -.->|assumes| IDP
```

## Resources by AWS service

| Service | Resources | Naming |
|---|---|---|
| S3 | 3 buckets | `retailpulse-{raw,vectors,ui}-dev` |
| S3 Vectors | 1 index | `retailpulse-chunks-v1` (1024-dim, cosine) |
| DynamoDB | 3 tables | `retailpulse-{orders,feedback,conversations}-dev` |
| Lambda | 7 functions | `retailpulse-{detect,parse,chunk,...,orchestrator,sales,support,returns,transcribe,polly}-dev` |
| Step Function | 1 state machine | `retailpulse-pipeline-dev` |
| EventBridge | 1 rule | `retailpulse-s3-trigger-dev` |
| API Gateway | 1 HTTP API | `retailpulse-api-dev` |
| CloudFront | 1 distribution | `retailpulse-ui-cdn-dev` |
| ECS Fargate | 1 task definition | `retailpulse-browser-use-dev` |
| SNS | 1 topic | `retailpulse-failures-dev` |
| CloudWatch | Log groups | `/aws/lambda/retailpulse-*-dev` |
| Budgets | 1 budget | `retailpulse-monthly-dev` |
| IAM | 1 OIDC + 4 roles | `retailpulse-*` |
| Resource Group | 1 group | `rg-retailpulse-dev` |

## Fargate for browser-use

```mermaid
graph TB
    subgraph FGT[Fargate Task]
        Browser[Headless Chromium]
        BUse[browser-use library]
        S3Out[S3 output bucket]
    end

    Browser --> BUse
    BUse -->|navigate| S1[Amazon]
    BUse -->|navigate| S2[Walmart]
    BUse -->|extract| S3Out
```

Fargate Spot is used (~$0.01/hr when running). Task boots in ~30s, runs the compare, writes JSON to S3, then dies.

## No VPC by design

This deployment has **no VPC** because:

1. All services are AWS-managed and accessed via service endpoints
2. Lambda functions run in AWS-managed compute (not in a customer VPC)
3. Fargate for browser-use runs in AWS-managed compute (no VPC)
4. Eliminates NAT gateway cost (~$32/month per AZ)
5. Eliminates VPC endpoint complexity for S3, DynamoDB, etc.

If Phase 5 introduces a need for private networking, a VPC would be added at that point.

## Account-wide controls (assumed pre-existing)

These should be set in the AWS Organization or root account, NOT in this Terraform:

- **Service Control Policies (SCPs)** — region restrictions, service denylist
- **AWS Config rules** — required tags, public bucket detection
- **CloudTrail** — organization-wide audit log
- **IAM Access Analyzer** — unused permission detection
- **GuardDuty** — threat detection

## Tagging strategy

Every resource carries:

```hcl
tags = {
  Project     = "retailpulse"
  Environment = "dev"  # dev | staging | prod
  Owner       = "vijay"
  CostCenter  = "portfolio"
  ManagedBy   = "terraform"
}
```

Resource Group `rg-retailpulse-dev` is filter-based:

```text
TagFilters: Project=retailpulse AND Environment=dev
```

## Cross-account deployment

To deploy the same codebase to a second AWS account:

```bash
# In the second account:
bash scripts/bootstrap.sh retailpulse dev ap-south-1 cloud-ai-architect retailpulse-cx-agent

# In your fork's GitHub Actions:
# - Add the same secrets (different role ARN)
# - Push to your fork's main

# In your local clone of the fork:
cd infra/terraform
terraform init -backend-config="bucket=retailpulse-tfstate-second" ...
terraform plan -var-file=envs/dev.tfvars
terraform apply -var-file=envs/dev.tfvars
```

**Time to bootstrap new account: ~2 minutes.** Plus 5–8 min for `init/plan/apply` and GitHub Actions secret updates.

## Disaster recovery

| Disaster | Recovery |
|---|---|
| Region down | Re-deploy to a new region (multi-region is Phase 5) |
| Accidental bucket delete | Versioning + soft delete; restore from previous version |
| Terraform state corruption | Restore from S3 versioning (S3 has 99.999999999% durability) |
| Bad deploy | `terraform apply` previous commit; OIDC allows rapid rollback |
| Compromised GitHub PAT | Rotate GitHub secrets; OIDC scope is by repo so blast radius is small |

## See also

- [HLD](01-hld.md) — service boundaries
- [LLD](02-lld.md) — data shapes, code structure
- [Security model](06-security-model.md) — trust boundaries
- [Cost model](07-cost-model.md) — per-resource cost
- [Bootstrap script](../../scripts/bootstrap.sh) — New-account setup
