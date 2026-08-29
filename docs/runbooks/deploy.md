# Deploy Runbook

## Purpose

Step-by-step procedure to deploy RetailPulse to a new AWS account, or to redeploy after a change. This is the operational reference for the bootstrap + apply flow.

## Pre-requisites

- [ ] AWS CLI ≥ 2.x installed and configured (`aws configure`)
- [ ] Terraform ≥ 1.9 installed
- [ ] Python ≥ 3.12 (for local testing, optional)
- [ ] GitHub CLI (for OIDC setup, optional)
- [ ] AWS account with admin access for the bootstrap step
- [ ] GitHub repo with admin access (for secrets)

## Deploy to a new AWS account

### Step 1: Clone the repo

```bash
git clone <https://github.com/cloud-ai-architect/retailpulse-cx-agent.git>
cd retailpulse-cx-agent
```

### Step 2: Run bootstrap (one time per account)

```bash
bash scripts/bootstrap.sh retailpulse dev ap-south-1
```

This creates:

- S3 bucket for Terraform state (versioned, encrypted, public-blocked)
- DynamoDB table for state locking
- GitHub OIDC provider
- GitHub Actions deploy IAM role

The script prints the role ARN and bucket names. **Copy these.**

### Step 3: Add GitHub secrets

Go to your GitHub repo → Settings → Secrets and variables → Actions → New repository secret:

| Name | Value | Source |
|---|---|---|
| `AWS_DEPLOY_ROLE_ARN` | `arn:aws:iam::ACCOUNT:role/retailpulse-github-deploy-role-dev` | From bootstrap output |
| `AWS_REGION` | `ap-south-1` | From bootstrap input |

### Step 4: Initialize Terraform

```bash
cd infra/terraform
terraform init \
  -backend-config="bucket=retailpulse-tfstate-dev" \
  -backend-config="region=ap-south-1" \
  -backend-config="dynamodb_table=retailpulse-tfstate-lock-dev"
```

### Step 5: Review the plan

```bash
terraform plan -var-file=envs/dev.tfvars -out=tfplan
```

Expected output: 30–50 resources to add, 0 to change, 0 to destroy.

**Important**: If the plan shows any resources being **destroyed**, do NOT apply. Investigate first — it usually means the state has drifted from reality.

### Step 6: Apply

```bash
terraform apply tfplan
```

Time: ~5–10 minutes.

### Step 7: Verify

```bash
cd ../..
bash scripts/verify.sh dev ap-south-1
```

All checks should pass.

### Step 8: Upload a test catalog

```bash
aws s3 sync data-curator/output/ s3://retailpulse-dev-catalog/ --region ap-south-1
```

### Step 9: Test the agent

Open the API URL in Postman or via the CLI. Send a test message:

```bash
aws apigatewayv2 create-deployment --api-id <api-id> --stage-name prod --region ap-south-1
```

Or use the `ui/index.html` to test the web interface.

## Redeploy after a code change

For changes that affect infrastructure:

```bash
# Make your changes
# Commit and push
git add -A
git commit -s -m "feat: add new agent tool"
git push origin main

# GitHub Actions runs plan + apply automatically
# Review the PR or check Actions tab
```

For changes that affect only Lambda code:

```bash
# GitHub Actions rebuilds and updates the Lambda code
# No infra change required
```

## Roll back a deploy

If a deploy breaks something:

```bash
# Option 1: Revert the commit and push
git revert HEAD
git push origin main

# Option 2: Apply previous state
cd infra/terraform
terraform plan -var-file=envs/dev.tfvars
# If destructive, use:
terraform state pull > current.tfstate
# Restore previous state from S3 versioning
# Then apply
```

## Multi-account deploy

To deploy the same codebase to a second AWS account:

```bash
# In the second account:
bash scripts/bootstrap.sh retailpulse dev ap-south-1 cloud-ai-architect retailpulse-cx-agent

# In your fork's GitHub:
# - Add the same secrets (different role ARN)
# - Push to your fork's main

# In your local clone of the fork:
cd infra/terraform
terraform init ...  # (with new backend)
terraform plan -var-file=envs/dev.tfvars
terraform apply -var-file=envs/dev.tfvars
```

## Environment promotion (dev → staging → prod)

The codebase uses the same Terraform for all environments; only `envs/<env>.tfvars` differs.

```bash
# In the same AWS account, with separate state:
terraform init -backend-config="bucket=retailpulse-tfstate-staging" ...
terraform plan -var-file=envs/staging.tfvars
terraform apply -var-file=envs/staging.tfvars

# In production, ALWAYS run plan first, review with team
# Manual approval via GitHub Environment "production"
```

## Troubleshooting

### "AccessDenied" during terraform plan

- Check the `AWS_DEPLOY_ROLE_ARN` GitHub secret matches the role from bootstrap
- Verify OIDC trust policy includes your repo
- Check `aws sts get-caller-identity` works locally

### "Bucket already exists and is owned by you" or "by another account"

- The bucket name is globally unique. If another AWS account created `retailpulse-vectors-dev`, pick a different name (use `random_id` suffix in `envs/<env>.tfvars`)

### Bedrock "AccessDeniedException"

- You need to enable model access in the Bedrock console first
- Go to <https://ap-south-1.console.aws.amazon.com/bedrock/home> → Model access → Enable "Anthropic Claude Sonnet 4.5", "Cohere Embed v3", "Titan Text Embeddings v2"

### Step Function execution fails immediately

- Check CloudWatch logs for the failing Lambda
- Verify the IAM role has permissions for S3 GetObject on the raw bucket
- Verify the S3 event notification is set on the raw bucket

### CloudFront returns 403

- Check the S3 bucket policy allows CloudFront OAC
- Check the CloudFront origin is configured correctly
- Wait ~5 minutes for CloudFront propagation

## See also

- [Bootstrap script](../../scripts/bootstrap.sh) — New-account setup
- [Destroy script](../../scripts/destroy.sh) — Tear down
- [Verify script](../../scripts/verify.sh) — Health check
- [Architecture overview](../architecture/00-overview.md) — What gets deployed
