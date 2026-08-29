variable "project_name" {
  type = string
}
variable "name_prefix" {
  type = string
}
variable "github_subs" {
  description = "Every OIDC subject allowed to assume the deploy role."
  type        = list(string)
}
variable "github_aud" {
  type = string
}
variable "buckets" {
  type = map(string)
}
variable "tables" {
  type = map(string)
}
variable "lambdas" {
  type = map(string)
}
variable "oidc_provider_arn" {
  type = string
}
variable "common_tags" {
  type = map(string)
  default = {
  }
}

# Used by the deploy policy to name the Terraform state bucket and lock
# table, which are per-environment.
variable "environment" {
  type = string
}
