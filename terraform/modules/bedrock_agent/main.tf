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
# Guardrails
# Blocks PII in responses, restricts to Salesforce-related topics only.
# Prevents agent from answering off-topic questions.
################################################################################

resource "aws_bedrock_guardrail" "agent_guardrail" {
  name                      = "${var.project_name}-guardrail"
  blocked_input_messaging   = "I can only help with Salesforce case analysis. Please provide a case for analysis."
  blocked_outputs_messaging = "I cannot provide that information. Please contact your Salesforce admin."
  description               = "Guardrail for SF Case Analysis Agent - PII filtering and topic restriction"

  content_policy_config {
    filters_config {
      type            = "HATE"
      input_strength  = "HIGH"
      output_strength = "HIGH"
    }
    filters_config {
      type            = "INSULTS"
      input_strength  = "HIGH"
      output_strength = "HIGH"
    }
    filters_config {
      type            = "SEXUAL"
      input_strength  = "HIGH"
      output_strength = "HIGH"
    }
    filters_config {
      type            = "VIOLENCE"
      input_strength  = "HIGH"
      output_strength = "HIGH"
    }
    filters_config {
      type            = "MISCONDUCT"
      input_strength  = "HIGH"
      output_strength = "HIGH"
    }
    filters_config {
      type            = "PROMPT_ATTACK"
      input_strength  = "HIGH"
      output_strength = "NONE"
    }
  }

  sensitive_information_policy_config {
    pii_entities_config {
      type   = "US_SOCIAL_SECURITY_NUMBER"
      action = "ANONYMIZE"
    }
    pii_entities_config {
      type   = "CREDIT_DEBIT_CARD_NUMBER"
      action = "ANONYMIZE"
    }
  }

  topic_policy_config {
    topics_config {
      name       = "Off-Topic"
      definition = "Questions completely unrelated to Salesforce, CRM, IT support, or Rackspace business processes. For example: personal advice, creative writing, general knowledge trivia, coding homework."
      type       = "DENY"
      examples   = ["What is the weather today", "Write me a poem", "Help me with my homework", "Tell me a joke"]
    }
  }
}

################################################################################
# Bedrock Agent
################################################################################

