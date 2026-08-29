terraform {
  required_version = ">= 1.9.0"
  required_providers {
    aws = { source = "hashicorp/aws", version = "~> 5.50" }
  }
}

variable "arn" {
  type = string
}
# Use data source to read existing OIDC provider (created once at account bootstrap)
data "aws_iam_openid_connect_provider" "github" {
  arn = var.arn
}

output "provider_arn" {
  value = data.aws_iam_openid_connect_provider.github.arn
}