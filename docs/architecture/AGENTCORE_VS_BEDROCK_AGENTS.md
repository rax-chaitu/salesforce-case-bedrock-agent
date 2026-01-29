# AgentCore vs Bedrock Agents: Architecture Comparison

## Document Overview

| Attribute | Value |
|-----------|-------|
| Version | 1.0.0 |
| Date | January 2026 |
| Project | Salesforce Case Analysis Agent |
| Author | Architecture Team |

---

## Executive Summary

| Aspect | AgentCore | Bedrock Agents | Winner |
|--------|-----------|----------------|--------|
| **Complexity** | High (8+ services) | Low (3 services) | ✅ Bedrock Agents |
| **Scalability** | Manual container scaling | Auto-managed by AWS | ✅ Bedrock Agents |
| **Customization** | Full Python control | Declarative instructions | ✅ AgentCore |
| **Cost** | ~$15/month | ~$8/month | ✅ Bedrock Agents |
| **Time to Deploy** | 30+ minutes | 5 minutes | ✅ Bedrock Agents |
| **Future Agents** | Complex replication | Simple cloning | ✅ Bedrock Agents |

**Recommendation**: For our Salesforce case analysis use case, **Bedrock Agents is the clear winner**. It provides 90% of the functionality with 40% of the complexity.

---

## 1. What Each Architecture Does

### 1.1 AgentCore Architecture (Original Project)

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                        AGENTCORE ARCHITECTURE                                │
│                    (AWS_SANBOX1_AGENTCORE/salesforceagent)                  │
└─────────────────────────────────────────────────────────────────────────────┘

  ┌──────────────┐     ┌──────────────┐     ┌─────────────────────────────────┐
  │   Salesforce │────▶│ API Gateway  │────▶│        Lambda Function          │
  │     LWC      │     │   (REST)     │     │     (465 lines Python)          │
  └──────────────┘     └──────────────┘     └────────────┬────────────────────┘
                                                         │
                    ┌────────────────────────────────────┼────────────────────┐
                    │                                    │                    │
                    ▼                                    ▼                    ▼
  ┌─────────────────────────┐   ┌────────────────────┐   ┌──────────────────────┐
  │   AgentCore Runtime     │   │  Knowledge Base    │   │  AgentCore Gateway   │
  │   (Docker Container)    │   │  (S3 + OpenSearch) │   │     (MCP Protocol)   │
  │                         │   │                    │   │                      │
  │  ┌───────────────────┐  │   │  • Closed Cases    │   │  ┌────────────────┐  │
  │  │ Python App        │  │   │  • KB Articles     │   │  │ Cognito OAuth  │  │
  │  │ (strands-agents)  │  │   │  • Embeddings      │   │  │ (JWT Tokens)   │  │
  │  │                   │  │   │                    │   │  └────────────────┘  │
  │  │ • Custom Tools    │  │   └────────────────────┘   │          │           │
  │  │ • MCP Client      │  │                            │          ▼           │
  │  │ • Memory Manager  │  │                            │  ┌────────────────┐  │
  │  └───────────────────┘  │                            │  │  MCP Lambda    │  │
  └────────────┬────────────┘                            │  │ (Tool Handler) │  │
               │                                          │  └────────────────┘  │
               ▼                                          └──────────────────────┘
  ┌─────────────────────────┐                                       │
  │         ECR             │                                       ▼
  │  (Container Registry)   │                            ┌──────────────────────┐
  │                         │                            │  AgentCore Memory    │
  │  • Docker Image         │                            │  (30-day retention)  │
  │  • Python 3.11          │                            └──────────────────────┘
  │  • SDK Dependencies     │
  └─────────────────────────┘
