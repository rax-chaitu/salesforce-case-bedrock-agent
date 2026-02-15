################################################################################
# EventBridge Module
# 
# Routes Salesforce Platform Events to SQS
# Partner event source: aws.partner/salesforce.com/...
################################################################################

variable "project_name" {
  type = string
}

variable "sqs_queue_arn" {
  type        = string
  description = "Target SQS queue ARN"
}

variable "salesforce_event_source" {
  type        = string
  description = "Salesforce partner event source name"
  default     = "" # Set via tfvars when Event Relay is configured
}

data "aws_caller_identity" "current" {}
data "aws_region" "current" {}

################################################################################
# Partner Event Source Association
# Associates the Salesforce partner event source with an event bus
################################################################################

resource "aws_cloudwatch_event_bus" "partner" {
  count              = var.salesforce_event_source != "" ? 1 : 0
  name               = var.salesforce_event_source
  event_source_name  = var.salesforce_event_source
}

################################################################################
# Event Bus (use default for partner events)
################################################################################

resource "aws_cloudwatch_event_rule" "case_created" {
  depends_on     = [aws_cloudwatch_event_bus.partner]
  name           = "${var.project_name}-event-rule"
  description    = "Route Salesforce Case creation events to SQS"
  event_bus_name = var.salesforce_event_source

  # Pattern matches Integration_Event__e with Object_Name__c = Case
  event_pattern = jsonencode({
    source = [var.salesforce_event_source != "" ? var.salesforce_event_source : "aws.partner/salesforce.com"]
    detail = {
      payload = {
        Object_Name__c = ["Case"]
        Type__c        = ["CREATE"]
      }
    }
  })

  tags = {
    Project   = var.project_name
    ManagedBy = "Terraform"
  }
}

################################################################################
# EventBridge Target - SQS Queue
################################################################################

resource "aws_cloudwatch_event_target" "sqs_target" {
  rule           = aws_cloudwatch_event_rule.case_created.name
  event_bus_name = var.salesforce_event_source
  target_id      = "case-analysis-queue"
  arn            = var.sqs_queue_arn

  # Retry policy
  retry_policy {
    maximum_event_age_in_seconds = 3600
    maximum_retry_attempts       = 3
  }

  # Dead letter queue handled by SQS itself
}

################################################################################
# Outputs
################################################################################

output "rule_arn" {
  value = aws_cloudwatch_event_rule.case_created.arn
}

output "rule_name" {
  value = aws_cloudwatch_event_rule.case_created.name
}
