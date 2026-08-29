# Changelog

All notable changes to this project are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added

- Initial project scaffold
- README, LICENSE (Apache 2.0), SECURITY.md, CONTRIBUTING.md
- Pre-commit hooks (gitleaks, ruff, mypy, terraform fmt/lint/sec, markdownlint)
- GitHub Actions workflows (CI, plan, apply)
- OPA Rego policies for CX guardrails
- Terraform modules for catalog, orders, KB, lambdas, step-function, API gateway, CloudFront, IAM
- CrewAI-based Sales, Support, Returns agents
- Browser-based price comparison tool (browser-use)
- Voice agent integration (LiveKit or Polly)
- Synthetic retail data generator
- 9 Architecture Decision Records
- Architecture docs (HLD, LLD, component, dataflow, deployment, security, cost)
- Runbooks (deploy, rollback, incident response, cost investigation)
- API reference
- Data model with ER diagram

### Security

- GitHub OIDC for AWS authentication (no long-lived credentials)
- Gitleaks pre-commit and CI secret-scanning
- Branch protection on `main` (required reviews, no force-push)
- Dependabot weekly updates
- All resources tagged `Project=retailpulse` for IAM scoping

[Unreleased]: <https://github.com/cloud-ai-architect/retailpulse-cx-agent/compare/main...HEAD>
