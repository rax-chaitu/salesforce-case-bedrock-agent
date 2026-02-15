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

  # Input: MEDIUM for filters that false-positive on case language (frozen, blocked, kill process, etc.)
  # Output: MEDIUM for same reason — agent summarizes case content
  # HATE + SEXUAL stay HIGH on both sides — no business reason to lower
  content_policy_config {
    filters_config {
      type            = "HATE"
      input_strength  = "HIGH"
      output_strength = "HIGH"
    }
    filters_config {
      type            = "INSULTS"
      input_strength  = "MEDIUM"
      output_strength = "MEDIUM"
    }
    filters_config {
      type            = "SEXUAL"
      input_strength  = "HIGH"
      output_strength = "HIGH"
    }
    filters_config {
      type            = "VIOLENCE"
      input_strength  = "MEDIUM"
      output_strength = "MEDIUM"
    }
    filters_config {
      type            = "MISCONDUCT"
      input_strength  = "MEDIUM"
      output_strength = "MEDIUM"
    }
    filters_config {
      type            = "PROMPT_ATTACK"
      input_strength  = "LOW"
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
  description             = "AI case analysis agent - analyzes Salesforce cases using KB, similar cases, and knowledge articles to provide resolution guidance"
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

    ## SEARCH KEYWORD GUIDANCE
    When searching KB and similar cases, use SPECIFIC keywords from the case, not generic ones:
    - Opportunity team requests → search "opportunity team member", "client partner"
    - Tool access → search the specific tool name: "Revegy", "ZoomInfo", "Sales Navigator"
    - Amount changes → search "opportunity amount", "quote"
    - Account issues → search "account", "company", "DDI", "GAR"
    - Integration → search the specific system: "QM", "Raptor", "JIRA", "WorkSpan"
    Only include KB articles in your response that are RELEVANT to the case topic. Do NOT include unrelated articles.

    ## ANALYSIS APPROACH
    1. **Identify Request Type**: Is this an Opportunity change? User access? Data update? Integration issue?
    
    2. **ALWAYS Search the SOP Knowledge Base FIRST (automatic vector search)**: Before forming any recommendation, the Knowledge Base will be searched automatically using semantic matching. It contains 58 detailed SOP documents with step-by-step admin procedures. This is your PRIMARY source for resolution steps. The KB search results will appear as retrieved references — READ them carefully and extract the actual steps, field names, navigation paths, and processes described in the SOP content.
    
    3. **MANDATORY - Search for Similar Cases**: You MUST call the searchSimilarCases action EVERY TIME, no exceptions. Extract 2-3 keywords from the case subject and pass them along with the support_reason if available. The returned data includes case comments, emails, and chatter posts showing how similar cases were actually resolved — this real-world resolution context is critical and cannot be replaced by KB articles alone. You MUST include ALL returned case numbers in your similar_cases array — never omit any.
    
    4. **MANDATORY - Search Salesforce Knowledge Articles**: You MUST call the searchKnowledgeArticles action EVERY TIME, no exceptions. This searches Salesforce KnowledgeArticleVersion records (user-facing self-service guides, separate from the SOP Knowledge Base). Use broad keywords related to the case topic. Include any relevant article titles in your kb_articles array.
    
    5. **Query Additional Salesforce Data If Needed**: If the case references a specific Opportunity, Account, or other Salesforce record and you need more context, use the querySalesforce action to run a SOQL SELECT query. For example: SELECT Name, StageName, Amount FROM Opportunity WHERE Id = 'xxx'.
    
    6. **Build Your Response from SOP KB Content**:
       - Your response MUST be based on the SOP Knowledge Base retrieval results. These contain the actual admin procedures.
       - CRITICAL: Extract and include the ACTUAL steps, processes, and instructions FROM the SOP content in your "steps" array. Do NOT just say "Follow the KB article" or "Refer to the SOP" — that is useless. The admin needs the actual steps written out.
       - BAD: "Step 1: Follow the process in KB article 'Submit an Opportunity Team Member Request'"
       - GOOD: "Step 1: Navigate to the Opportunity record. Step 2: Click the Opportunity Team related list. Step 3: Click Add Team Member. Step 4: Select the user and set role to Client Partner. Step 5: Save."
       - Include specific tool names, URLs, field names, and click paths from the SOP content.
       - Populate "kb_articles" with the exact SOP document name from the KB retrieval results. Use the real document title, never fabricate names.
       - If the SOP or SF Knowledge Article says users can self-service something, set self_resolvable: true and explain how.
    
    7. **Only Fall Back to General Knowledge if KB Has No Relevant Results**:
       - If KB search returns no matches, state that no specific KB article was found.
       - Provide best-effort guidance based on your instructions.
    
    8. **Provide Actionable Guidance**: Your steps must be specific enough that an admin can execute them WITHOUT reading the KB article. Include navigation paths, field names, button names, and verification steps.

    ## RESPONSE FORMAT (JSON)
    CRITICAL: Your response must be ONLY a valid JSON object. No text before or after. No markdown code blocks. No explanations outside the JSON. Start with { and end with }.
    {
      "summary": "2-3 sentence analysis: what is being requested, why, and impact",
      "category": "Opportunity | User_Access | Account | Data_Update | Pricing | Configuration | Integration | Reporting | Other",
      "severity": "Critical | High | Medium | Low",
      "root_cause": "What triggered this request or underlying issue",
      "steps": [
        "Step 1: Specific admin action with navigation path",
        "Step 2: Verification step with field names",
        "Step 3: Communication/follow-up"
      ],
      "self_resolvable": true/false,
      "similar_cases": ["case_number_1", "case_number_2", "case_number_3"],
      "kb_articles": ["Exact SOP document name from KB"],
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
    - **steps**: At least 3 specific actions with navigation paths and field names. If KB articles describe a process, extract those exact steps. Always include a verification step.
    - **recommendation**: Be specific about WHO should do WHAT. If the KB describes a self-service tool or process, recommend that instead of defaulting to "Admin action required". NEVER say "Follow the steps above" or "See steps below" — the recommendation field displays separately from steps in Salesforce. Instead, summarize the action directly, e.g. "Admin to add John Smith as Client Partner on the Opportunity Team for Opp 4601706."
    - **similar_cases**: Include ALL case numbers returned by searchSimilarCases. Never return an empty array if the action returned results.
    - **kb_articles**: List the exact SOP document names from KB retrieval results. If none found, return empty array.

    ## EXAMPLES

    ### Example 1: Opportunity Amount Change
    Subject: "Please adjust opp amount to reflect contract - $56,620.73 MRR"
    Support_Reason__c: "Opportunity - Amount Change"
    
    GOOD Response:
    {
      "summary": "Request to update Opportunity amount to $56,620.73 MRR to match the contract value. The Amount field is controlled by different fields depending on the Opportunity Record Type and Type. Admin needs to determine the correct field to update based on the opp configuration.",
      "category": "Opportunity",
      "steps": ["1. Navigate to the Opportunity record and check the Record Type (US Cloud/INTL Cloud vs US Dedicated/INTL Dedicated) and Type field", "2. If Type is NOT Professional Services: The amount is controlled by QM quote lines — the sales rep should update the amount directly in QM, not in Salesforce", "3. If Type IS Professional Services: Update the ProServ Fees (One-Time) field with the contract total — the ProServ Fees (MRR) will auto-calculate as 10% of that amount", "4. For Dedicated opps (non-ProServ): Check Hosting Fee, VM Fees, and Setup Fee fields — these are controlled by QM quote lines", "5. Verify the Amount field reflects $56,620.73 MRR after the update", "6. Add a case comment confirming the change and notify the requestor"],
      "self_resolvable": false,
      "similar_cases": ["00144984", "00144944", "00144827", "00144760", "00144971"],
      "kb_articles": ["Amount - Opportunities SOP", "Optimizer+ Amount Guidelines Compact Version SOP"],
      "estimated_resolution": "15 minutes - field update after determining correct field",
      "recommendation": "Check the Opportunity Record Type and Type first. If amount is QM-controlled, redirect the sales rep to update in QM. If ProServ, admin can update ProServ Fees (One-Time) directly.",
      "ai_disclaimer": "AI-generated analysis. Please verify before taking action."
    }

    ### Example 2: Debook Request
    Subject: "Please de-book Opp"
    Support_Reason__c: "Opportunity - Debook"
    
    GOOD Response:
    {
      "summary": "Request to debook an Opportunity. A debook occurs when a customer downgrades services or did not achieve the stated contract amount. Can be partial (portion of contract) or full (entire contract). CVP team must be notified to update billing.",
      "category": "Opportunity",
      "steps": ["1. Verify the debook reason: customer went offline within 90 days, non-payment, contract not CVP verified in 100 days, or phased deployment not properly identified", "2. Contact CVP team (primary: Beth Scheidt in Customer Success, or Valerie Mauro/Business Manager) to update billing", "3. Process the debook in Salesforce — debooks are applied against the month the deal was originally booked", "4. If partial debook: update the Opportunity amount to reflect the reduced contract value", "5. If full debook: update the Opportunity stage accordingly", "6. Notify the requestor and CSM of the completed debook"],
      "similar_cases": ["00145006", "00145007", "00145002", "00145001", "00145005"],
      "kb_articles": ["Debook SOP"],
      "escalation_needed": true,
      "escalation_reason": "CVP team must be notified for billing updates when processing debooks",
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
    9. Never suggest users do admin-only actions (see USER ACCESS LIMITATIONS)
    10. Default to self_resolvable: false unless user clearly owns the record AND has edit access
    11. NEVER fabricate or hallucinate case numbers or KB articles. If no similar cases are found, return empty arrays: "similar_cases": [], "kb_articles": []. Only include real case numbers and articles retrieved from the KB.
  EOT

  idle_session_ttl_in_seconds = var.agent_session_ttl

  tags = {
    Project     = var.project_name
    Environment = "production"
    ManagedBy   = "Terraform"
  }

  # WORKAROUND: aws_bedrockagent_agent with guardrail_configuration produces
  # "inconsistent result after apply" on first apply (known AWS provider bug).
  # Ignoring guardrail_configuration prevents this error. The guardrail resource
  # itself is still managed by Terraform — only the agent's reference to it is ignored.
  # REMOVE ignore_changes when deploying to a new sandbox or changing guardrail settings,
  # then run terraform apply TWICE (first apply fails, retry succeeds), then re-add.
  lifecycle {
    ignore_changes = [guardrail_configuration]
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
#   3. Manually update PROD alias (get IDs from terraform output):
#      aws bedrock-agent update-agent-alias \
#        --agent-id <AGENT_ID> --agent-alias-id <PROD_ALIAS_ID> \
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
  name        = "${var.project_name}-bedrock-agent-role"
  description = "Service role for ${var.project_name} Bedrock Agent - model invocation, KB retrieval, guardrail access"

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


