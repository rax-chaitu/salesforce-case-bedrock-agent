# AgentCore to Bedrock Agent Migration Analysis

## Executive Summary

Your current architecture uses **Amazon Bedrock AgentCore** (the newer, more complex runtime-based system) which requires:
- Docker container deployment to ECR
- AgentCore Runtime with Python/Strands Agents SDK
- AgentCore Gateway for MCP tool integration
- AgentCore Memory for conversation persistence
- Cognito for OAuth authentication
- Complex IAM roles (~8 policies)

The target **Amazon Bedrock Agents** architecture is significantly simpler:
- No container management
- Direct Knowledge Base attachment
- Action Groups for custom tools (Lambda-based)
- Built-in session management
- Simpler IAM (~3 policies)

**Migration Recommendation**: ✅ **Proceed with migration**. Your use case (case analysis with KB search) is a perfect fit for Bedrock Agents. You'll eliminate 60% of infrastructure complexity while maintaining all functionality.

**Estimated Effort**: 2-3 days (including testing)
**Risk Level**: Low (can run in parallel)
**Cost Impact**: ~30% reduction (no ECR, simpler compute)

---

## 1. Current Architecture Analysis

### Architecture Diagram (Current - AgentCore)

```
┌─────────────────────────────────────────────────────────────────────────────────────────────────┐
│                                    CURRENT ARCHITECTURE                                          │
│                                    (AgentCore-based)                                             │
└─────────────────────────────────────────────────────────────────────────────────────────────────┘

                    ┌─────────────────────────────────────────────┐
                    │           External Clients                   │
                    │     (Salesforce LWC, curl, etc.)            │
                    └──────────────────┬──────────────────────────┘
                                       │
                                       ▼
┌─────────────────────────────────────────────────────────────────────────────────────────────────┐
│                              API Gateway (salesforceagent-api)                                   │
│                    https://4m6dgv3lmi.execute-api.us-east-1.amazonaws.com/prod                   │
│                                                                                                  │
│  Endpoints:                                                                                      │
│  ├── GET  /health          → Health check with AgentCore connectivity                           │
│  ├── GET  /test            → API test                                                           │
│  ├── POST /agent/invoke    → Direct AgentCore invocation                                        │
│  ├── POST /case/analyze    → Case analysis                                                      │
│  ├── POST /case/escalation-check → Escalation assessment                                        │
│  ├── POST /kb/search       → Knowledge Base vector search                                       │
│  └── POST /kb/rag          → Knowledge Base RAG query                                           │
└────────────────────────────────────────┬────────────────────────────────────────────────────────┘
                                         │
                                         ▼
┌─────────────────────────────────────────────────────────────────────────────────────────────────┐
│                            Lambda: salesforceagent-api                                           │
│                            (lambda_function.py - 465 lines)                                     │
│                                                                                                  │
│  ┌──────────────────────────────────────────────────────────────────────────────────────────┐  │
│  │  AWS Clients:                                                                              │  │
│  │  • bedrock_agentcore (bedrock-agentcore client)                                           │  │
│  │  • bedrock_agent_runtime (for KB operations)                                              │  │
│  │                                                                                            │  │
│  │  Environment Variables:                                                                    │  │
│  │  • AGENT_RUNTIME_ARN = arn:aws:bedrock-agentcore:...:runtime/salesforceagent_Agent-*     │  │
│  │  • AGENT_QUALIFIER = DEV                                                                   │  │
│  │  • BEDROCK_KNOWLEDGE_BASE_ID = TKYEX1S8ZP                                                 │  │
│  │  • KB_MODEL_ARN = amazon.nova-pro-v1:0                                                    │  │
│  └──────────────────────────────────────────────────────────────────────────────────────────┘  │
└────────────────────────────────────────┬────────────────────────────────────────────────────────┘
                                         │
                    ┌────────────────────┼────────────────────┐
                    │                    │                    │
                    ▼                    ▼                    ▼
┌──────────────────────────┐ ┌──────────────────────┐ ┌──────────────────────────────────────────┐
│   AgentCore Runtime      │ │   Knowledge Base     │ │        AgentCore Gateway                 │
│   salesforceagent_Agent  │ │   TKYEX1S8ZP         │ │        salesforceagent-Gateway          │
│   -7cR9676mLR            │ │                      │ │                                          │
│                          │ │   Storage: S3 Vectors│ │   Protocol: MCP                         │
│   ┌──────────────────┐   │ │   Embedding: Titan   │ │   Auth: Cognito JWT                     │
│   │ Docker Container │   │ │   v2 (1024 dims)     │ │                                          │
│   │ in ECR           │   │ │                      │ │   Target: MCP Lambda                    │
│   │                  │   │ │   Data Sources:      │ │   (placeholder_tool)                    │
│   │ src/main.py      │   │ │   • Closed Cases     │ │                                          │
│   │ - Strands Agent  │   │ │   • KB Articles      │ └──────────────────────────────────────────┘
│   │ - KB Tools       │   │ │                      │                    │
│   │ - MCP Client     │   │ └──────────────────────┘                    │
│   │ - Memory Mgr     │   │                                              ▼
│   └──────────────────┘   │                              ┌──────────────────────────────────────┐
│                          │                              │     AgentCore Memory                 │
│   Endpoints:             │                              │     salesforceagent_Memory           │
│   • DEV                  │                              │     (30 day event expiry)           │
│   • PROD                 │                              └──────────────────────────────────────┘
└──────────────────────────┘                                               │
           │                                                               ▼
           │                                              ┌──────────────────────────────────────┐
           │                                              │     Cognito User Pool                │
           │                                              │     salesforceagent-CognitoUserPool  │
           │                                              │                                       │
           │                                              │     OAuth: client_credentials        │
           │                                              │     Scope: basic                      │
           │                                              └──────────────────────────────────────┘
           ▼
┌──────────────────────────┐
│         ECR              │
│  bedrock-agentcore/      │
│  salesforceagent:latest  │
│                          │
│  Docker Image:           │
│  • Python 3.11           │
│  • strands-agents        │
│  • bedrock-agentcore SDK │
│  • mcp client            │
└──────────────────────────┘
```

