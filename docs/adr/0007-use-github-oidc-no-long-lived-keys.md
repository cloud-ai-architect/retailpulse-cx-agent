# ADR-0007: Use GitHub OIDC for AWS authentication; no long-lived AWS keys

- **Status**: Accepted
- **Date**: 2026-08-27
- **Deciders**: Vijay Madhu, Mavis
- **Tags**: security, ci-cd

## Context and problem statement

GitHub Actions needs to deploy infrastructure and update Lambda code. The traditional approach (long-lived AWS access keys in GitHub secrets) is a well-known security risk:

- Keys can leak (malicious PR, log scraper, compromised dependency)
- Blast radius = full AWS access for up to 90 days
- Manual rotation is error-prone

## Decision drivers

- **Zero static secrets** in GitHub or anywhere
- **Scoped trust** — only this exact repo, on `main` branch
- **Short-lived tokens** (15 min max)
- **Audit trail** — every `AssumeRoleWithWebIdentity` attributable to a commit
- **Public repo safety** — even public viewers cannot gain AWS access

## Considered options

### Option 1: Long-lived AWS access keys in GitHub Secrets

- ❌ Security risk if leaked
- ❌ Manual rotation

### Option 2: External secret manager + CI

- ✅ Short-lived credentials
- ❌ Out-of-band setup
- ❌ Still bootstraps with long-lived keys

### Option 3: GitHub OIDC federation (chosen)

- ✅ **No long-lived secrets anywhere**
- ✅ Short-lived tokens (15 min)
- ✅ Trust policy scoped to exact repo + branch
- ✅ CloudTrail shows `token.actions.githubusercontent.com` as principal

## Decision outcome

**Chosen option 3: GitHub OIDC** with `sub` claim scoped to `repo:cloud-ai-architect/retailpulse-cx-agent:ref:refs/heads/main` and `repo:cloud-ai-architect/retailpulse-cx-agent:pull_request`.

Trust policy:
```json
{
  "Effect": "Allow",
  "Principal": { "Federated": "arn:aws:iam::ACCOUNT:oidc-provider/token.actions.githubusercontent.com" },
  "Action": "sts:AssumeRoleWithWebIdentity",
  "Condition": {
    "StringEquals": { "token.actions.githubusercontent.com:aud": "sts.amazonaws.com" },
    "StringLike": {
      "token.actions.githubusercontent.com:sub": [
        "repo:cloud-ai-architect/retailpulse-cx-agent:ref:refs/heads/main",
        "repo:cloud-ai-architect/retailpulse-cx-agent:pull_request"
      ]
    }
  }
}
```

### Consequences

**Positive**

- No secrets in GitHub, ever
- Public repo viewers cannot gain AWS access
- Compromised PR can only `plan`, not `apply`
- CloudTrail shows exact commit for every deploy

**Negative**

- One-time setup complexity (handled by `bootstrap.sh`)
- Trust policy mistakes can over-scope (mitigated by `tflint` and PR review)

## Pros and cons of the options

| Option | Secrets in repo | Rotation | Audit | Trust scope |
|---|---|---|---|---|
| Long-lived keys | ❌ Yes | Manual | Key ID only | All |
| AWS Vault | ✅ None | Auto | Session only | All |
| **GitHub OIDC** | **✅ None** | **Auto** | **Full context** | **Repo + branch** |

## References

- [GitHub OIDC for AWS](https://docs.github.com/en/actions/deployment/security-hardening-your-deployments/configuring-openid-connect-in-amazon-web-services)
- [aws-actions/configure-aws-credentials](https://github.com/aws-actions/configure-aws-credentials)
