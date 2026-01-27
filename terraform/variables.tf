################################################################################
# Variables
################################################################################

variable "project_name" {
  description = "Project name for resource naming (pattern: sf-{object}-{function})"
  type        = string
  default     = "sf-case-analysis"
}

variable "aws_region" {
  description = "AWS region"
  type        = string
  default     = "us-east-1"
}

variable "aws_profile" {
  description = "AWS profile for CLI commands"
  type        = string
  default     = "default"
}

variable "knowledge_base_id" {
  description = "Existing Bedrock Knowledge Base ID"
  type        = string
}

variable "foundation_model" {
  description = "Foundation model ID for Bedrock Agent"
  type        = string
  default     = "amazon.nova-pro-v1:0"
}

variable "lambda_timeout" {
  description = "Lambda timeout in seconds"
  type        = number
  default     = 300
}

variable "log_retention_days" {
  description = "CloudWatch log retention"
  type        = number
  default     = 14
}

variable "agent_session_ttl" {
  description = "Agent session TTL in seconds"
  type        = number
  default     = 1800
}

################################################################################
# EventBridge / Salesforce Variables
################################################################################

variable "salesforce_event_source" {
  description = "Salesforce partner event source (from Event Relay)"
  type        = string
  default     = "" # Set when Event Relay is configured
}

################################################################################
# Salesforce API Variables (JWT Bearer Token Flow)
################################################################################

variable "salesforce_instance_url" {
  description = "Salesforce instance URL (e.g., https://myorg.sandbox.my.salesforce.com)"
  type        = string
  default     = ""
}

variable "salesforce_client_id" {
  description = "Salesforce Connected App Consumer Key"
  type        = string
  default     = ""
}

variable "salesforce_username" {
  description = "Salesforce integration user username for JWT auth"
  type        = string
  default     = ""
}

variable "salesforce_private_key" {
  description = "RSA private key (PEM format) for JWT signing"
  type        = string
  default     = ""
  sensitive   = true
}

################################################################################
# Bedrock KB Salesforce Connector Variables (DISABLED)
# Using S3 + AppFlow approach instead of direct Salesforce connector
# Uncomment if you want to use Bedrock's native Salesforce connector
################################################################################
# variable "salesforce_kb_consumer_key" {
#   description = "Salesforce Connected App Consumer Key for Bedrock KB connector"
#   type        = string
#   default     = ""
# }
# 
# variable "salesforce_kb_consumer_secret" {
#   description = "Salesforce Connected App Consumer Secret for Bedrock KB connector"
#   type        = string
#   default     = ""
#   sensitive   = true
# }
# 
# variable "salesforce_kb_auth_url" {
#   description = "Salesforce OAuth token URL (e.g., https://yourorg.my.salesforce.com/services/oauth2/token)"
#   type        = string
#   default     = ""
# }


################################################################################
# AppFlow + Step Functions KB Sync Variables
################################################################################

variable "appflow_flow_name" {
  description = "Existing AppFlow flow name for Salesforce sync"
  type        = string
  default     = "SYNCCASESWITHS3"
}

variable "kb_data_source_id" {
  description = "Bedrock KB Data Source ID"
  type        = string
  default     = ""
}

variable "sync_schedule_expression" {
  description = "EventBridge schedule expression for KB sync"
  type        = string
  default     = "cron(0 2 * * ? *)"  # Daily at 2am UTC
}

variable "enable_scheduled_sync" {
  description = "Enable scheduled KB sync"
  type        = bool
  default     = false
}
