################################################################################
# Secrets Manager Module
# 
# Stores Salesforce JWT private key for authentication
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
# Salesforce Private Key (for JWT Bearer Token flow)
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
# Outputs
################################################################################

output "private_key_arn" {
  value = aws_secretsmanager_secret.salesforce_private_key.arn
}

output "private_key_name" {
  value = aws_secretsmanager_secret.salesforce_private_key.name
}
