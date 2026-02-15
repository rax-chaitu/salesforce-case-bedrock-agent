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
  salesforce_environment = var.salesforce_environment
  create_secret          = var.create_sf_secret
  salesforce_client_id   = var.salesforce_client_id
  salesforce_username    = var.salesforce_username
  salesforce_private_key = var.salesforce_private_key
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

module "lambda_layer" {
  source       = "./modules/lambda_layer"
  project_name = var.project_name
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
  sf_auth_layer_arn      = module.lambda_layer.layer_arn

  # Salesforce JWT (matches Glue pattern)
  salesforce_secret_name  = module.secrets.secret_name
  salesforce_environment  = var.salesforce_environment
}

module "action_group" {
  source = "./modules/action_group"

  project_name           = var.project_name
  sf_auth_layer_arn      = module.lambda_layer.layer_arn
  bedrock_agent_id       = module.bedrock_agent.agent_id
  salesforce_secret_name = module.secrets.secret_name
  salesforce_environment = var.salesforce_environment
  log_retention_days     = var.log_retention_days
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

output "action_group_function_name" {
  description = "Action Group Lambda function name"
  value       = module.action_group.function_name
}

output "sf_auth_layer_arn" {
  description = "Rackspace SF Auth Lambda Layer ARN"
  value       = module.lambda_layer.layer_arn
}

# Disabled - using S3 + AppFlow approach
# output "salesforce_kb_connector_secret_arn" {
#   description = "Salesforce KB Connector Secret ARN (for Bedrock data source)"
#   value       = module.secrets.kb_connector_secret_arn
# }