### Component Inventory

| Component | Resource Name | Purpose | Lines of Code/Config |
|-----------|---------------|---------|---------------------|
| **Lambda (API)** | `salesforceagent-api` | API handler, routes requests | 465 lines Python |
| **Lambda (MCP)** | `salesforceagent-McpLambda` | MCP tool placeholder | 60 lines Python |
| **AgentCore Runtime** | `salesforceagent_Agent-7cR9676mLR` | AI agent execution | Container + 149 lines |
| **AgentCore Gateway** | `salesforceagent-Gateway` | MCP protocol handler | Terraform config |
| **AgentCore Memory** | `salesforceagent_Memory` | 30-day conversation history | Terraform config |
| **Knowledge Base** | `TKYEX1S8ZP` | Closed cases + KB articles | Manual setup |
| **ECR Repository** | `bedrock-agentcore/salesforceagent` | Docker image storage | Dockerfile |
| **Cognito** | `salesforceagent-CognitoUserPool` | OAuth for Gateway | Terraform config |
| **API Gateway** | `salesforceagent-api` | REST API | 191 lines Terraform |

### AWS Resources Created (Current)

| Service | Count | Resources |
|---------|-------|-----------|
| Lambda | 2 | API handler, MCP handler |
| ECR | 1 | Container repository |
| IAM Roles | 4 | Lambda role, Gateway role, Runtime role, MCP Lambda role |
| IAM Policies | 8+ | Various permissions |
| Cognito | 3 | User Pool, Client, Resource Server |
| API Gateway | 1 | REST API with 7 endpoints |
| CloudWatch | 2 | Log groups |
| AgentCore | 4 | Runtime, Gateway, Memory, Endpoints |
| Bedrock KB | 1 | Knowledge Base (manual) |

