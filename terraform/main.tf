################################################################################
# Salesforce Agent - Event-Driven Architecture
# 
# Modular structure:
# - Bedrock Agent with Knowledge Base
# - EventBridge → SQS → Lambda (production)
# - API Gateway → Lambda (testing)
################################################################################

terraform {
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = ">= 5.0"
    }
  }
  required_version = ">= 1.2"
}

provider "aws" {
  region = var.aws_region
  # Uses AWS_PROFILE or AWS_ACCESS_KEY_ID/AWS_SECRET_ACCESS_KEY from environment
}

data "aws_region" "current" {}

################################################################################
# Modules
################################################################################

module "bedrock_agent" {
  source = "./modules/bedrock_agent"

  project_name      = var.project_name
  knowledge_base_id = var.knowledge_base_id
  foundation_model  = var.foundation_model
  agent_session_ttl = var.agent_session_ttl
  aws_profile       = var.aws_profile
}

module "secrets" {
  source = "./modules/secrets"

  project_name           = var.project_name
  salesforce_private_key = var.salesforce_private_key

  # Bedrock KB Salesforce Connector credentials (DISABLED)
  # Using S3 + AppFlow approach instead
  # salesforce_kb_consumer_key    = var.salesforce_kb_consumer_key
  # salesforce_kb_consumer_secret = var.salesforce_kb_consumer_secret
  # salesforce_kb_auth_url        = var.salesforce_kb_auth_url
}

module "sqs" {
  source = "./modules/sqs"

  project_name       = var.project_name
  visibility_timeout = var.lambda_timeout + 30 # Buffer for Lambda
}

module "eventbridge" {
  source = "./modules/eventbridge"

  project_name            = var.project_name
  sqs_queue_arn           = module.sqs.queue_arn
  salesforce_event_source = var.salesforce_event_source
}

module "lambda" {
  source = "./modules/lambda"

  project_name           = var.project_name
  lambda_timeout         = var.lambda_timeout
  log_retention_days     = var.log_retention_days
  bedrock_agent_id       = module.bedrock_agent.agent_id
  bedrock_agent_alias_id = module.bedrock_agent.dev_alias_id
  bedrock_agent_arn      = module.bedrock_agent.agent_arn
  knowledge_base_id      = var.knowledge_base_id
  sqs_queue_arn          = module.sqs.queue_arn

  # Salesforce JWT config
  salesforce_instance_url    = var.salesforce_instance_url
  salesforce_client_id       = var.salesforce_client_id
  salesforce_username        = var.salesforce_username
  salesforce_private_key_arn = module.secrets.private_key_arn
}

################################################################################
# Outputs
################################################################################

output "api_gateway_url" {
  description = "API Gateway endpoint URL"
  value       = aws_api_gateway_stage.api.invoke_url
}

output "bedrock_agent_id" {
  description = "Bedrock Agent ID"
  value       = module.bedrock_agent.agent_id
}

output "bedrock_agent_dev_alias_id" {
  description = "Bedrock Agent DEV Alias ID"
  value       = module.bedrock_agent.dev_alias_id
}

output "bedrock_agent_prod_alias_id" {
  description = "Bedrock Agent PROD Alias ID"
  value       = module.bedrock_agent.prod_alias_id
}

output "lambda_function_name" {
  description = "Lambda function name"
  value       = module.lambda.function_name
}

output "sqs_queue_url" {
  description = "SQS Queue URL"
  value       = module.sqs.queue_url
}

output "sqs_dlq_url" {
  description = "SQS Dead Letter Queue URL"
  value       = module.sqs.dlq_url
}

output "knowledge_base_id" {
  description = "Knowledge Base ID"
  value       = var.knowledge_base_id
}

# Disabled - using S3 + AppFlow approach
# output "salesforce_kb_connector_secret_arn" {
#   description = "Salesforce KB Connector Secret ARN (for Bedrock data source)"
#   value       = module.secrets.kb_connector_secret_arn
# }
