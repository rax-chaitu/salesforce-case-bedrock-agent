################################################################################
# Secrets Manager Module
# 
# Creates Salesforce JWT secret matching Glue job pattern:
# - salesforce-inttest-sandbox-jwt (for sandbox/inttest)
# - salesforce-production-jwt (for production)
#
# Secret Format: { "client_id", "username", "private_key" }
#
# Usage:
# - create_secret = true:  Creates new secret (sandbox5jan27, new accounts)
# - create_secret = false: Uses existing secret (main account with Glue secrets)
################################################################################

variable "project_name" {
  type = string
}

variable "salesforce_environment" {
  description = "inttest or production (matches Glue job pattern)"
  type        = string
  default     = "inttest"
}

variable "create_secret" {
  description = "Create new secret (true) or use existing (false)"
  type        = bool
  default     = true
}

variable "salesforce_client_id" {
  type      = string
  default   = ""
  sensitive = true
}

variable "salesforce_username" {
  type    = string
  default = ""
}

variable "salesforce_private_key" {
  type      = string
  default   = ""
  sensitive = true
}

################################################################################
# Secret Naming (matches Glue job convention)
################################################################################

locals {
  # Glue pattern: salesforce-{environment}-sandbox-jwt or salesforce-production-jwt
  secret_name = var.salesforce_environment == "production" ? "salesforce-production-jwt" : "salesforce-${var.salesforce_environment}-sandbox-jwt"
}

################################################################################
# Create New Secret (for sandbox5jan27 and new accounts)
################################################################################

resource "aws_secretsmanager_secret" "salesforce_jwt" {
  count       = var.create_secret ? 1 : 0
  name        = local.secret_name
  description = "Salesforce JWT credentials for ${var.salesforce_environment} - {client_id, username, private_key}"

  tags = {
    Project     = var.project_name
    Environment = var.salesforce_environment
    ManagedBy   = "Terraform"
  }
}

resource "aws_secretsmanager_secret_version" "salesforce_jwt" {
  count     = var.create_secret && var.salesforce_client_id != "" ? 1 : 0
  secret_id = aws_secretsmanager_secret.salesforce_jwt[0].id
  secret_string = jsonencode({
    client_id   = var.salesforce_client_id
    username    = var.salesforce_username
    private_key = var.salesforce_private_key
  })
}

################################################################################
# Reference Existing Secret (for main account with Glue secrets)
################################################################################

data "aws_secretsmanager_secret" "existing_jwt" {
  count = var.create_secret ? 0 : 1
  name  = local.secret_name
}

################################################################################
# Outputs
################################################################################

output "secret_arn" {
  description = "ARN of Salesforce JWT secret"
  value       = var.create_secret ? aws_secretsmanager_secret.salesforce_jwt[0].arn : data.aws_secretsmanager_secret.existing_jwt[0].arn
}

output "secret_name" {
  description = "Name of Salesforce JWT secret"
  value       = local.secret_name
}
