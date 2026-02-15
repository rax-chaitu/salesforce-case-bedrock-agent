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

# Salesforce JWT config (matches Glue pattern)
variable "salesforce_secret_name" {
  description = "Secret name: salesforce-{env}-sandbox-jwt or salesforce-production-jwt"
  type        = string
  default     = ""
}

variable "salesforce_environment" {
  description = "inttest or production (determines auth URL)"
  type        = string
  default     = "inttest"
}

variable "sf_auth_layer_arn" {
  description = "ARN of the rackspace-sf-auth Lambda Layer"
  type        = string
}

data "aws_caller_identity" "current" {}
data "aws_region" "current" {}

################################################################################
# Lambda Function
################################################################################

# Package dependencies and Python files
resource "null_resource" "pip_install" {
  triggers = {
    requirements = filemd5("${path.module}/../../../lambda/case_processor/requirements.txt")
    handler      = filemd5("${path.module}/../../../lambda/case_processor/handler.py")
    salesforce   = filemd5("${path.module}/../../../lambda/case_processor/salesforce_client.py")
    bedrock      = filemd5("${path.module}/../../../lambda/case_processor/bedrock_client.py")
  }

  provisioner "local-exec" {
    command = <<-EOT
      cd ${path.module}/../../../lambda/case_processor
      rm -rf package lambda_package
      mkdir -p lambda_package
      pip3 install -r requirements.txt -t lambda_package/ --platform manylinux2014_x86_64 --python-version 3.11 --only-binary=:all: 2>/dev/null || true
      cp *.py lambda_package/
    EOT
  }
}

data "archive_file" "lambda_zip" {
  depends_on  = [null_resource.pip_install]
  type        = "zip"
  source_dir  = "${path.module}/../../../lambda/case_processor/lambda_package"
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
  layers           = [var.sf_auth_layer_arn]

  # Increased concurrency for better throughput (was 2, bottleneck at 480 cases/hr)
  # Set to 20 for ~10x capacity. Monitor Bedrock throttling and adjust as needed.
  reserved_concurrent_executions = 20

  tracing_config {
    mode = "Active"
  }

  environment {
    variables = {
      BEDROCK_AGENT_ID          = var.bedrock_agent_id
      BEDROCK_AGENT_ALIAS_ID    = var.bedrock_agent_alias_id
      BEDROCK_KNOWLEDGE_BASE_ID = var.knowledge_base_id
      SALESFORCE_SECRET_NAME    = var.salesforce_secret_name
      SALESFORCE_ENVIRONMENT    = var.salesforce_environment
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

resource "aws_iam_role_policy_attachment" "lambda_xray" {
  role       = aws_iam_role.lambda_role.name
  policy_arn = "arn:aws:iam::aws:policy/AWSXRayDaemonWriteAccess"
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

# Secrets Manager access (salesforce-*-jwt secrets)
# NOTE: Using AWS-managed KMS key (default), no explicit kms:Decrypt needed
resource "aws_iam_role_policy" "lambda_secrets" {
  name = "${var.project_name}-secrets"
  role = aws_iam_role.lambda_role.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect   = "Allow"
        Action   = ["secretsmanager:GetSecretValue"]
        Resource = [
          # Glue-style secrets: salesforce-inttest-sandbox-jwt, salesforce-production-jwt
          "arn:aws:secretsmanager:${data.aws_region.current.id}:${data.aws_caller_identity.current.account_id}:secret:salesforce-*"
        ]
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