---

## 2. Target Architecture (Bedrock Agents)

### Architecture Diagram (Target - Bedrock Agents)

```
┌─────────────────────────────────────────────────────────────────────────────────────────────────┐
│                                    TARGET ARCHITECTURE                                           │
│                                    (Bedrock Agents)                                              │
└─────────────────────────────────────────────────────────────────────────────────────────────────┘

                    ┌─────────────────────────────────────────────┐
                    │           External Clients                   │
                    │     (Salesforce LWC, curl, etc.)            │
                    └──────────────────┬──────────────────────────┘
                                       │
                                       ▼
┌─────────────────────────────────────────────────────────────────────────────────────────────────┐
│                              API Gateway (salesforceagent-api)                                   │
│                    https://xxxxx.execute-api.us-east-1.amazonaws.com/prod                        │
│                                                                                                  │
│  Endpoints (simplified):                                                                         │
│  ├── GET  /health          → Health check                                                       │
│  ├── POST /agent/invoke    → Bedrock Agent invocation                                           │
│  ├── POST /case/analyze    → Case analysis (via Agent)                                          │
│  └── POST /kb/search       → Direct KB search (optional)                                        │
└────────────────────────────────────────┬────────────────────────────────────────────────────────┘
                                         │
                                         ▼
┌─────────────────────────────────────────────────────────────────────────────────────────────────┐
│                            Lambda: salesforceagent-api (simplified)                              │
│                            (~150 lines - 68% reduction)                                         │
│                                                                                                  │
│  AWS Clients:                                                                                    │
│  • bedrock_agent_runtime (for Agent + KB)                                                       │
│                                                                                                  │
│  Environment Variables:                                                                          │
│  • BEDROCK_AGENT_ID = XXXXXXXXXX                                                                │
│  • BEDROCK_AGENT_ALIAS_ID = XXXXXXXXXX                                                          │
│  • BEDROCK_KNOWLEDGE_BASE_ID = TKYEX1S8ZP (reused!)                                            │
└────────────────────────────────────────┬────────────────────────────────────────────────────────┘
                                         │
                    ┌────────────────────┴────────────────────┐
                    │                                         │
                    ▼                                         ▼
┌──────────────────────────────────────────────┐ ┌──────────────────────────────────────────────┐
│           Bedrock Agent                       │ │         Knowledge Base                       │
│           salesforceagent                     │ │         TKYEX1S8ZP (REUSED)                 │
│                                               │ │                                              │
│   ┌───────────────────────────────────────┐  │ │   Storage: S3 Vectors                       │
│   │  Agent Instructions                   │  │ │   Embedding: Titan v2                       │
│   │  (migrated from src/main.py)          │  │ │                                              │
│   │                                       │  │ │   Data Sources:                             │
│   │  Foundation Model:                    │  │ │   • Closed Cases                            │
│   │  amazon.nova-pro-v1:0                │◀─┼─┤   • KB Articles                             │
│   │                                       │  │ │                                              │
│   │  Knowledge Base: TKYEX1S8ZP          │──┼─▶│                                              │
│   │  (directly attached)                  │  │ │                                              │
│   └───────────────────────────────────────┘  │ └──────────────────────────────────────────────┘
│                                               │
│   Action Groups (optional):                   │
│   • SalesforceTools (if needed)              │
│   • Custom integrations                       │
│                                               │
│   Aliases:                                    │
│   • DEV, PROD                                │
└──────────────────────────────────────────────┘

                         ❌ REMOVED COMPONENTS ❌
┌─────────────────────────────────────────────────────────────────────────────────────────────────┐
│  • ECR Repository (no containers needed)                                                        │
│  • AgentCore Runtime (replaced by Bedrock Agent)                                                │
│  • AgentCore Gateway (not needed - no MCP)                                                      │
│  • AgentCore Memory (use Bedrock Agent sessions)                                                │
│  • Cognito User Pool (not needed for this use case)                                             │
│  • MCP Lambda (not needed)                                                                       │
│  • Docker build process                                                                          │
│  • strands-agents dependency                                                                     │
│  • bedrock-agentcore SDK dependency                                                             │
└─────────────────────────────────────────────────────────────────────────────────────────────────┘
```

