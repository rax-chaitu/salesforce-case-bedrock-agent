################################################################################
# Lambda Module
# 
# Dual-mode Lambda: SQS events (production) + API Gateway (testing)
################################################################################

variable "project_name" {
  type = string
}

variable "lambda_timeout" {
  type    = number
  default = 300
}

variable "log_retention_days" {
  type    = number
  default = 14
}

variable "bedrock_agent_id" {
  type = string
}

variable "bedrock_agent_alias_id" {
  type = string
}

variable "bedrock_agent_arn" {
  type = string
}

variable "knowledge_base_id" {
  type = string
}

variable "sqs_queue_arn" {
  type = string
}

# Salesforce JWT config
variable "salesforce_instance_url" {
  type    = string
  default = ""
}

variable "salesforce_client_id" {
  type    = string
  default = ""
}

variable "salesforce_username" {
  type    = string
  default = ""
}

variable "salesforce_private_key_arn" {
  type    = string
  default = ""
}

data "aws_caller_identity" "current" {}
data "aws_region" "current" {}

################################################################################
# Lambda Function
################################################################################

# Package dependencies
resource "null_resource" "pip_install" {
  triggers = {
    requirements = filemd5("${path.module}/../../../lambda/case_processor/requirements.txt")
  }

  provisioner "local-exec" {
    command = <<-EOT
      cd ${path.module}/../../../lambda/case_processor
      rm -rf package
      mkdir -p package
      pip3 install -r requirements.txt -t package/ --platform manylinux2014_x86_64 --only-binary=:all:
    EOT
  }
}

data "archive_file" "lambda_zip" {
  depends_on  = [null_resource.pip_install]
  type        = "zip"
  source_dir  = "${path.module}/../../../lambda/case_processor"
  output_path = "${path.module}/lambda_function.zip"
  excludes    = ["__pycache__", "*.pyc", ".pytest_cache"]
}

resource "aws_lambda_function" "api" {
  filename         = data.archive_file.lambda_zip.output_path
  source_code_hash = data.archive_file.lambda_zip.output_base64sha256
  function_name    = "${var.project_name}-api"
  role             = aws_iam_role.lambda_role.arn
  handler          = "handler.lambda_handler"
  runtime          = "python3.11"
  timeout          = var.lambda_timeout
  memory_size      = 512

  # Limit concurrency to avoid Bedrock throttling (10 parallel = ~10 cases/15s)
  reserved_concurrent_executions = 10

  environment {
    variables = {
      BEDROCK_AGENT_ID            = var.bedrock_agent_id
      BEDROCK_AGENT_ALIAS_ID      = var.bedrock_agent_alias_id
      BEDROCK_KNOWLEDGE_BASE_ID   = var.knowledge_base_id
      SALESFORCE_INSTANCE_URL     = var.salesforce_instance_url
      SALESFORCE_CLIENT_ID        = var.salesforce_client_id
      SALESFORCE_USERNAME         = var.salesforce_username
      SALESFORCE_PRIVATE_KEY_ARN  = var.salesforce_private_key_arn
    }
  }

  depends_on = [
    aws_iam_role_policy_attachment.lambda_logs,
    aws_cloudwatch_log_group.lambda_logs,
  ]

  tags = {
    Project   = var.project_name
    ManagedBy = "Terraform"
  }

  # TODO: TEMPORARY - Remove after fixing pip install for Lambda packaging
  # Added because manual Lambda deploy was needed to fix dependency issues.
  # Once packaging is stable, remove this block to let Terraform manage Lambda code.
  lifecycle {
    ignore_changes = [filename, source_code_hash]
  }
}

################################################################################
# SQS Trigger
################################################################################

resource "aws_lambda_event_source_mapping" "sqs_trigger" {
  event_source_arn                   = var.sqs_queue_arn
  function_name                      = aws_lambda_function.api.arn
  batch_size                         = 1
  enabled                            = true
  function_response_types            = ["ReportBatchItemFailures"]
}

################################################################################
# Lambda IAM Role
################################################################################

resource "aws_iam_role" "lambda_role" {
  name = "${var.project_name}-lambda-role"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Action    = "sts:AssumeRole"
      Effect    = "Allow"
      Principal = { Service = "lambda.amazonaws.com" }
    }]
  })

  tags = { Project = var.project_name, ManagedBy = "Terraform" }
}

resource "aws_iam_role_policy_attachment" "lambda_logs" {
  role       = aws_iam_role.lambda_role.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole"
}

# Bedrock Agent access
resource "aws_iam_role_policy" "lambda_bedrock_agent" {
  name = "${var.project_name}-bedrock-agent"
  role = aws_iam_role.lambda_role.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect = "Allow"
      Action = ["bedrock:InvokeAgent"]
      Resource = [
        var.bedrock_agent_arn,
        "${var.bedrock_agent_arn}/*",
        "arn:aws:bedrock:${data.aws_region.current.id}:${data.aws_caller_identity.current.account_id}:agent-alias/*"
      ]
    }]
  })
}

# Knowledge Base access
resource "aws_iam_role_policy" "lambda_bedrock_kb" {
  name = "${var.project_name}-bedrock-kb"
  role = aws_iam_role.lambda_role.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect   = "Allow"
      Action   = ["bedrock:Retrieve", "bedrock:RetrieveAndGenerate"]
      Resource = ["arn:aws:bedrock:${data.aws_region.current.id}:${data.aws_caller_identity.current.account_id}:knowledge-base/${var.knowledge_base_id}"]
    }]
  })
}

# SQS access
resource "aws_iam_role_policy" "lambda_sqs" {
  name = "${var.project_name}-sqs"
  role = aws_iam_role.lambda_role.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect   = "Allow"
      Action   = ["sqs:ReceiveMessage", "sqs:DeleteMessage", "sqs:GetQueueAttributes"]
      Resource = [var.sqs_queue_arn]
    }]
  })
}

# Secrets Manager access
resource "aws_iam_role_policy" "lambda_secrets" {
  name = "${var.project_name}-secrets"
  role = aws_iam_role.lambda_role.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect   = "Allow"
        Action   = ["secretsmanager:GetSecretValue"]
        Resource = ["arn:aws:secretsmanager:${data.aws_region.current.id}:${data.aws_caller_identity.current.account_id}:secret:${var.project_name}/*"]
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
# CloudWatch Log Group
################################################################################

resource "aws_cloudwatch_log_group" "lambda_logs" {
  name              = "/aws/lambda/${var.project_name}-api"
  retention_in_days = var.log_retention_days
  tags              = { Project = var.project_name, ManagedBy = "Terraform" }
}

################################################################################
# Outputs
################################################################################

output "function_name" {
  value = aws_lambda_function.api.function_name
}

output "function_arn" {
  value = aws_lambda_function.api.arn
}

output "invoke_arn" {
  value = aws_lambda_function.api.invoke_arn
}

output "role_arn" {
  value = aws_iam_role.lambda_role.arn
}
