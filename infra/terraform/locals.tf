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

  github_sub_main = "repo:${var.github_org}/${var.github_repo}:ref:refs/heads/main"
  github_sub_pr   = "repo:${var.github_org}/${var.github_repo}:pull_request"
  github_oidc_arn = "arn:aws:iam::${local.account_id}:oidc-provider/token.actions.githubusercontent.com"
  github_aud      = "sts.amazonaws.com"

  vector_index_name = "${var.project_name}-chunks-v1"
}

data "aws_caller_identity" "current" {}

