################################################################################
# Secrets Manager Module
# 
# Stores Salesforce credentials for:
# 1. JWT Bearer Token flow (Lambda → Salesforce API)
# 2. OAuth2 Client Credentials flow (Bedrock KB → Salesforce connector)
################################################################################

variable "project_name" {
  type = string
}

variable "salesforce_private_key" {
  type      = string
  default   = ""
  sensitive = true
}

################################################################################
# Bedrock KB Salesforce Connector credentials (DISABLED)
# Using S3 + AppFlow approach instead of direct Salesforce connector
# Uncomment if you want to use Bedrock's native Salesforce connector
################################################################################
# variable "salesforce_kb_consumer_key" {
#   type        = string
#   default     = ""
#   description = "Salesforce Connected App Consumer Key for Bedrock KB connector"
# }
# 
# variable "salesforce_kb_consumer_secret" {
#   type        = string
#   default     = ""
#   sensitive   = true
#   description = "Salesforce Connected App Consumer Secret for Bedrock KB connector"
# }
# 
# variable "salesforce_kb_auth_url" {
#   type        = string
#   default     = ""
#   description = "Salesforce OAuth token URL (e.g., https://yourorg.my.salesforce.com/services/oauth2/token)"
# }

################################################################################
# Salesforce Private Key (for JWT Bearer Token flow - Lambda)
################################################################################

resource "aws_secretsmanager_secret" "salesforce_private_key" {
  name        = "${var.project_name}/salesforce/jwt-private-key"
  description = "Salesforce JWT Bearer Token private key"

  tags = {
    Project   = var.project_name
    ManagedBy = "Terraform"
  }
}

resource "aws_secretsmanager_secret_version" "salesforce_private_key" {
  count         = var.salesforce_private_key != "" ? 1 : 0
  secret_id     = aws_secretsmanager_secret.salesforce_private_key.id
  secret_string = var.salesforce_private_key
}

################################################################################
# Salesforce KB Connector Secret (DISABLED)
# Using S3 + AppFlow approach instead of direct Salesforce connector
# Uncomment if you want to use Bedrock's native Salesforce connector
################################################################################
# resource "aws_secretsmanager_secret" "salesforce_kb_connector" {
#   count       = var.salesforce_kb_consumer_key != "" ? 1 : 0
#   name        = "${var.project_name}/salesforce/kb-connector-credentials"
#   description = "Salesforce OAuth2 Client Credentials for Bedrock KB Salesforce connector"
#
#   tags = {
#     Project   = var.project_name
#     ManagedBy = "Terraform"
#     Purpose   = "Bedrock Knowledge Base Salesforce Data Source"
#   }
# }
#
# resource "aws_secretsmanager_secret_version" "salesforce_kb_connector" {
#   count     = var.salesforce_kb_consumer_key != "" ? 1 : 0
#   secret_id = aws_secretsmanager_secret.salesforce_kb_connector[0].id
#   secret_string = jsonencode({
#     consumerKey       = var.salesforce_kb_consumer_key
#     consumerSecret    = var.salesforce_kb_consumer_secret
#     authenticationUrl = var.salesforce_kb_auth_url
#   })
# }

################################################################################
# Outputs
################################################################################

output "private_key_arn" {
  value = aws_secretsmanager_secret.salesforce_private_key.arn
}

output "private_key_name" {
  value = aws_secretsmanager_secret.salesforce_private_key.name
}

# Disabled - using S3 + AppFlow approach
# output "kb_connector_secret_arn" {
#   value       = length(aws_secretsmanager_secret.salesforce_kb_connector) > 0 ? aws_secretsmanager_secret.salesforce_kb_connector[0].arn : ""
#   description = "ARN of Salesforce KB connector secret for Bedrock data source"
# }

output "kb_connector_secret_arn" {
  value       = ""
  description = "Disabled - using S3 + AppFlow approach instead of Salesforce connector"
}
