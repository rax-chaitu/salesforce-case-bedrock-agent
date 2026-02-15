################################################################################
# EventBridge Schedule - Trigger KB Sync State Machine
################################################################################

resource "aws_cloudwatch_event_rule" "kb_sync_schedule" {
  count = var.enable_scheduled_sync ? 1 : 0

  name                = "${var.project_name}-kb-sync-schedule"
  description         = "Trigger KB sync state machine on schedule"
  schedule_expression = var.sync_schedule_expression

  tags = {
    Project   = var.project_name
    ManagedBy = "Terraform"
  }
}

resource "aws_cloudwatch_event_target" "kb_sync_sfn" {
  count = var.enable_scheduled_sync ? 1 : 0

  rule      = aws_cloudwatch_event_rule.kb_sync_schedule[0].name
  target_id = "kb-sync-state-machine"
  arn       = aws_sfn_state_machine.kb_sync.arn
  role_arn  = aws_iam_role.eventbridge_sfn_role[0].arn
}

resource "aws_iam_role" "eventbridge_sfn_role" {
  count = var.enable_scheduled_sync ? 1 : 0

  name = "${var.project_name}-eventbridge-sfn-role"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Action    = "sts:AssumeRole"
      Effect    = "Allow"
      Principal = { Service = "events.amazonaws.com" }
    }]
  })

  tags = {
    Project   = var.project_name
    ManagedBy = "Terraform"
  }
}

resource "aws_iam_role_policy" "eventbridge_sfn" {
  count = var.enable_scheduled_sync ? 1 : 0

  name = "${var.project_name}-eventbridge-sfn"
  role = aws_iam_role.eventbridge_sfn_role[0].id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect   = "Allow"
      Action   = "states:StartExecution"
      Resource = aws_sfn_state_machine.kb_sync.arn
    }]
  })
}

################################################################################
# Outputs
################################################################################

output "kb_sync_schedule_rule_arn" {
  description = "EventBridge schedule rule ARN"
  value       = var.enable_scheduled_sync ? aws_cloudwatch_event_rule.kb_sync_schedule[0].arn : null
}
