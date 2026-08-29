###############################################################################
# Locals
###############################################################################

locals {
  account_id  = data.aws_caller_identity.current.account_id
  name_prefix = "${var.project_name}-${var.environment}"

  common_tags = {
    Project     = var.project_name
    Environment = var.environment
    Owner       = var.owner
    CostCenter  = var.cost_center
    ManagedBy   = "terraform"
  }

  # Both spellings of the OIDC subject.
  #
  # GitHub does not send the plain "repo:ORG/REPO:..." form documented in
  # most examples. The token this organisation issues carries numeric ids:
  #
  #   repo:cloud-ai-architect@258468489/retailpulse-cx-agent@1349157484:ref:refs/heads/main
  #
  # A trust policy with only the plain form fails with "Not authorized to
  # perform sts:AssumeRoleWithWebIdentity", which gives no hint that the
  # subject is the problem -- the id form was only visible in CloudTrail.
  #
  # The @* variants match the id form without pinning ids that change if the
  # repository is transferred or renamed. The plain forms are kept so the
  # policy still works wherever GitHub sends that instead.
  github_sub_main = "repo:${var.github_org}@*/${var.github_repo}@*:ref:refs/heads/main"
  github_sub_pr   = "repo:${var.github_org}@*/${var.github_repo}@*:pull_request"

  github_sub_main_plain = "repo:${var.github_org}/${var.github_repo}:ref:refs/heads/main"
  github_sub_pr_plain   = "repo:${var.github_org}/${var.github_repo}:pull_request"

  github_subs = [
    local.github_sub_main,
    local.github_sub_pr,
    local.github_sub_main_plain,
    local.github_sub_pr_plain,
  ]
  github_oidc_arn = "arn:aws:iam::${local.account_id}:oidc-provider/token.actions.githubusercontent.com"
  github_aud      = "sts.amazonaws.com"

  vector_index_name = "${var.project_name}-chunks-v1"
}

data "aws_caller_identity" "current" {}

