################################################################################
# KAV Sync Lambda Module
# 
# Daily sync of Salesforce Knowledge Articles to S3 + Bedrock KB
# Triggered by EventBridge schedule
################################################################################

variable "project_name" {
  type = string
}

variable "s3_bucket" {
  type        = string
  description = "S3 bucket for KAV articles"
}

variable "s3_key" {
  type        = string
  default     = "kav_articles.txt"
  description = "S3 key for KAV articles file"
}

variable "knowledge_base_id" {
  type        = string
  description = "Bedrock Knowledge Base ID"
}

variable "data_source_id" {
  type        = string
  description = "Bedrock KB Data Source ID"
}

variable "salesforce_instance_url" {
  type = string
}

variable "salesforce_client_id" {
  type = string
}

variable "salesforce_username" {
  type = string
}

variable "salesforce_private_key_arn" {
  type = string
}

variable "schedule_expression" {
  type        = string
  default     = "cron(0 6 * * ? *)"  # Daily at 6 AM UTC
  description = "EventBridge schedule expression"
}

data "aws_caller_identity" "current" {}
data "aws_region" "current" {}

################################################################################
# Lambda Function
################################################################################

data "archive_file" "lambda_zip" {
  type        = "zip"
  source_dir  = "${path.module}/../../../lambda/kav_sync"
  output_path = "${path.module}/kav_sync.zip"
  excludes    = ["__pycache__", "*.pyc"]
}

# Copy salesforce_client.py from case_processor
resource "null_resource" "copy_shared_code" {
  triggers = {
    always = timestamp()
  }

  provisioner "local-exec" {
    command = "cp ${path.module}/../../../lambda/case_processor/salesforce_client.py ${path.module}/../../../lambda/kav_sync/"
  }
}

resource "aws_lambda_function" "kav_sync" {
  depends_on       = [null_resource.copy_shared_code]
  filename         = data.archive_file.lambda_zip.output_path
  source_code_hash = data.archive_file.lambda_zip.output_base64sha256
  function_name    = "${var.project_name}-kav-sync"
  role             = aws_iam_role.lambda_role.arn
  handler          = "handler.lambda_handler"
  runtime          = "python3.11"
  timeout          = 300
  memory_size      = 256

  environment {
    variables = {
      S3_BUCKET                  = var.s3_bucket
      S3_KEY                     = var.s3_key
      KNOWLEDGE_BASE_ID          = var.knowledge_base_id
      DATA_SOURCE_ID             = var.data_source_id
      SALESFORCE_INSTANCE_URL    = var.salesforce_instance_url
      SALESFORCE_CLIENT_ID       = var.salesforce_client_id
      SALESFORCE_USERNAME        = var.salesforce_username
      SALESFORCE_PRIVATE_KEY_ARN = var.salesforce_private_key_arn
    }
  }

  tags = {
    Project   = var.project_name
    ManagedBy = "Terraform"
  }
}

################################################################################
# IAM Role
################################################################################

resource "aws_iam_role" "lambda_role" {
  name = "${var.project_name}-kav-sync-role"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Action    = "sts:AssumeRole"
      Effect    = "Allow"
      Principal = { Service = "lambda.amazonaws.com" }
    }]
  })

  tags = { Project = var.project_name }
}

resource "aws_iam_role_policy_attachment" "lambda_logs" {
  role       = aws_iam_role.lambda_role.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole"
}

# S3 access
resource "aws_iam_role_policy" "s3_access" {
  name = "${var.project_name}-kav-sync-s3"
  role = aws_iam_role.lambda_role.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect   = "Allow"
      Action   = ["s3:PutObject", "s3:GetObject"]
      Resource = ["arn:aws:s3:::${var.s3_bucket}/*"]
    }]
  })
}

# Bedrock KB access
resource "aws_iam_role_policy" "bedrock_access" {
  name = "${var.project_name}-kav-sync-bedrock"
  role = aws_iam_role.lambda_role.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect   = "Allow"
      Action   = ["bedrock:StartIngestionJob"]
      Resource = ["arn:aws:bedrock:${data.aws_region.current.id}:${data.aws_caller_identity.current.account_id}:knowledge-base/${var.knowledge_base_id}"]
    }]
  })
}

# Secrets Manager access
resource "aws_iam_role_policy" "secrets_access" {
  name = "${var.project_name}-kav-sync-secrets"
  role = aws_iam_role.lambda_role.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect   = "Allow"
        Action   = ["secretsmanager:GetSecretValue"]
        Resource = [var.salesforce_private_key_arn]
      },
      {
        Effect   = "Allow"
        Action   = ["kms:Decrypt"]
        Resource = ["arn:aws:kms:${data.aws_region.current.id}:${data.aws_caller_identity.current.account_id}:key/*"]
      }
    ]
  })
}

################################################################################
# EventBridge Schedule
################################################################################

resource "aws_cloudwatch_event_rule" "daily_sync" {
  name                = "${var.project_name}-kav-sync-schedule"
  description         = "Daily KAV sync to Bedrock KB"
  schedule_expression = var.schedule_expression

  tags = { Project = var.project_name }
}

resource "aws_cloudwatch_event_target" "lambda_target" {
  rule      = aws_cloudwatch_event_rule.daily_sync.name
  target_id = "kav-sync-lambda"
  arn       = aws_lambda_function.kav_sync.arn
}

resource "aws_lambda_permission" "eventbridge" {
  statement_id  = "AllowEventBridge"
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.kav_sync.function_name
  principal     = "events.amazonaws.com"
  source_arn    = aws_cloudwatch_event_rule.daily_sync.arn
}

################################################################################
# Outputs
################################################################################

output "function_name" {
  value = aws_lambda_function.kav_sync.function_name
}

output "function_arn" {
  value = aws_lambda_function.kav_sync.arn
}

output "schedule_rule" {
  value = aws_cloudwatch_event_rule.daily_sync.name
}