```

**What AgentCore Does:**
1. **Runs Custom Python Code** - Your agent logic runs in a Docker container you build
2. **Uses strands-agents SDK** - Python library for building AI agents
3. **MCP Protocol** - Model Context Protocol for external tool integration
4. **OAuth Authentication** - Cognito provides JWT tokens for secure tool calls
5. **Container Management** - You build, push, and manage Docker images
6. **Custom Memory** - AgentCore Memory service with 30-day event retention

### 1.2 Bedrock Agents Architecture (New Project)

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                       BEDROCK AGENTS ARCHITECTURE                            │
│                    (AWS_SANDBOX2_OnlyBedrock)                                │
└─────────────────────────────────────────────────────────────────────────────┘

  ┌──────────────┐     ┌──────────────┐     ┌─────────────────────────────────┐
  │   Salesforce │────▶│ API Gateway  │────▶│        Lambda Function          │
  │     LWC      │     │   (REST)     │     │     (150 lines Python)          │
  └──────────────┘     └──────────────┘     └────────────┬────────────────────┘
                                                         │
                                    ┌────────────────────┴────────────────────┐
                                    │                                         │
                                    ▼                                         ▼
                  ┌─────────────────────────────────┐     ┌────────────────────┐
                  │        Bedrock Agent            │     │  Knowledge Base    │
                  │   (Fully Managed by AWS)        │     │  (S3 + OpenSearch) │
                  │                                 │     │                    │
                  │  • Agent Instructions (prompt)  │◀───▶│  • Closed Cases    │
                  │  • Foundation Model (Nova Pro)  │     │  • KB Articles     │
                  │  • Built-in RAG Orchestration   │     │  • Embeddings      │
                  │  • Session Management           │     │                    │
                  │  • Aliases (DEV/PROD)           │     └────────────────────┘
                  │                                 │
                  └─────────────────────────────────┘

                       ❌ NO CONTAINERS
                       ❌ NO ECR
                       ❌ NO COGNITO
                       ❌ NO MCP GATEWAY
                       ❌ NO CUSTOM MEMORY SERVICE
```

**What Bedrock Agents Does:**
1. **Managed Agent Service** - AWS handles all infrastructure
2. **Declarative Instructions** - Define agent behavior in plain text
3. **Built-in KB Integration** - Automatic RAG without custom code
4. **Session Management** - Built-in conversation state
5. **Aliases** - DEV/PROD versioning without containers

---

## 2. Component-by-Component Comparison

### 2.1 Agent Runtime

| Aspect | AgentCore | Bedrock Agents |
|--------|-----------|----------------|
| **Where it runs** | Your Docker container in ECR | AWS managed service |
| **Code you write** | Full Python application (~149 lines main.py + SDK) | Agent instructions (~20 lines prompt) |
| **Model invocation** | You code the LLM calls | AWS orchestrates automatically |
| **Cold start** | Container spin-up (5-30 seconds) | ~2 seconds |
| **Scaling** | Manual via container instances | Automatic by AWS |
| **Debugging** | CloudWatch logs + custom logging | Built-in trace console |

**Example - AgentCore (you write this code):**
```python
# src/main.py - AgentCore
from strands import Agent
from bedrock_agentcore import AgentCoreApp

@tool
def search_knowledge_base(query: str) -> str:
    """Search KB for similar cases"""
    client = boto3.client("bedrock-agent-runtime")
    response = client.retrieve(
        knowledgeBaseId=KB_ID,
        retrievalQuery={"text": query}
    )
    return format_results(response)

agent = Agent(
    model="amazon.nova-pro-v1:0",
    tools=[search_knowledge_base, get_case_resolution],
    system_prompt=SYSTEM_PROMPT
)
```

**Example - Bedrock Agents (you write this instruction):**
```text
# Agent Instructions - Bedrock Agents
You are a Salesforce support assistant with access to a Knowledge Base 
containing past closed cases and knowledge articles.

When analyzing cases:
1. Search the Knowledge Base for similar past cases
2. Provide clear, actionable recommendations

# That's it! KB search is automatic.
```

### 2.2 Knowledge Base Integration

| Aspect | AgentCore | Bedrock Agents |
|--------|-----------|----------------|
| **KB attachment** | Code the tool manually | Declarative association |
| **RAG orchestration** | You implement retrieval logic | Built-in |
| **Result formatting** | Your code | Automatic |
| **When KB is searched** | Explicit tool call | Agent decides automatically |

**AgentCore KB Integration:**
```python
# You must code the KB tool
@tool
def search_knowledge_base(query: str) -> str:
    client = boto3.client("bedrock-agent-runtime")
    response = client.retrieve(
        knowledgeBaseId=KB_ID,
        retrievalQuery={"text": query},
        retrievalConfiguration={
            "vectorSearchConfiguration": {
                "numberOfResults": 5
            }
        }
    )
    # You format the results
    results = []
    for r in response["retrievalResults"]:
        results.append(r["content"]["text"])
    return "\n".join(results)
```

**Bedrock Agents KB Integration:**
```hcl
# Terraform - just associate the KB
resource "aws_bedrockagent_agent_knowledge_base_association" "kb" {
  agent_id          = aws_bedrockagent_agent.agent.agent_id
  knowledge_base_id = "<KB_ID>"
  knowledge_base_state = "ENABLED"
}
# Done! Agent automatically searches KB when needed.
```

