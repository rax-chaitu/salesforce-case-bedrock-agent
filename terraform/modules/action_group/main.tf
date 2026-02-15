################################################################################
# Action Group Module
#
# Lambda + Bedrock Agent Action Group for searching similar SF cases.
# Uses shared rackspace_sf_auth layer for authentication.
################################################################################

variable "project_name" {
  type = string
}

variable "sf_auth_layer_arn" {
  description = "ARN of the rackspace-sf-auth Lambda Layer"
  type        = string
}

variable "bedrock_agent_id" {
  type = string
}

variable "salesforce_secret_name" {
  type    = string
  default = ""
}

variable "salesforce_environment" {
  type    = string
  default = "inttest"
}

variable "log_retention_days" {
  type    = number
  default = 14
}

data "aws_caller_identity" "current" {}
data "aws_region" "current" {}

################################################################################
# Lambda Function
################################################################################

data "archive_file" "action_group_zip" {
  type        = "zip"
  source_file = "${path.module}/../../../lambda/action_group/handler.py"
  output_path = "${path.module}/action_group.zip"
}

resource "aws_lambda_function" "action_group" {
  filename         = data.archive_file.action_group_zip.output_path
  source_code_hash = data.archive_file.action_group_zip.output_base64sha256
  function_name    = "${var.project_name}-action-group"
  role             = aws_iam_role.action_group_role.arn
  handler          = "handler.lambda_handler"
  runtime          = "python3.11"
  timeout          = 60
  memory_size      = 256
  layers           = [var.sf_auth_layer_arn]

  environment {
    variables = {
      SALESFORCE_SECRET_NAME = var.salesforce_secret_name
      SALESFORCE_ENVIRONMENT = var.salesforce_environment
    }
  }

  depends_on = [aws_cloudwatch_log_group.action_group_logs]

  tags = { Project = var.project_name, ManagedBy = "Terraform" }
}

################################################################################
# Bedrock Agent Action Group
################################################################################

resource "aws_bedrockagent_agent_action_group" "similar_cases" {
  action_group_name          = "SearchSimilarCases"
  agent_id                   = var.bedrock_agent_id
  agent_version              = "DRAFT"
  description                = "Search Salesforce for similar closed cases by keywords and support reason"
  skip_resource_in_use_check = true

  action_group_executor {
    lambda = aws_lambda_function.action_group.arn
  }

  api_schema {
    payload = file("${path.module}/../../../lambda/action_group/openapi_schema.json")
  }
}

# Allow Bedrock to invoke the action group Lambda
resource "aws_lambda_permission" "bedrock_invoke" {
  statement_id  = "AllowBedrockInvoke"
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.action_group.function_name
  principal     = "bedrock.amazonaws.com"
  source_arn    = "arn:aws:bedrock:${data.aws_region.current.id}:${data.aws_caller_identity.current.account_id}:agent/${var.bedrock_agent_id}"
}

################################################################################
# IAM Role
################################################################################

resource "aws_iam_role" "action_group_role" {
  name = "${var.project_name}-action-group-role"

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

resource "aws_iam_role_policy_attachment" "action_group_logs" {
  role       = aws_iam_role.action_group_role.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole"
}

resource "aws_iam_role_policy" "action_group_secrets" {
  name = "${var.project_name}-action-group-secrets"
  role = aws_iam_role.action_group_role.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect   = "Allow"
      Action   = ["secretsmanager:GetSecretValue"]
      Resource = ["arn:aws:secretsmanager:${data.aws_region.current.id}:${data.aws_caller_identity.current.account_id}:secret:salesforce-*"]
    }]
  })
}

################################################################################
# CloudWatch Logs
################################################################################

resource "aws_cloudwatch_log_group" "action_group_logs" {
  name              = "/aws/lambda/${var.project_name}-action-group"
  retention_in_days = var.log_retention_days
  tags              = { Project = var.project_name, ManagedBy = "Terraform" }
}

################################################################################
# Outputs
################################################################################

output "function_name" {
  value = aws_lambda_function.action_group.function_name
}

output "function_arn" {
  value = aws_lambda_function.action_group.arn
}
