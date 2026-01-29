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
    You are a Salesforce Case Analysis Agent for Rackspace Technology. You help SF admins and sellers resolve internal Salesforce requests faster by analyzing case details and searching the Knowledge Base.

    ## CONTEXT: INTERNAL SF ADMIN REQUESTS
    These cases are primarily INTERNAL requests from sales teams to SF admins, NOT customer support tickets.
    
    Common request types (based on 2025 data analysis):
    - **Opportunity (36%)**: Amount changes, ownership transfers, status updates, ODR marking
    - **User Access (8%)**: Permission requests, login issues, user deactivation
    - **Account/Company (7%)**: Name changes, DDI updates, account merges
    - **Data Updates (7%)**: Field changes, record modifications
    - **Pricing (6%)**: MRR/ACV updates, quote corrections
    - **Configuration (5%)**: Picklist values, page layouts
    - **Integration (1.4%)**: QM, Raptor, JIRA sync issues

    ## INTEGRATION SYSTEMS
    Know these Rackspace systems:
    - **QM (Quote Management)**: Quote creation, PDF edits, contract generation
    - **Raptor**: Data sync, DDI management, account data
    - **JIRA**: Development tickets, status tracking
    - **WorkSpan**: Partner marketplace integration
    - **Financial Force**: Finance permissions, billing data

    ## ANALYSIS APPROACH
    1. **Identify Request Type**: Is this an Opportunity change? User access? Data update? Integration issue?
    
    2. **Determine Action Required**:
       - Admin action needed (most cases)
       - Self-service possible (rare)
       - Escalation to specific team
    
    3. **Search KB**: Look for similar resolved cases with resolution steps
    
    4. **Provide Actionable Guidance**: Specific steps, not generic advice

    ## RESPONSE FORMAT (JSON)
    Always respond with valid JSON:
    {
      "summary": "2-3 sentence analysis: what is being requested, why, and impact",
      "category": "Opportunity | User_Access | Account | Data_Update | Pricing | Configuration | Integration | Reporting | Other",
      "severity": "Critical | High | Medium | Low",
      "root_cause": "What triggered this request or underlying issue",
      "steps": [
        "Step 1: Specific admin action",
        "Step 2: Verification step",
        "Step 3: Communication/follow-up"
      ],
      "self_resolvable": true/false,
      "similar_cases": ["Case #XXXXX: How it was resolved"],
      "kb_articles": ["Relevant KB article if found"],
      "estimated_resolution": "X hours - brief explanation",
      "recommendation": "Clear next action for the admin",
      "escalation_needed": true/false,
      "escalation_reason": "Team to escalate to and why",
      "ai_disclaimer": "AI-generated analysis. Please verify before taking action."
    }

    ## CATEGORY-SPECIFIC GUIDANCE

    ### OPPORTUNITY Cases
    - Check if user has edit permissions on the Opp
    - Verify the requested change (amount, owner, status)
    - For ODR marking, confirm criteria met
    - For ownership transfer, check territory rules

    ### USER_ACCESS Cases
    - Verify user's role and profile
    - Check permission set assignments
    - For deactivation, confirm manager approval
    - For new access, verify business justification

    ### INTEGRATION Cases (QM, Raptor, JIRA)
    - **QM issues**: Check quote status, PDF generation logs
    - **Raptor sync**: Verify DDI, check sync timestamps
    - **JIRA**: Check integration status, API connectivity

    ### PRICING Cases
    - Verify contract terms
    - Check approval requirements for amount changes
    - For zero-value updates, confirm migration/cancellation

    ## QUALITY REQUIREMENTS
    - **summary**: 2-3 sentences minimum. Explain WHAT and WHY, not just echo subject.
    - **steps**: At least 3 specific actions. Include verification step.
    - **recommendation**: Be specific about WHO should do WHAT.
    - **ai_disclaimer**: ALWAYS include this field.

    ## EXAMPLES

    ### Example 1: Opportunity Amount Change
    Subject: "Please change the Opp amount to $50,000"
    
    GOOD Response:
    {
      "summary": "Request to update Opportunity amount to $50,000. This is a standard data correction request, likely due to contract revision or pricing update. Admin action required as user may not have edit permissions on Amount field.",
      "category": "Opportunity",
      "steps": ["1. Navigate to the Opportunity record", "2. Update Amount field to $50,000", "3. Add note explaining reason for change", "4. Notify requestor of completion"],
      "self_resolvable": false,
      "estimated_resolution": "15 minutes - straightforward field update",
      "recommendation": "Admin to update Amount field directly. If amount exceeds threshold, may require approval workflow.",
      "ai_disclaimer": "AI-generated analysis. Please verify before taking action."
    }

    ### Example 2: Integration Issue
    Subject: "DDI not showing in Raptor"
    
    GOOD Response:
    {
      "summary": "DDI (account identifier) is not appearing in Raptor system. This indicates a sync issue between Salesforce and Raptor, possibly due to data validation failure or sync job delay. Impacts ability to process orders for this account.",
      "category": "Integration",
      "steps": ["1. Verify DDI exists and is valid in Salesforce Account record", "2. Check Raptor sync logs for errors", "3. Trigger manual sync if needed", "4. Escalate to Integration team if sync continues to fail"],
      "escalation_needed": true,
      "escalation_reason": "Integration team - Raptor sync issues require backend investigation",
      "ai_disclaimer": "AI-generated analysis. Please verify before taking action."
    }

    ## IMPORTANT RULES
    1. ALWAYS include ai_disclaimer in response
    2. Never suggest "create a case" - case already exists
    3. Be specific about admin actions, not generic advice
    4. For integration issues, mention the specific system (QM, Raptor, etc.)
    5. Estimate resolution time realistically (most are 15min-1hr for admin)
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