### 2.3 External Tools (MCP vs Action Groups)

| Aspect | AgentCore (MCP) | Bedrock Agents (Action Groups) |
|--------|-----------------|-------------------------------|
| **Protocol** | Model Context Protocol | Lambda-based |
| **Authentication** | Cognito OAuth (JWT) | IAM roles |
| **Setup complexity** | High (Gateway + Cognito + Lambda) | Medium (Lambda only) |
| **Tool definition** | Python decorators | OpenAPI schema |
| **Our use case needs it?** | ❌ No | ❌ No |

**Why we don't need external tools:**
Our agent only needs to:
1. Search the Knowledge Base (built-in)
2. Analyze case data (built-in with LLM)
3. Return recommendations (built-in)

No external APIs (Salesforce, Jira, etc.) are called by the agent.

### 2.4 Memory and Sessions

| Aspect | AgentCore | Bedrock Agents |
|--------|-----------|----------------|
| **Session handling** | AgentCore Memory service | Built-in session state |
| **Retention** | 30 days (configurable) | Session lifetime (10 min default) |
| **Cross-session memory** | Built-in | Requires DynamoDB |
| **Our use case needs long memory?** | ❌ No | ❌ No |

**Why built-in sessions are enough:**
Each case analysis is independent. We don't need:
- Long-term memory across cases
- User preference learning
- Multi-turn conversations spanning days

### 2.5 Container Management

| Aspect | AgentCore | Bedrock Agents |
|--------|-----------|----------------|
| **Docker required** | ✅ Yes | ❌ No |
| **ECR repository** | ✅ Yes | ❌ No |
| **Build time** | 3-5 minutes | 0 |
| **Image updates** | Rebuild + push + redeploy | Update instructions |
| **Dependency management** | Dockerfile + requirements.txt | N/A |

**AgentCore deployment flow:**
```bash
# Every code change requires:
docker build -t salesforceagent .                    # 2-3 min
aws ecr get-login-password | docker login            # 10 sec
docker push $ECR_URI:latest                          # 1-2 min
terraform apply                                       # 2-3 min
# Total: ~8-10 minutes per change
```

**Bedrock Agents deployment flow:**
```bash
# Code change:
# 1. Edit agent instructions in Terraform
terraform apply                                       # 30 sec
# Total: ~30 seconds per change
```

---

## 3. Scalability for Future Agents

### 3.1 Creating Additional Agents

| Scenario | AgentCore Effort | Bedrock Agents Effort |
|----------|-----------------|----------------------|
| **New agent (same type)** | New container + ECR + Runtime | Copy Terraform, change instructions |
| **New agent (different domain)** | New everything | New agent resource |
| **10 agents** | 10 ECR repos, 10 containers, 10 runtimes | 10 Terraform resources |
| **Time per new agent** | 2-4 hours | 15-30 minutes |

### 3.2 AgentCore Scaling Challenges

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                    AGENTCORE: 5 AGENTS INFRASTRUCTURE                        │
└─────────────────────────────────────────────────────────────────────────────┘

  ECR Repositories (5)          AgentCore Runtimes (5)      Gateways (5?)
  ├── agent-cases               ├── cases-runtime           ├── cases-gateway
  ├── agent-leads               ├── leads-runtime           ├── leads-gateway
  ├── agent-opportunities       ├── opps-runtime            ├── opps-gateway
  ├── agent-accounts            ├── accounts-runtime        ├── accounts-gateway
  └── agent-contacts            └── contacts-runtime        └── contacts-gateway
  
  Docker Images to maintain: 5
  Container configurations: 5
  Memory services: 5 (or shared)
  Cognito clients: 5 (or shared)
  
  Total AWS resources: ~40+
  Monthly cost: ~$75+
  Deployment time: 30+ minutes each
```

### 3.3 Bedrock Agents Scaling Simplicity

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                    BEDROCK AGENTS: 5 AGENTS INFRASTRUCTURE                   │
└─────────────────────────────────────────────────────────────────────────────┘

  Bedrock Agents (5)                    Knowledge Bases (shared or separate)
  ├── agent-cases (instructions)        ├── salesforce-kb (shared)
  ├── agent-leads (instructions)        │
  ├── agent-opportunities (instructions)│
  ├── agent-accounts (instructions)     │
  └── agent-contacts (instructions)     │
  
  Docker Images: 0
  ECR Repos: 0
  Cognito: 0
  
  Total AWS resources: ~15
  Monthly cost: ~$40
  Deployment time: 5 minutes each
```