---

## 3. Gap Analysis

### Feature Mapping

| Current Feature (AgentCore) | Bedrock Agent Equivalent | Migration Effort | Notes |
|-----------------------------|-------------------------|------------------|-------|
| **AgentCore Runtime** | Bedrock Agent | ⭐ Low | Direct replacement, simpler |
| **Container Deployment (ECR)** | ❌ Not needed | ⭐ Low | Eliminated - no containers |
| **AgentCore Gateway (MCP)** | Action Groups (Lambda) | ⭐⭐ Medium | Only if custom tools needed |
| **AgentCore Memory** | Session Attributes + DynamoDB | ⭐⭐ Medium | Built-in session management |
| **Cognito OAuth** | ❌ Not needed | ⭐ Low | Eliminated for internal use |
| **Knowledge Base** | ✅ Reuse existing | ⭐ None | Same KB, direct attachment |
| **System Prompt** | Agent Instructions | ⭐ Low | Copy/paste with minor edits |
| **KB Tools (search_knowledge_base)** | Built-in KB retrieval | ⭐ Low | Automatic with attached KB |
| **KB Tools (get_case_resolution)** | Built-in RAG | ⭐ Low | Automatic |
| **Multi-endpoint (DEV/PROD)** | Agent Aliases | ⭐ Low | Same concept |
| **Strands Agent SDK** | ❌ Not needed | ⭐ Low | Eliminated |

### Features Lost vs Gained

#### ❌ Features Lost (Minor Impact)
| Feature | Impact | Workaround |
|---------|--------|------------|
| MCP Protocol Support | Low | Use Action Groups if external tools needed |
| Custom Python Tools in Container | Low | Move to Action Group Lambda |
| 30-day Memory Persistence | Medium | Use DynamoDB for long-term memory |
| Code Interpreter (AgentCoreCodeInterpreter) | Low | Not used in current implementation |

#### ✅ Features Gained
| Feature | Benefit |
|---------|---------|
| No container management | Faster deployments, no Docker |
| Simpler IAM | 3 policies vs 8+ |
| Built-in guardrails | Content filtering, PII protection |
| Trace/debug console | Better debugging in AWS Console |
| Automatic KB orchestration | No manual retrieval code |
| Lower latency | Direct invocation, no container cold start |
| Cost savings | No ECR storage, simpler compute |

---

## 4. Migration Plan

### Phase 1: Create Bedrock Agent (Day 1)

#### Step 1.1: Terraform for Bedrock Agent

