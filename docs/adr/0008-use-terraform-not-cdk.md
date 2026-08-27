# ADR-0008: Use Terraform for IaC, not AWS CDK

- **Status**: Accepted
- **Date**: 2026-08-27
- **Deciders**: Vijay Madhu, Mavis
- **Tags**: infrastructure, tooling

## Context and problem statement

We need to choose an IaC tool for the 50+ AWS resources that RetailPulse will create. The choice affects:
- Who can read/modify infrastructure
- How reusable the codebase is for the other 14 portfolio projects
- Long-term maintainability
- Tooling ecosystem (linting, scanning, docs generation)

## Decision drivers

- Cloud-portability (project tagline is "cloud-portable")
- Tooling maturity (linter, scanner, doc generator)
- Public repo readability (recruiters + contributors)
- Multi-account deployment (single tool, multiple AWS accounts)
- Skill transfer (Terraform is more transferable than CDK)

## Considered options

### Option 1: AWS CDK (TypeScript)

- ✅ First-class AWS support
- ✅ TypeScript types
- ❌ AWS-only (not portable)
- ❌ Less portable skills

### Option 2: AWS CDK (Python)

- ✅ Same as TS but in Python
- ❌ Still AWS-only

### Option 3: Terraform ≥1.9 (chosen)

- ✅ **Cloud-portable** — same HCL works for AWS, Azure, GCP
- ✅ **Mature tooling** — tflint, tfsec, checkov, terraform-docs
- ✅ **Declarative HCL** is more readable than CDK code
- ✅ **State portability** — S3 backend works everywhere
- ✅ **Module ecosystem** — public registry for common patterns

## Decision outcome

**Chosen option 3: Terraform ≥1.9** for all infrastructure.

Application code remains Python (Lambda handlers, agent logic, parsers, embedders). Terraform handles only provisioned resources (buckets, DynamoDB, IAM, Step Functions, etc.).

### Consequences

**Positive**

- Cloud-portable: same `infra/terraform/` can deploy to AWS, Azure, GCP
- Rich tooling: tflint, tfsec, checkov, terraform-docs
- State in S3 with DynamoDB locking is the de-facto standard
- Module reusability across the 15-project portfolio

**Negative**

- Less type safety than CDK
- Provider bug workarounds sometimes required

### Confirmation

- All infrastructure changes go through `terraform plan` in PRs
- `tfsec` reports 0 high/critical findings
- Modules are reusable across at least 3 portfolio projects

## Pros and cons of the options

| Option | Cloud-portable | Tooling | Onboarding | Mature |
|---|---|---|---|---|
| CDK (TS) | ❌ AWS only | Medium | Slow (TS) | ✅ |
| CDK (Python) | ❌ AWS only | Medium | Medium | ✅ |
| **Terraform** | **✅ All** | **Rich** | **Fast** | **✅** |
| Pulumi | ✅ All | Medium | Medium | ⚠️ |

## References

- [Terraform AWS provider](https://registry.terraform.io/providers/hashicorp/aws/latest/docs)
- [tflint](https://github.com/terraform-linters/tflint)
- [tfsec](https://github.com/aquasecurity/tfsec)
- [terraform-docs](https://github.com/terraform-docs/terraform-docs)