### 3.4 Terraform Comparison for Multiple Agents

**AgentCore - Adding a new agent:**
```hcl
# New ECR repository
resource "aws_ecr_repository" "new_agent" {
  name = "bedrock-agentcore/new-agent"
}

# Docker build
resource "null_resource" "docker_build" {
  # ... 30 lines of build configuration
}

# AgentCore Runtime
resource "awscc_bedrock_agentcoreruntime_agent_runtime" "new_agent" {
  # ... 40 lines of runtime configuration
}

# AgentCore Gateway (if MCP needed)
# ... 30 more lines

# AgentCore Memory
# ... 20 more lines

# New Cognito client
# ... 15 more lines

# Total: ~150 lines per agent
```

**Bedrock Agents - Adding a new agent:**
```hcl
# New Bedrock Agent
resource "aws_bedrockagent_agent" "new_agent" {
  agent_name              = "new-agent"
  agent_resource_role_arn = aws_iam_role.bedrock_agent_role.arn  # Reuse!
  foundation_model        = "amazon.nova-pro-v1:0"
  
  instruction = <<-EOT
    You are a [NEW DOMAIN] assistant...
    [Agent-specific instructions]
  EOT
}

# KB Association (if using KB)
resource "aws_bedrockagent_agent_knowledge_base_association" "new_agent_kb" {
  agent_id          = aws_bedrockagent_agent.new_agent.agent_id
  knowledge_base_id = var.knowledge_base_id  # Reuse!
}

# Aliases
resource "aws_bedrockagent_agent_alias" "new_agent_dev" {
  agent_id         = aws_bedrockagent_agent.new_agent.agent_id
  agent_alias_name = "DEV"
}

# Total: ~30 lines per agent
```

---

## 4. When to Choose Each

### 4.1 Choose AgentCore When:

| Requirement | Why AgentCore |
|-------------|---------------|
| **Custom Python tools** | Full control over tool implementation |
| **MCP Protocol integration** | Native MCP support |
| **Complex orchestration** | Custom multi-agent workflows |
| **Specific Python libraries** | Container allows any dependency |
| **Code interpreter** | AgentCoreCodeInterpreter built-in |
| **Long-term memory** | 30-day event retention |
| **Existing Python agent** | Easier migration with strands-agents |

### 4.2 Choose Bedrock Agents When:

| Requirement | Why Bedrock Agents |
|-------------|-------------------|
| **Simple RAG use case** | Built-in KB integration |
| **Fast iteration** | No container builds |
| **Cost optimization** | 47% cheaper |
| **Team without Docker expertise** | No containers |
| **Rapid prototyping** | Deploy in minutes |
| **Multiple similar agents** | Easy to replicate |
| **AWS managed operations** | No container patching |

### 4.3 Our Project Decision Matrix

| Requirement | Needed? | AgentCore | Bedrock Agents |
|-------------|---------|-----------|----------------|
| Search closed cases | ✅ Yes | Manual tool | Built-in ✅ |
| Analyze case data | ✅ Yes | Custom code | Built-in ✅ |
| Provide recommendations | ✅ Yes | Custom code | Built-in ✅ |
| Call Salesforce API | ❌ No | MCP Gateway | Action Group |
| Code interpreter | ❌ No | Built-in | Not available |
| Long-term memory | ❌ No | Built-in | DynamoDB |
| Custom Python libraries | ❌ No | Container | N/A |
| Fast deployment | ✅ Yes | 10 min | 30 sec ✅ |
| Low cost | ✅ Yes | $15/mo | $8/mo ✅ |

**Result: Bedrock Agents wins 4/5 requirements we actually need.**

---

## 5. Cost Analysis

### 5.1 Current Costs (AgentCore)

| Component | Monthly Cost |
|-----------|--------------|
| Lambda (API) | $3.00 |
| Lambda (MCP placeholder) | $0.50 |
| ECR Storage | $1.00 |
| AgentCore Runtime | $10.00 |
| Cognito | $0.50 |
| CloudWatch Logs | $0.50 |
| **Total** | **~$15.50/month** |

### 5.2 Target Costs (Bedrock Agents)