resource "aws_bedrockagent_agent" "salesforce_agent" {
  agent_name              = var.project_name
  agent_resource_role_arn = aws_iam_role.bedrock_agent_role.arn
  foundation_model        = var.foundation_model
  guardrail_configuration {
    guardrail_identifier = aws_bedrock_guardrail.agent_guardrail.guardrail_id
    guardrail_version    = "DRAFT"
  }

  # Memory disabled - each case analysis is a single-shot Lambda invocation
  # with no follow-up conversation, so session memory adds latency with no benefit.
  # Uncomment below to re-enable if agent becomes conversational in the future.
  # memory_configuration = [{
  #   enabled_memory_types           = ["SESSION_SUMMARY"]
  #   storage_days                   = 30
  #   session_summary_configuration  = [{
  #     max_recent_sessions = 20
  #   }]
  # }]

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
    
    2. **ALWAYS Search Knowledge Base FIRST**: Before forming any recommendation, you MUST search the Knowledge Base for relevant articles and resolved cases. Use the case subject, description keywords, and category as search terms.
    
    3. **Use KB Content as Primary Source for Response**:
       - If the KB returns relevant articles or resolved cases, your response MUST be based on that KB content.
       - Include specific processes, tool names, step-by-step instructions, and policies found in KB articles.
       - Do NOT give generic advice when the KB has specific guidance. For example, if the KB describes a specific tool or process for handling a request type, reference that tool/process by name and include the steps from the article.
       - Populate "kb_articles" with the exact SOP document name from the KB retrieval results (e.g., "Opportunity Creation SOP", "Revegy Access SOP", "Terminations SOP"). Use the real document title, never fabricate names.
       - If the KB article says users can self-service something, set self_resolvable: true and explain how.
    
    4. **Only Fall Back to General Knowledge if KB Has No Relevant Results**:
       - If KB search returns no matches, state that no specific KB article was found.
       - Provide best-effort guidance based on your instructions.
    
    5. **Provide Actionable Guidance**: Specific steps from KB articles, not generic advice. Include tool names, process names, and approval workflows mentioned in KB content.

    ## RESPONSE FORMAT (JSON)
    CRITICAL: Your response must be ONLY a valid JSON object. No text before or after. No markdown code blocks. No explanations outside the JSON. Start with { and end with }.
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
      "similar_cases": [],
      "kb_articles": ["Exact SOP document name from KB, e.g. Revegy Access SOP, Opportunity Creation SOP"],
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
    - **steps**: At least 3 specific actions. If KB articles describe a process, use those exact steps. Include verification step.
    - **recommendation**: Be specific about WHO should do WHAT. If the KB describes a self-service tool or process, recommend that instead of defaulting to "Admin action required".
    - **kb_articles**: List the exact SOP document names from KB retrieval results that informed your response. Example: ["Opportunity Creation SOP", "SOW Approval SOP"]. If none found, return empty array.
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

    ## USER ACCESS LIMITATIONS
    CRITICAL: Most case requestors are regular Salesforce users with LIMITED permissions.
    
    **Users CANNOT do (Admin-only actions):**
    - Add/remove fields on page layouts
    - Create/modify picklist values
    - Change field-level security or permissions
    - Create/deactivate users
    - Modify profiles or permission sets
    - Change validation rules or workflows
    - Edit record types or page layouts
    - Modify sharing rules or OWD settings
    - Access Setup menu or metadata
    
    **Users CAN do (Self-service possible):**
    - Edit records they own or have access to
    - Run reports they have access to
    - Update their own user preferences
    - Create records (if object permissions allow)
    - View dashboards shared with them
    
    **When suggesting actions:**
    - IMPORTANT: If a KB article describes a self-service process (e.g., user can submit a request, use a tool, click a button), then self_resolvable = true and guide the user through those steps. KB content OVERRIDES the defaults below.
    - For metadata/admin changes with no KB self-service article: Say "Contact SF Admin to..." or "Admin action required: ..."
    - For data changes: Check if user likely has edit access based on ownership
    - Never suggest users modify page layouts, picklists, or permissions
    - Only default to self_resolvable: false when NO KB article describes a self-service path

    ## IMPORTANT RULES
    1. ALWAYS include ai_disclaimer in response
    2. Never suggest "create a case" - case already exists
    3. Be specific about admin actions, not generic advice
    4. For integration issues, mention the specific system (QM, Raptor, etc.)
    5. Estimate resolution time realistically (most are 15min-1hr for admin)
    6. ALWAYS search the Knowledge Base before responding. Your response quality depends on incorporating KB content.
    7. If the KB describes a self-service process or tool for the request type, do NOT default to "Admin action required". Instead, guide the user to the self-service option with the specific steps from the KB article.
    8. Include specific names of tools, processes, and policies from KB articles in your steps and recommendation.
    6. Never suggest users do admin-only actions (see USER ACCESS LIMITATIONS)
    7. Default to self_resolvable: false unless user clearly owns the record AND has edit access
    8. NEVER fabricate or hallucinate case numbers or KB articles. If no similar cases are found in the Knowledge Base, return empty arrays: "similar_cases": [], "kb_articles": []. Only include real case numbers and articles retrieved from the KB.
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

  # Must wait for prod_alias to finish versioning before KB association can prepare agent
  depends_on = [aws_bedrockagent_agent_alias.prod_alias]
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
    model       = var.foundation_model
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
#
# DEV ALIAS: Auto-updates on every terraform apply when instructions or model
#   change. Description hash triggers alias update, which creates a new numbered
#   version from DRAFT and points the alias to it. Safe for development/testing.
#
# PROD ALIAS: Manually controlled. lifecycle.ignore_changes prevents terraform
#   from changing the routing. To promote to PROD:
#   1. Test thoroughly on DEV alias
#   2. Note the DEV alias version number (check AWS console or CLI)
#   3. Manually update PROD alias:
#      aws bedrock-agent update-agent-alias \
#        --agent-id YFGXELIXEF --agent-alias-id <PROD_ALIAS_ID> \
#        --agent-alias-name PROD --region us-east-1
#   This creates a new version from current DRAFT and points PROD to it.
#   NEVER auto-promote to PROD — always test on DEV first.
################################################################################

resource "aws_bedrockagent_agent_alias" "dev_alias" {
  depends_on       = [null_resource.prepare_agent]
  agent_id         = aws_bedrockagent_agent.salesforce_agent.agent_id
  agent_alias_name = "DEV"
  description      = "Development alias - v${md5("${aws_bedrockagent_agent.salesforce_agent.instruction}${var.foundation_model}")}"
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
        "arn:aws:bedrock:${data.aws_region.current.id}:${data.aws_caller_identity.current.account_id}:inference-profile/${var.foundation_model}",
        "arn:aws:bedrock:*::foundation-model/anthropic.claude-*",
        "arn:aws:bedrock:*::foundation-model/amazon.nova-*",
        "arn:aws:bedrock:*::foundation-model/amazon.titan-embed-text-*"
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

resource "aws_iam_role_policy" "bedrock_agent_guardrail_policy" {
  name = "${var.project_name}-guardrail-policy"
  role = aws_iam_role.bedrock_agent_role.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect   = "Allow"
      Action   = ["bedrock:ApplyGuardrail"]
      Resource = [aws_bedrock_guardrail.agent_guardrail.guardrail_arn]
    }]
  })
}