```hcl
# terraform/bedrock_agent.tf (NEW FILE)

################################################################################
# Bedrock Agent - Replaces AgentCore Runtime
################################################################################

resource "aws_bedrockagent_agent" "salesforce_agent" {
  agent_name              = "salesforceagent"
  agent_resource_role_arn = aws_iam_role.bedrock_agent_role.arn
  foundation_model        = "amazon.nova-pro-v1:0"
  
  instruction = <<-EOT
    You are a helpful Salesforce support assistant with access to a Knowledge Base 
    containing past closed cases and knowledge articles.

    When analyzing cases:
    1. Search the Knowledge Base for similar past cases
    2. Look for resolutions and close notes from similar issues
    3. Identify if the issue can be self-resolved by the user
    4. Provide clear, actionable recommendations

    ANALYSIS FORMAT:
    ## Issue Summary
    [Brief summary of what the user is asking for]

    ## Self-Resolution Steps
    [Numbered steps the user can take, if applicable]

    ## Similar Cases Found
    [Reference similar cases from the Knowledge Base]

    ## Recommendation
    - Self_Resolvable: Yes/No
    - Estimated Resolution Time: X hours/days
    - If admin needed: Reason why

    Be concise, actionable, and always provide a clear next step.
  EOT

  idle_session_ttl_in_seconds = 600
  
  tags = {
    Project     = "salesforceagent"
    Environment = "production"
    ManagedBy   = "Terraform"
  }
}

################################################################################
# Knowledge Base Association
################################################################################

resource "aws_bedrockagent_agent_knowledge_base_association" "kb_association" {
  agent_id             = aws_bedrockagent_agent.salesforce_agent.agent_id
  knowledge_base_id    = var.knowledge_base_id  # Reuse existing: TKYEX1S8ZP
  description          = "Salesforce closed cases and knowledge articles"
  knowledge_base_state = "ENABLED"
}

################################################################################
# Agent Alias (DEV)
################################################################################

resource "aws_bedrockagent_agent_alias" "dev_alias" {
  agent_id         = aws_bedrockagent_agent.salesforce_agent.agent_id
  agent_alias_name = "DEV"
  description      = "Development alias"
  
  tags = {
    Environment = "development"
  }
}

################################################################################
# Agent Alias (PROD) - After testing
################################################################################

resource "aws_bedrockagent_agent_alias" "prod_alias" {
  agent_id         = aws_bedrockagent_agent.salesforce_agent.agent_id
  agent_alias_name = "PROD"
  description      = "Production alias"
  
  tags = {
    Environment = "production"
  }
}

################################################################################
# IAM Role for Bedrock Agent
################################################################################

resource "aws_iam_role" "bedrock_agent_role" {
  name = "salesforceagent-bedrock-agent-role"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Principal = {
          Service = "bedrock.amazonaws.com"
        }
        Action = "sts:AssumeRole"
        Condition = {
          StringEquals = {
            "aws:SourceAccount" = data.aws_caller_identity.current.account_id
          }
        }
      }
    ]
  })
}

resource "aws_iam_role_policy" "bedrock_agent_policy" {
  name = "salesforceagent-bedrock-agent-policy"
  role = aws_iam_role.bedrock_agent_role.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Sid    = "BedrockModelAccess"
        Effect = "Allow"
        Action = [
          "bedrock:InvokeModel",
          "bedrock:InvokeModelWithResponseStream"
        ]
        Resource = [
          "arn:aws:bedrock:${data.aws_region.current.region}::foundation-model/amazon.nova-pro-v1:0",
          "arn:aws:bedrock:${data.aws_region.current.region}::foundation-model/amazon.titan-embed-text-v2:0"
        ]
      },
      {
        Sid    = "KnowledgeBaseAccess"
        Effect = "Allow"
        Action = [
          "bedrock:Retrieve",
          "bedrock:RetrieveAndGenerate"
        ]
        Resource = [
          "arn:aws:bedrock:${data.aws_region.current.region}:${data.aws_caller_identity.current.account_id}:knowledge-base/${var.knowledge_base_id}"
        ]
      }
    ]
  })
}

################################################################################
# Outputs
################################################################################

output "bedrock_agent_id" {
  description = "Bedrock Agent ID"
  value       = aws_bedrockagent_agent.salesforce_agent.agent_id
}

output "bedrock_agent_arn" {
  description = "Bedrock Agent ARN"
  value       = aws_bedrockagent_agent.salesforce_agent.agent_arn
}

output "bedrock_agent_dev_alias_id" {
  description = "DEV Alias ID"
  value       = aws_bedrockagent_agent_alias.dev_alias.agent_alias_id
}

output "bedrock_agent_prod_alias_id" {
  description = "PROD Alias ID"
  value       = aws_bedrockagent_agent_alias.prod_alias.agent_alias_id
}
```

