################################################################################
# Bedrock Agent Module
# 
# Creates Bedrock Agent with Knowledge Base attachment
# Outputs agent IDs for use by Lambda
################################################################################

variable "project_name" {
  type = string
}

variable "knowledge_base_id" {
  type = string
}

variable "foundation_model" {
  type    = string
  default = "amazon.nova-pro-v1:0"
}

variable "agent_session_ttl" {
  type    = number
  default = 1800
}

variable "aws_profile" {
  type    = string
  default = "default"
}

data "aws_caller_identity" "current" {}
data "aws_region" "current" {}

################################################################################
# Bedrock Agent
################################################################################

resource "aws_bedrockagent_agent" "salesforce_agent" {
  agent_name              = var.project_name
  agent_resource_role_arn = aws_iam_role.bedrock_agent_role.arn
  foundation_model        = var.foundation_model

  # Enable memory for cross-session context
  memory_configuration = [{
    enabled_memory_types           = ["SESSION_SUMMARY"]
    storage_days                   = 30
    session_summary_configuration  = [{
      max_recent_sessions = 20
    }]
  }]

  instruction = <<-EOT
    You are a Salesforce Case Analysis Agent. You analyze EXISTING cases and provide resolution suggestions based ONLY on Knowledge Articles (KAV) and similar closed cases from the Knowledge Base.

    CONTEXT: The case has ALREADY been created in Salesforce. Your job is to help support agents resolve it faster.

    CRITICAL RULES:
    1. ALWAYS search the Knowledge Base FIRST
    2. ONLY provide suggestions found in the Knowledge Base
    3. DO NOT use general knowledge or make up solutions
    4. If no relevant KB article or similar case exists, say "No KB match found - requires manual review"

    KB Search Strategy:
    1. If user provides a Case ID (format: 500Pe...), search using BOTH the ID AND description keywords
    2. Extract key terms: error messages, product names, symptoms
    3. Search for closed cases with Status=Closed and Resolution__c populated
    4. Look for Close_Notes__c field for resolution steps
    5. Match by Priority and Category when available

    Response Format (JSON):
    {
      "summary": "Brief issue description",
      "steps": ["Step 1 from KB", "Step 2 from KB"],
      "self_resolvable": true/false,
      "similar_cases": ["Case #12345: Resolution summary"],
      "estimated_resolution": "X hours/days",
      "recommendation": "Self-resolve using KB steps" OR "Requires admin intervention: [reason]" OR "No KB match found - requires manual review"
    }

    IMPORTANT:
    - NEVER suggest "create a case" - the case already exists
    - NEVER provide generic solutions not found in KB
    - If KB has no match, set self_resolvable=false and recommendation="No KB match found - requires manual review"
    - Always return valid JSON. Be concise and actionable.
  EOT

  idle_session_ttl_in_seconds = var.agent_session_ttl

  tags = {
    Project     = var.project_name
    Environment = "production"
    ManagedBy   = "Terraform"
  }
}

################################################################################
# Knowledge Base Association
# NOTE: Set to 0 if KB association already exists in AWS
################################################################################

variable "create_kb_association" {
  type    = bool
  default = true  # Create KB association via Terraform
}

resource "aws_bedrockagent_agent_knowledge_base_association" "kb_association" {
  count                = var.create_kb_association ? 1 : 0
  agent_id             = aws_bedrockagent_agent.salesforce_agent.agent_id
  knowledge_base_id    = var.knowledge_base_id
  description          = "Salesforce closed cases and knowledge articles"
  knowledge_base_state = "ENABLED"
}

################################################################################
# Prepare Agent
################################################################################

resource "null_resource" "prepare_agent" {
  depends_on = [
    aws_bedrockagent_agent.salesforce_agent,
    aws_bedrockagent_agent_knowledge_base_association.kb_association
  ]

  triggers = {
    agent_id    = aws_bedrockagent_agent.salesforce_agent.agent_id
    instruction = md5(aws_bedrockagent_agent.salesforce_agent.instruction)
    kb_id       = var.knowledge_base_id
  }

  provisioner "local-exec" {
    command = <<-EOT
      aws bedrock-agent prepare-agent \
        --agent-id ${aws_bedrockagent_agent.salesforce_agent.agent_id} \
        --region ${data.aws_region.current.id} \
        --profile ${var.aws_profile}
      sleep 15
    EOT
  }
}

################################################################################
# Agent Aliases
# Note: Updating alias without routing_configuration creates new version
################################################################################

resource "aws_bedrockagent_agent_alias" "dev_alias" {
  depends_on       = [null_resource.prepare_agent]
  agent_id         = aws_bedrockagent_agent.salesforce_agent.agent_id
  agent_alias_name = "DEV"
  description      = "Development alias - v${md5(aws_bedrockagent_agent.salesforce_agent.instruction)}"
  tags             = { Environment = "development", Project = var.project_name }

  # No routing_configuration = creates new version from DRAFT and points to it
}

resource "aws_bedrockagent_agent_alias" "prod_alias" {
  agent_id         = aws_bedrockagent_agent.salesforce_agent.agent_id
  agent_alias_name = "PROD"
  description      = "Production alias"
  tags             = { Environment = "production", Project = var.project_name }

  lifecycle {
    ignore_changes = [routing_configuration]
  }
}

################################################################################
# IAM Role for Bedrock Agent
################################################################################

resource "aws_iam_role" "bedrock_agent_role" {
  name = "${var.project_name}-bedrock-agent-role"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect    = "Allow"
      Principal = { Service = "bedrock.amazonaws.com" }
      Action    = "sts:AssumeRole"
      Condition = { StringEquals = { "aws:SourceAccount" = data.aws_caller_identity.current.account_id } }
    }]
  })
  tags = { Project = var.project_name, ManagedBy = "Terraform" }
}

resource "aws_iam_role_policy" "bedrock_agent_model_policy" {
  name = "${var.project_name}-model-policy"
  role = aws_iam_role.bedrock_agent_role.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect = "Allow"
      Action = ["bedrock:InvokeModel", "bedrock:InvokeModelWithResponseStream"]
      Resource = [
        "arn:aws:bedrock:${data.aws_region.current.id}::foundation-model/${var.foundation_model}",
        "arn:aws:bedrock:${data.aws_region.current.id}::foundation-model/amazon.nova-lite-v1:0",
        "arn:aws:bedrock:${data.aws_region.current.id}::foundation-model/amazon.titan-embed-text-v2:0"
      ]
    }]
  })
}

resource "aws_iam_role_policy" "bedrock_agent_kb_policy" {
  name = "${var.project_name}-kb-policy"
  role = aws_iam_role.bedrock_agent_role.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect   = "Allow"
      Action   = ["bedrock:Retrieve", "bedrock:RetrieveAndGenerate"]
      Resource = ["arn:aws:bedrock:${data.aws_region.current.id}:${data.aws_caller_identity.current.account_id}:knowledge-base/${var.knowledge_base_id}"]
    }]
  })
}