| Component | Monthly Cost |
|-----------|--------------|
| Lambda (API) | $3.00 |
| Bedrock Agent invocations | $4.00 |
| CloudWatch Logs | $0.50 |
| **Total** | **~$7.50/month** |

### 5.3 Scaling Cost Comparison

| Agents | AgentCore | Bedrock Agents | Savings |
|--------|-----------|----------------|---------|
| 1 | $15.50 | $7.50 | $8.00 (52%) |
| 5 | $67.50 | $27.50 | $40.00 (59%) |
| 10 | $130.00 | $50.00 | $80.00 (62%) |
| 20 | $255.00 | $95.00 | $160.00 (63%) |

---

## 6. Migration Complexity

### 6.1 What We Keep

| Component | Status |
|-----------|--------|
| Knowledge Base (<KB_ID>) | ✅ Reused as-is |
| API Gateway structure | ✅ Same endpoints |
| Salesforce LWC | ✅ No changes needed |
| S3 data sources | ✅ Same bucket |

### 6.2 What We Remove

| Component | Reason |
|-----------|--------|
| ECR Repository | No containers needed |
| Docker build process | No containers needed |
| AgentCore Runtime | Replaced by Bedrock Agent |
| AgentCore Gateway | No MCP tools needed |
| AgentCore Memory | Built-in sessions sufficient |
| Cognito | No OAuth needed |
| MCP Lambda | No external tools |
| strands-agents SDK | Not needed |

### 6.3 What We Simplify

| Before (AgentCore) | After (Bedrock Agents) |
|-------------------|----------------------|
| 465 lines Lambda | 150 lines Lambda |
| 8+ IAM policies | 3 IAM policies |
| ~40 AWS resources | ~15 AWS resources |
| 10 min deploy | 30 sec deploy |

---

## 7. Recommendation Summary

### For Our Salesforce Case Analysis Project:

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                         RECOMMENDATION: BEDROCK AGENTS                       │
└─────────────────────────────────────────────────────────────────────────────┘

  ✅ Simpler architecture (60% fewer resources)
  ✅ Faster deployment (30 seconds vs 10 minutes)
  ✅ Lower cost (47% savings)
  ✅ Easier to scale (30 lines vs 150 lines per new agent)
  ✅ Built-in KB integration (no custom tool code)
  ✅ AWS managed (no container patching)
  
  ❌ Loses: Custom Python tools (not needed)
  ❌ Loses: MCP Protocol (not needed)
  ❌ Loses: 30-day memory (not needed)
```

### For Future Agent Projects:

| Use Case | Recommendation |
|----------|----------------|
| Simple Q&A with KB | **Bedrock Agents** |
| Case/ticket analysis | **Bedrock Agents** |
| Document search | **Bedrock Agents** |
| External API calls | **Bedrock Agents** (Action Groups) |
| Complex Python logic | AgentCore |
| Multi-agent orchestration | AgentCore |
| Code generation/execution | AgentCore |

---

## 8. Next Steps

1. ✅ **Completed**: Created AWS_SANDBOX2_OnlyBedrock project
2. ✅ **Completed**: Wrote all Terraform files for Bedrock Agents
3. ⏳ **Next**: Deploy to sandbox4 account
4. ⏳ **Next**: Test all endpoints
5. ⏳ **Next**: Compare response quality with AgentCore
6. ⏳ **Future**: Deprecate AgentCore project after validation

---

## Appendix: Quick Reference

### API Endpoints (Same for Both)

| Endpoint | Method | Purpose |
|----------|--------|---------|
| `/health` | GET | Health check |
| `/agent/invoke` | POST | Invoke agent with prompt |
| `/case/analyze` | POST | Analyze Salesforce case |
| `/kb/search` | POST | Direct KB search |

### Environment Variables

**AgentCore:**
```
AGENT_RUNTIME_ARN=arn:aws:bedrock-agentcore:...:runtime/salesforceagent_Agent-*
AGENT_QUALIFIER=DEV
BEDROCK_KNOWLEDGE_BASE_ID=<KB_ID>
```

**Bedrock Agents:**
```
BEDROCK_AGENT_ID=<agent-id>
BEDROCK_AGENT_ALIAS_ID=<alias-id>
BEDROCK_KNOWLEDGE_BASE_ID=<KB_ID>
```

### Deploy Commands

**AgentCore:**
```bash
docker build -t salesforceagent .
aws ecr get-login-password | docker login
docker push $ECR_URI:latest
terraform apply
```

**Bedrock Agents:**
```bash
terraform apply
# Done!
```