### Phase 2: Update Lambda Handler (Day 1-2)

#### Step 2.1: Simplified Lambda Function

```python
# lambda_function_bedrock_agent.py (NEW FILE - replaces lambda_function.py)

#!/usr/bin/env python3
"""
AWS Lambda handler for Bedrock Agent API
Simplified version - replaces AgentCore with Bedrock Agents
"""

import json
import uuid
import os
import boto3
import logging
from datetime import datetime

logger = logging.getLogger()
logger.setLevel(logging.INFO)

# Initialize Bedrock Agent Runtime client
bedrock_agent_runtime = boto3.client("bedrock-agent-runtime", region_name="us-east-1")

# Configuration from environment
AGENT_ID = os.environ.get("BEDROCK_AGENT_ID")
AGENT_ALIAS_ID = os.environ.get("BEDROCK_AGENT_ALIAS_ID")
KNOWLEDGE_BASE_ID = os.environ.get("BEDROCK_KNOWLEDGE_BASE_ID", "TKYEX1S8ZP")


def lambda_handler(event, context):
    """Main Lambda handler"""
    try:
        http_method = event.get("httpMethod", "GET")
        path = event.get("path", "/")
        body = event.get("body", "")

        request_data = {}
        if body:
            try:
                request_data = json.loads(body)
            except json.JSONDecodeError:
                return create_response(400, {"error": "Invalid JSON"})

        # Route requests
        if path == "/health" and http_method == "GET":
            return handle_health()
        elif path == "/agent/invoke" and http_method == "POST":
            return handle_agent_invoke(request_data)
        elif path == "/case/analyze" and http_method == "POST":
            return handle_case_analyze(request_data)
        elif path == "/kb/search" and http_method == "POST":
            return handle_kb_search(request_data)
        else:
            return create_response(404, {"error": "Endpoint not found"})

    except Exception as e:
        logger.error(f"Error: {str(e)}")
        return create_response(500, {"error": "Internal server error"})


def create_response(status_code: int, body: dict):
    """Create HTTP response"""
    return {
        "statusCode": status_code,
        "headers": {
            "Content-Type": "application/json",
            "Access-Control-Allow-Origin": "*",
        },
        "body": json.dumps(body),
    }


def handle_health():
    """Health check"""
    return create_response(200, {
        "status": "healthy",
        "agent_id": AGENT_ID,
        "agent_alias_id": AGENT_ALIAS_ID,
        "timestamp": datetime.utcnow().isoformat(),
    })


def handle_agent_invoke(request_data):
    """Invoke Bedrock Agent"""
    if "prompt" not in request_data:
        return create_response(400, {"error": "Missing prompt"})

    session_id = request_data.get("session_id") or str(uuid.uuid4())
    
    try:
        response = bedrock_agent_runtime.invoke_agent(
            agentId=AGENT_ID,
            agentAliasId=AGENT_ALIAS_ID,
            sessionId=session_id,
            inputText=request_data["prompt"],
        )

        # Process streaming response
        result = ""
        for event in response.get("completion", []):
            if "chunk" in event:
                chunk = event["chunk"]
                if "bytes" in chunk:
                    result += chunk["bytes"].decode("utf-8")

        return create_response(200, {
            "success": True,
            "response": result,
            "session_id": session_id,
            "timestamp": datetime.utcnow().isoformat(),
        })

    except Exception as e:
        logger.error(f"Agent invoke error: {str(e)}")
        return create_response(500, {"error": str(e)})


def handle_case_analyze(request_data):
    """Case analysis via Bedrock Agent"""
    required = ["case_number", "subject", "description"]
    for field in required:
        if field not in request_data:
            return create_response(400, {"error": f"Missing {field}"})

    prompt = f"""Analyze this Salesforce case and provide recommendations:

Case Number: {request_data["case_number"]}
Subject: {request_data["subject"]}
Description: {request_data["description"]}
Priority: {request_data.get("priority", "Medium")}

Search the Knowledge Base for similar cases and provide:
1. Issue summary
2. Self-resolution steps (if applicable)
3. Similar cases found
4. Recommendation (self-resolvable or needs admin)"""

    session_id = f"case-{request_data['case_number']}-{uuid.uuid4().hex[:8]}"
    
    try:
        response = bedrock_agent_runtime.invoke_agent(
            agentId=AGENT_ID,
            agentAliasId=AGENT_ALIAS_ID,
            sessionId=session_id,
            inputText=prompt,
        )

        result = ""
        for event in response.get("completion", []):
            if "chunk" in event:
                chunk = event["chunk"]
                if "bytes" in chunk:
                    result += chunk["bytes"].decode("utf-8")

        return create_response(200, {
            "success": True,
            "case": {
                "number": request_data["case_number"],
                "subject": request_data["subject"],
            },
            "analysis": result,
            "session_id": session_id,
            "timestamp": datetime.utcnow().isoformat(),
        })

    except Exception as e:
        logger.error(f"Case analysis error: {str(e)}")
        return create_response(500, {"error": str(e)})


def handle_kb_search(request_data):
    """Direct Knowledge Base search"""
    if "query" not in request_data:
        return create_response(400, {"error": "Missing query"})

    try:
        response = bedrock_agent_runtime.retrieve(
            knowledgeBaseId=KNOWLEDGE_BASE_ID,
            retrievalQuery={"text": request_data["query"]},
            retrievalConfiguration={
                "vectorSearchConfiguration": {
                    "numberOfResults": request_data.get("max_results", 5)
                }
            },
        )

        results = []
        for r in response.get("retrievalResults", []):
            results.append({
                "content": r.get("content", {}).get("text", ""),
                "score": r.get("score", 0),
            })

        return create_response(200, {
            "success": True,
            "query": request_data["query"],
            "results": results,
            "timestamp": datetime.utcnow().isoformat(),
        })

    except Exception as e:
        logger.error(f"KB search error: {str(e)}")
        return create_response(500, {"error": str(e)})
```

