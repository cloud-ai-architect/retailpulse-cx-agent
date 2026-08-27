# Security Policy

## Supported versions

| Version | Supported          |
| ------- | ------------------ |
| 0.1.x   | :white_check_mark: |
| < 0.1   | :x:                |

## Reporting a vulnerability

**Please do NOT file a public GitHub issue for security vulnerabilities.**

Report privately via GitHub Security Advisories: https://github.com/cloud-ai-architect/retailpulse-cx-agent/security/advisories/new

Please include:
- Description of the vulnerability and its impact
- Steps to reproduce or a proof-of-concept
- Affected component(s) and version(s)
- Any known mitigations

## Response timeline

| Stage | Target time |
|---|---|
| Acknowledge report | 48 hours |
| Triage and severity assessment | 7 days |
| Patch release (Critical/High) | 14 days |
| Patch release (Medium/Low) | 30 days |
| Public disclosure | After patch is released + 7 days |

## Security model summary

This project follows these security principles by design:

1. **No long-lived AWS credentials** — GitHub Actions assumes IAM role via OIDC with `sub` claim scoped to specific repo and branch.
2. **No secrets in code** — Pre-commit `gitleaks` and CI secret-scan block any credential patterns. Use AWS Secrets Manager or SSM Parameter Store for runtime secrets.
3. **Least-privilege IAM** — Every IAM role is scoped to `Project=retailpulse` resource tag, no wildcard resource ARNs.
4. **Encryption everywhere** — S3 (AES-256), DynamoDB (AWS-managed KMS), S3 Vectors (AES-256), in transit (TLS 1.2+).
5. **Public bucket restricted** — Only the KB UI bucket is public, and only for static assets; no list/read of raw data from public.
6. **No public network exposure** of internal services — API Gateway endpoints have IAM auth + rate limiting.
7. **Branch protection** on `main` — Required reviews, no force-push, signed-off commits.
8. **Dependency scanning** via Dependabot weekly updates.

For the full threat model and trust boundaries, see [`docs/architecture/06-security-model.md`](docs/architecture/06-security-model.md).

## Known limitations

- **Public KB UI bucket** exposes static HTML/JS files. The API Gateway endpoint should be treated as semi-public — rate limiting and input validation are essential.
- **Voice channel** uses LiveKit (or Polly) — these services receive call audio. Review their BAA/compliance posture for your jurisdiction.
- **Browser-use tool** has the agent controlling a real browser. Sandboxing is critical to prevent unintended actions.
- **GitHub OIDC trust** depends on GitHub's token issuance. Compromise of GitHub Actions could lead to AWS access within the scope of the trusted role.

## Recognition

We appreciate responsible disclosure. Reporters of valid vulnerabilities will be credited (with permission) in the release notes.
