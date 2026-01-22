################################################################################
# Variables
################################################################################

variable "project_name" {
  description = "Project name for resource naming"
  type        = string
  default     = "salesforceagent"
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