### Phase 3: Update API Gateway Lambda (Day 2)

Update `terraform/api_gateway.tf`:

```hcl
# Update Lambda environment variables
resource "aws_lambda_function" "agentcore_api" {
  # ... existing config ...
  
  environment {
    variables = {
      # NEW: Bedrock Agent config
      BEDROCK_AGENT_ID       = aws_bedrockagent_agent.salesforce_agent.agent_id
      BEDROCK_AGENT_ALIAS_ID = aws_bedrockagent_agent_alias.dev_alias.agent_alias_id
      BEDROCK_KNOWLEDGE_BASE_ID = var.knowledge_base_id
      
      # DEPRECATED: Remove these after migration
      # AGENT_RUNTIME_ARN = ...
      # AGENT_QUALIFIER = ...
    }
  }
}

# Update IAM policy for Bedrock Agent
resource "aws_iam_role_policy" "lambda_bedrock" {
  name = "salesforceagent-lambda-bedrock"
  role = aws_iam_role.lambda_role.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Sid    = "BedrockAgentAccess"
        Effect = "Allow"
        Action = [
          "bedrock:InvokeAgent"
        ]
        Resource = [
          aws_bedrockagent_agent.salesforce_agent.agent_arn,
          "${aws_bedrockagent_agent.salesforce_agent.agent_arn}/*"
        ]
      },
      {
        Sid    = "KnowledgeBaseAccess"
        Effect = "Allow"
        Action = [
          "bedrock:Retrieve"
        ]
        Resource = [
          "arn:aws:bedrock:${data.aws_region.current.region}:${data.aws_caller_identity.current.account_id}:knowledge-base/${var.knowledge_base_id}"
        ]
      }
    ]
  })
}
```

### Phase 4: Deprecate AgentCore Resources (Day 3)

