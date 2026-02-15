################################################################################
# SQS Module
# 
# Case analysis queue with DLQ for failed messages
# 300s visibility timeout for Lambda processing
################################################################################

variable "project_name" {
  type = string
}

variable "visibility_timeout" {
  type    = number
  default = 300 # 5 minutes - matches Lambda timeout
}

variable "message_retention" {
  type    = number
  default = 1209600 # 14 days
}

################################################################################
# Main Queue
################################################################################

resource "aws_sqs_queue" "case_analysis" {
  name                       = "${var.project_name}-queue"
  visibility_timeout_seconds = var.visibility_timeout
  message_retention_seconds  = var.message_retention
  receive_wait_time_seconds  = 20 # Long polling
  sqs_managed_sse_enabled    = true

  redrive_policy = jsonencode({
    deadLetterTargetArn = aws_sqs_queue.dlq.arn
    maxReceiveCount     = 3
  })

  tags = {
    Project   = var.project_name
    ManagedBy = "Terraform"
  }
}

################################################################################
# Dead Letter Queue
################################################################################

resource "aws_sqs_queue" "dlq" {
  name                      = "${var.project_name}-queue-dlq"
  message_retention_seconds = var.message_retention

  tags = {
    Project   = var.project_name
    ManagedBy = "Terraform"
  }
}

################################################################################
# Queue Policy - Allow EventBridge to send messages
################################################################################

resource "aws_sqs_queue_policy" "eventbridge_policy" {
  queue_url = aws_sqs_queue.case_analysis.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Sid       = "AllowEventBridge"
      Effect    = "Allow"
      Principal = { Service = "events.amazonaws.com" }
      Action    = "sqs:SendMessage"
      Resource  = aws_sqs_queue.case_analysis.arn
    }]
  })
}

################################################################################
# Outputs
################################################################################

output "queue_arn" {
  value = aws_sqs_queue.case_analysis.arn
}

output "queue_url" {
  value = aws_sqs_queue.case_analysis.url
}

output "queue_name" {
  value = aws_sqs_queue.case_analysis.name
}

output "dlq_arn" {
  value = aws_sqs_queue.dlq.arn
}

output "dlq_url" {
  value = aws_sqs_queue.dlq.url
}

################################################################################
# CloudWatch Alarm for DLQ - Alert when messages fail
################################################################################

resource "aws_cloudwatch_metric_alarm" "dlq_messages" {
  alarm_name          = "${var.project_name}-dlq-has-messages"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = 1
  metric_name         = "ApproximateNumberOfMessagesVisible"
  namespace           = "AWS/SQS"
  period              = 300
  statistic           = "Sum"
  threshold           = 0
  alarm_description   = "Cases failing to process - check DLQ"
  treat_missing_data  = "notBreaching"

  dimensions = {
    QueueName = aws_sqs_queue.dlq.name
  }

  tags = {
    Project   = var.project_name
    ManagedBy = "Terraform"
  }
}

output "dlq_alarm_arn" {
  value = aws_cloudwatch_metric_alarm.dlq_messages.arn
}
