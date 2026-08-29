terraform {
  required_version = ">= 1.9.0"
  required_providers {
    aws = { source = "hashicorp/aws", version = "~> 5.50" }
  }
}

variable "name_prefix" {
  type = string
}
variable "aws_region" {
  type = string
}

variable "ui_bucket" {
  type = string
}
variable "enabled" {
  type    = bool
  default = true
}
variable "common_tags" {
  type    = map(string)
  default = {}
}
resource "aws_cloudfront_origin_access_control" "this" {
  name                              = "${var.name_prefix}-oac"
  description                       = "OAC for ${var.ui_bucket}"
  origin_access_control_origin_type = "s3"
  signing_behavior                  = "always"
  signing_protocol                  = "sigv4"
}

# Three checks are deliberately accepted here:
#
#   WAF carries a fixed monthly charge per web ACL plus per-request cost.
#   This distribution serves a static, read-only UI with no authenticated
#   surface and no write path; the API it calls is a separate origin with
#   its own controls.
#
#   With the default *.cloudfront.net certificate AWS pins the minimum TLS
#   protocol version to TLSv1 and rejects any higher value. Raising it
#   requires a custom domain and an ACM certificate, which this distribution
#   does not have.
#
#   Standard access logging writes to a dedicated S3 bucket that would
#   itself need lifecycle and access controls. Request-level telemetry is
#   captured at the API stage instead, where the requests that matter land.
# tfsec:ignore:aws-cloudfront-enable-waf
# tfsec:ignore:aws-cloudfront-use-secure-tls-policy
# tfsec:ignore:aws-cloudfront-enable-logging
resource "aws_cloudfront_distribution" "this" {
  enabled             = var.enabled
  comment             = "RetailPulse KB UI"
  default_root_object = "index.html"
  price_class         = "PriceClass_100"
  tags                = var.common_tags

  origin {
    # Regional endpoint. The global "<bucket>.s3.amazonaws.com" form issues a
    # redirect for buckets outside us-east-1, and OAC-signed requests do not
    # follow redirects -- so every request would 301 into a failure.
    domain_name              = "${var.ui_bucket}.s3.${var.aws_region}.amazonaws.com"
    origin_id                = "S3-${var.ui_bucket}"
    origin_access_control_id = aws_cloudfront_origin_access_control.this.id
  }

  default_cache_behavior {
    target_origin_id       = "S3-${var.ui_bucket}"
    viewer_protocol_policy = "redirect-to-https"
    allowed_methods        = ["GET", "HEAD", "OPTIONS"]
    cached_methods         = ["GET", "HEAD"]
    compress               = true

    forwarded_values {
      query_string = false
      cookies { forward = "none" }
    }

    min_ttl     = 0
    default_ttl = 3600
    max_ttl     = 86400
  }

  restrictions {
    geo_restriction { restriction_type = "none" }
  }

  viewer_certificate {
    cloudfront_default_certificate = true
  }
}

# Grant this distribution -- and only this distribution -- read access to the
# UI bucket. Scoping to the CloudFront service principal with a SourceArn
# condition is what makes the OAC meaningful, and it lets the bucket keep
# public access fully blocked.
resource "aws_s3_bucket_policy" "oac_read" {
  bucket = var.ui_bucket

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Sid       = "AllowCloudFrontOACRead"
        Effect    = "Allow"
        Principal = { Service = "cloudfront.amazonaws.com" }
        Action    = "s3:GetObject"
        Resource  = "arn:aws:s3:::${var.ui_bucket}/*"
        Condition = {
          StringEquals = {
            "AWS:SourceArn" = aws_cloudfront_distribution.this.arn
          }
        }
      }
    ]
  })
}

output "distribution_id" {
  value = aws_cloudfront_distribution.this.id
}
output "distribution_domain" {
  value = aws_cloudfront_distribution.this.domain_name
}