After successful testing, remove from `bedrock_agentcore.tf`:
- ECR Repository
- Docker build process
- AgentCore Runtime
- AgentCore Gateway
- AgentCore Memory
- Cognito resources
- MCP Lambda

---

## 5. Risk Assessment

| Risk | Likelihood | Impact | Mitigation |
|------|------------|--------|------------|
| Agent response quality differs | Medium | Medium | Test extensively before switching |
| Missing MCP tool functionality | Low | Low | Placeholder tool not used in production |
| Session/memory behavior changes | Medium | Low | Document session ID handling |
| API response format changes | Low | High | Maintain backward compatibility |
| Terraform state issues | Low | Medium | Use `terraform state mv` carefully |
| Knowledge Base issues | Very Low | High | KB is reused, not migrated |

### Rollback Plan

1. Keep `bedrock_agentcore.tf` commented (not deleted) for 30 days
2. Maintain Lambda with feature flag:
   ```python
   USE_BEDROCK_AGENT = os.environ.get("USE_BEDROCK_AGENT", "true") == "true"
   ```
3. API Gateway can route to either Lambda version
4. Terraform workspaces for parallel testing

---

## 6. Testing Strategy

### Parallel Testing

```bash
# Test current (AgentCore)
curl -X POST "https://4m6dgv3lmi.execute-api.us-east-1.amazonaws.com/prod/agent/invoke" \
  -H "Content-Type: application/json" \
  -d '{"prompt": "Summarize the top 3 cases"}'

# Test new (Bedrock Agent) - after deployment
curl -X POST "https://NEW-API-ID.execute-api.us-east-1.amazonaws.com/prod/agent/invoke" \
  -H "Content-Type: application/json" \
  -d '{"prompt": "Summarize the top 3 cases"}'

# Compare responses for:
# - Quality of analysis
# - Response time
# - Error handling
```

### Validation Criteria

| Metric | AgentCore Baseline | Bedrock Agent Target |
|--------|-------------------|---------------------|
| Response time (p95) | ~8 seconds | ≤6 seconds |
| Error rate | <1% | <1% |
| KB retrieval accuracy | Manual | Automatic |
| Analysis quality | Good | Equal or better |

---

## 7. Implementation Checklist

### Pre-Migration
- [ ] Review and approve this migration plan
- [ ] Backup current Terraform state
- [ ] Document current API response formats
- [ ] Set up parallel testing environment

### Migration Execution
- [ ] Create `terraform/bedrock_agent.tf`
- [ ] Create `lambda_function_bedrock_agent.py`
- [ ] Run `terraform plan` and review
- [ ] Deploy with `terraform apply`
- [ ] Test all endpoints
- [ ] Compare response quality

### Post-Migration
- [ ] Monitor for 7 days
- [ ] Remove AgentCore resources
- [ ] Update documentation
- [ ] Delete ECR images
- [ ] Update README.md

---

## 8. Cost Comparison

| Component | Current (AgentCore) | Target (Bedrock Agent) | Savings |
|-----------|--------------------|-----------------------|---------|
| Lambda (API) | $3/month | $3/month | $0 |
| Lambda (MCP) | $0.50/month | ❌ Removed | $0.50 |
| ECR Storage | $1/month | ❌ Removed | $1 |
| AgentCore Runtime | $10/month | ❌ Removed | $10 |
| Bedrock Agent | N/A | $5/month | -$5 |
| Cognito | $0.50/month | ❌ Removed | $0.50 |
| **Total** | **~$15/month** | **~$8/month** | **~$7/month (47%)** |

---

## Next Steps

1. **Review this document** and ask any clarifying questions
2. **Approve migration plan** 
3. I will create:
   - `terraform/bedrock_agent.tf`
   - `lambda_function_bedrock_agent.py` 
   - Updated IAM policies
4. **Test in parallel** before cutover
5. **Deprecate AgentCore** after validation

**Ready to proceed with Phase 1?**
