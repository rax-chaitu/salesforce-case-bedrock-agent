################################################################################
# Step Functions - AppFlow + Bedrock KB Sync Orchestration
#
# Flow: StartAppFlow → Poll → StartKBSync → Poll → Done
#
# PREREQUISITES:
#   1. Create AppFlow flow manually in AWS Console first:
#      - Source: Salesforce (requires Salesforce Connected App + OAuth)
#      - Destination: S3 bucket used by Bedrock KB
#      - Trigger: OnDemand
#   2. Create Bedrock Knowledge Base with S3 data source
#   3. Set variables: appflow_flow_name, knowledge_base_id, kb_data_source_id
#
# AppFlow cannot be fully managed by Terraform due to OAuth connection
# requirements - the Salesforce connector must be created via Console.
################################################################################

# Using data.aws_caller_identity.current from locals.tf

################################################################################
# Step Functions State Machine
################################################################################

resource "aws_sfn_state_machine" "kb_sync" {
  name     = "${var.project_name}-kb-sync"
  role_arn = aws_iam_role.sfn_role.arn

  definition = jsonencode({
    Comment = "Salesforce to Bedrock KB Sync Pipeline"
    StartAt = "StartAppFlowExecution"
    States = {
      StartAppFlowExecution = {
        Type     = "Task"
        Resource = "arn:aws:states:::aws-sdk:appflow:startFlow"
        Parameters = {
          FlowName = var.appflow_flow_name
        }
        ResultPath = "$.appFlowResult"
        Next       = "WaitForAppFlow"
      }

      WaitForAppFlow = {
        Type    = "Wait"
        Seconds = 30
        Next    = "CheckAppFlowStatus"
      }

      CheckAppFlowStatus = {
        Type     = "Task"
        Resource = "arn:aws:states:::aws-sdk:appflow:describeFlowExecutionRecords"
        Parameters = {
          FlowName   = var.appflow_flow_name
          MaxResults = 1
        }
        ResultPath = "$.flowStatus"
        Next       = "IsAppFlowComplete"
      }

      IsAppFlowComplete = {
        Type = "Choice"
        Choices = [
          {
            Variable     = "$.flowStatus.FlowExecutions[0].ExecutionStatus"
            StringEquals = "Successful"
            Next         = "StartBedrockKBSync"
          },
          {
            Variable     = "$.flowStatus.FlowExecutions[0].ExecutionStatus"
            StringEquals = "Error"
            Next         = "AppFlowFailed"
          }
        ]
        Default = "WaitForAppFlow"
      }

      StartBedrockKBSync = {
        Type     = "Task"
        Resource = "arn:aws:states:::aws-sdk:bedrockagent:startIngestionJob"
        Parameters = {
          KnowledgeBaseId = var.knowledge_base_id
          DataSourceId    = var.kb_data_source_id
        }
        ResultPath = "$.ingestionJob"
        Next       = "WaitForKBSync"
      }

      WaitForKBSync = {
        Type    = "Wait"
        Seconds = 60
        Next    = "CheckKBSyncStatus"
      }

      CheckKBSyncStatus = {
        Type     = "Task"
        Resource = "arn:aws:states:::aws-sdk:bedrockagent:getIngestionJob"
        Parameters = {
          KnowledgeBaseId    = var.knowledge_base_id
          DataSourceId       = var.kb_data_source_id
          "IngestionJobId.$" = "$.ingestionJob.IngestionJob.IngestionJobId"
        }
        ResultPath = "$.syncStatus"
        Next       = "IsKBSyncComplete"
      }

      IsKBSyncComplete = {
        Type = "Choice"
        Choices = [
          {
            Variable     = "$.syncStatus.IngestionJob.Status"
            StringEquals = "COMPLETE"
            Next         = "SyncSuccess"
          },
          {
            Variable     = "$.syncStatus.IngestionJob.Status"
            StringEquals = "FAILED"
            Next         = "KBSyncFailed"
          }
        ]
        Default = "WaitForKBSync"
      }

      SyncSuccess = {
        Type = "Succeed"
      }

      AppFlowFailed = {
        Type  = "Fail"
        Error = "AppFlowExecutionFailed"
        Cause = "AppFlow failed to sync Salesforce data"
      }

      KBSyncFailed = {
        Type  = "Fail"
        Error = "BedrockKBSyncFailed"
        Cause = "Bedrock Knowledge Base sync failed"
      }
    }
  })

  logging_configuration {
    log_destination        = "${aws_cloudwatch_log_group.sfn_logs.arn}:*"
    include_execution_data = true
    level                  = "ERROR"
  }

  tags = {
    Project   = var.project_name
    ManagedBy = "Terraform"
  }
}

################################################################################
# CloudWatch Log Group for Step Functions
################################################################################

resource "aws_cloudwatch_log_group" "sfn_logs" {
  name              = "/aws/vendedlogs/states/${var.project_name}-kb-sync"
  retention_in_days = var.log_retention_days

  tags = {
    Project   = var.project_name
    ManagedBy = "Terraform"
  }
}

################################################################################
# IAM Role for Step Functions
################################################################################

resource "aws_iam_role" "sfn_role" {
  name = "${var.project_name}-sfn-kb-sync-role"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Action    = "sts:AssumeRole"
      Effect    = "Allow"
      Principal = { Service = "states.amazonaws.com" }
    }]
  })

  tags = {
    Project   = var.project_name
    ManagedBy = "Terraform"
  }
}

resource "aws_iam_role_policy" "sfn_appflow" {
  name = "${var.project_name}-sfn-appflow"
  role = aws_iam_role.sfn_role.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Sid    = "AppFlowPermissions"
        Effect = "Allow"
        Action = [
          "appflow:StartFlow",
          "appflow:DescribeFlow",
          "appflow:DescribeFlowExecutionRecords"
        ]
        Resource = "arn:aws:appflow:${var.aws_region}:${data.aws_caller_identity.current.account_id}:flow/${var.appflow_flow_name}"
      }
    ]
  })
}

resource "aws_iam_role_policy" "sfn_bedrock" {
  name = "${var.project_name}-sfn-bedrock"
  role = aws_iam_role.sfn_role.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Sid    = "BedrockKBPermissions"
        Effect = "Allow"
        Action = [
          "bedrock:StartIngestionJob",
          "bedrock:GetIngestionJob"
        ]
        Resource = "arn:aws:bedrock:${var.aws_region}:${data.aws_caller_identity.current.account_id}:knowledge-base/${var.knowledge_base_id}"
      }
    ]
  })
}

resource "aws_iam_role_policy" "sfn_logs" {
  name = "${var.project_name}-sfn-logs"
  role = aws_iam_role.sfn_role.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Sid    = "CloudWatchLogs"
        Effect = "Allow"
        Action = [
          "logs:CreateLogDelivery",
          "logs:GetLogDelivery",
          "logs:UpdateLogDelivery",
          "logs:DeleteLogDelivery",
          "logs:ListLogDeliveries",
          "logs:PutResourcePolicy",
          "logs:DescribeResourcePolicies",
          "logs:DescribeLogGroups"
        ]
        Resource = "*"
      }
    ]
  })
}

################################################################################
# Outputs
################################################################################

output "sfn_state_machine_arn" {
  description = "Step Functions state machine ARN"
  value       = aws_sfn_state_machine.kb_sync.arn
}

output "sfn_state_machine_name" {
  description = "Step Functions state machine name"
  value       = aws_sfn_state_machine.kb_sync.name
}
