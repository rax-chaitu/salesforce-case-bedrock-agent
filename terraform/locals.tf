locals {
  # Computed values
  event_source_pattern = "arn:aws:events:${var.aws_region}:${data.aws_caller_identity.current.account_id}:event-source/aws.partner/salesforce.com/${var.salesforce_event_source}"
  
  # Resource naming
  resource_prefix = var.project_name
  
  # Common tags
  common_tags = {
    Project     = var.project_name
    ManagedBy   = "Terraform"
  }
}

data "aws_caller_identity" "current" {}
