# Event-Driven Self-Service Case Analysis Architecture

## Business Context

### Problem Statement
End users creating Salesforce Cases often wait hours/days for admin responses. Admins are busy, and many cases could be self-resolved if users had access to:
- Similar past closed cases with resolutions
- Relevant Knowledge Articles
- AI-powered guidance on self-resolution steps

### Solution Overview
When a Case is created in Salesforce:
1. **Platform Event** (`Integration_Event__e`) fires automatically
2. **AWS Event Relay** forwards to EventBridge (already configured: `AWS_Integration_UAT_TEST`)
3. **Lambda** invokes **Bedrock Agent** to analyze the case
4. **Bedrock Agent** searches Knowledge Base (closed cases + knowledge articles)
5. **Analysis** is written back to Case field
6. **User receives email** with AI-generated guidance

### Key Benefits
- Users get instant AI analysis without waiting for admins
- Self-resolvable issues are resolved faster
- Admins focus on complex cases requiring human intervention
- Knowledge Base is continuously improved with closed case patterns

---

## Architecture Diagram

```
┌─────────────────────────────────────────────────────────────────────────────────────────┐
│                              SALESFORCE UAT (UATDEC25)                                   │
│                                                                                          │
│  ┌──────────────┐         ┌─────────────────────────┐         ┌───────────────────┐    │
│  │  User Creates │ Trigger │   Integration_Event__e  │  Email  │   User Reviews    │    │
│  │    Case       │────────▶│   Platform Event        │◀────────│   AI Analysis     │    │
│  └──────────────┘         └───────────┬─────────────┘         └───────────────────┘    │
│         │                             │                               ▲                 │
│         │                             │                               │                 │
│         ▼                             │                               │                 │
│  ┌──────────────────────────────────────────────────────────────────────────────────┐  │
│  │                              Case Object                                          │  │
│  │  ┌────────────────────────────────────────────────────────────────────────────┐  │  │
│  │  │ Key Fields:                                                                 │  │  │
│  │  │ • Status: New → Agent_Analysis → [Self_Resolved | Admin_Router]            │  │  │
│  │  │ • Agent_Analysis__c: AI-generated analysis and recommendations             │  │  │
│  │  │ • Agent_Analysis_Status__c: Pending | Completed | Failed                   │  │  │
│  │  │ • Agent_Analyzed_Date__c: Timestamp of analysis                            │  │  │
│  │  │ • RecordType: Determines case routing logic                                │  │  │
│  │  │ • Type, Priority, Origin: Input for AI analysis                            │  │  │
│  │  └────────────────────────────────────────────────────────────────────────────┘  │  │
│  └──────────────────────────────────────────────────────────────────────────────────┘  │
│                                                                                          │
│  ┌──────────────────────────────────────────────────────────────────────────────────┐  │
│  │  Event Relay: AWS_Integration_UAT_TEST (RUN state)                               │  │
│  │  Channel: /event/Integration_Event__e                                             │  │
│  └──────────────────────────────────────────────────────────────────────────────────┘  │
└───────────────────────────────────────────────────────────────────────────────────────┘
                                        │
                                        ▼
┌─────────────────────────────────────────────────────────────────────────────────────────┐
│                              AWS (914296863611 - sandbox4)                               │
│                                                                                          │
│  ┌──────────────────────────────────────────────────────────────────────────────────┐  │
│  │                         Amazon EventBridge                                         │  │
│  │  Partner Event Source: aws.partner/salesforce.com/00DgP0000023yjFUAQ/...          │  │
│  │                                                                                    │  │
│  │  Rule: case-created-rule                                                          │  │
│  │  Pattern: {                                                                        │  │
│  │    "detail": {                                                                     │  │
│  │      "payload": {                                                                  │  │
│  │        "Object_Name__c": ["Case"],                                                │  │
│  │        "Type__c": ["Created"]                                                     │  │
│  │      }                                                                             │  │
│  │    }                                                                               │  │
│  │  }                                                                                 │  │
│  └────────────────────────────────────┬─────────────────────────────────────────────┘  │
│                                       │                                                  │
│                                       ▼                                                  │
│  ┌──────────────────────────────────────────────────────────────────────────────────┐  │
│  │                            Amazon SQS                                              │  │
│  │  Queue: case-analysis-queue                    DLQ: case-analysis-dlq             │  │
│  │  • Visibility: 300s                            • Failed messages                   │  │
│  │  • Max Receive: 3                              • Retention: 14 days                │  │
│  │  • Buffers events during spikes                • Alerts on messages > 0            │  │
│  └────────────────────────────────────┬─────────────────────────────────────────────┘  │
│                                       │                                                  │
│                                       ▼                                                  │
│  ┌──────────────────────────────────────────────────────────────────────────────────┐  │
│  │                    Lambda: case-analysis-processor                                 │  │
│  │  ┌────────────────────────────────────────────────────────────────────────────┐  │  │
│  │  │  1. Parse Integration_Event__e                                              │  │  │
│  │  │  2. Extract Case ID, Subject, Description, Type, Priority                   │  │  │
│  │  │  3. Check if analysis needed (RecordType filter)                            │  │  │
│  │  │  4. Invoke Bedrock Agent with case context                                  │  │  │
│  │  │  5. Receive AI analysis + self-resolution steps                             │  │  │
│  │  │  6. Update Salesforce Case via internal API                                 │  │  │
│  │  │     - Agent_Analysis__c = AI response                                       │  │  │
│  │  │     - Status = Self_Resolved (if self-resolvable) OR Admin_Router           │  │  │
│  │  └────────────────────────────────────────────────────────────────────────────┘  │  │
│  │                                                                                    │  │
│  │  🔒 INTERNAL ONLY - No public API exposure                                        │  │
│  │  Lambda calls Bedrock Agent directly within AWS                                   │  │
│  └────────────────────────────┬─────────────────────────────────────────────────────┘  │
│                               │                                                          │
│               ┌───────────────┼───────────────────┐                                     │
│               ▼               ▼                   ▼                                     │
│  ┌─────────────────────┐ ┌─────────────────┐ ┌─────────────────────────────────┐       │
│  │   Bedrock Agent     │ │ Knowledge Base  │ │   Salesforce API (Callback)    │       │
│  │   salesforceagent   │ │ TKYEX1S8ZP      │ │   • Update Case fields         │       │
│  │                     │ │                 │ │   • Add Case Comment            │       │
│  │   Model:            │ │ Content:        │ │   • Trigger email workflow      │       │
│  │   amazon.nova-pro   │ │ • Closed Cases  │ │                                 │       │
│  │                     │ │ • Knowledge     │ │   🔒 Connected App Auth         │       │
│  │   Aliases: DEV,PROD │ │   Articles      │ │   (Client Credentials Flow)     │       │
│  └─────────────────────┘ └─────────────────┘ └─────────────────────────────────┘       │
│                                                                                          │
└─────────────────────────────────────────────────────────────────────────────────────────┘
```

---

## Simplified Architecture (Bedrock Agent vs AgentCore)

This architecture uses **standard Bedrock Agents** instead of Bedrock AgentCore:

| Component | AgentCore (Old) | Bedrock Agent (New) |
|-----------|-----------------|---------------------|
| Agent Runtime | ECR Container + MCP | Managed Bedrock Agent |
| Memory | AgentCore Memory (30 days) | Session-based (30 min) |
| Tools | MCP Gateway + Lambda | Action Groups (optional) |
| KB Access | Manual tools | Direct attachment |
| Cognito | Required | Not needed |
| **Complexity** | High (15+ resources) | Low (6 resources) |

---

## Salesforce Case Object Details

### Case Record Types (11 types in UAT)

| Record Type | Description | Auto-Analysis |
|-------------|-------------|---------------|
| Bridge Team Intake Form | Internal team requests | ✅ Yes |
| FinancialForce | FF support requests | ✅ Yes |
| Sales Academy Request | Training requests | ❌ No (manual) |
| Raptor Support | Raptor system issues | ✅ Yes |
| QM Support | Quality management | ✅ Yes |
| ROE Escalations | Revenue ops escalations | ❌ No (manual) |
| Partner Portal | Partner inquiries | ✅ Yes |
| Tool Help | Tool access/support | ✅ Yes |
| Sales Commissions | Commission issues | ✅ Yes |
| Intake Request | General intake | ✅ Yes |
| Customer Success | CS requests | ✅ Yes |

### Key Case Fields for Analysis

| API Name | Label | Type | Usage in Analysis |
|----------|-------|------|-------------------|
| `Subject` | Subject | String | Primary search query |
| `Description` | Description | Textarea | Detailed context |
| `Type` | Case Type | Picklist | Categorization |
| `Case_Type__c` | Case Type (Custom) | Picklist | Sub-categorization |
| `Priority` | Priority | Picklist | High/Medium/Low |
| `Origin` | Case Origin | Picklist | Web/Email/Phone |
| `Status` | Status | Picklist | Workflow state |
| `RecordTypeId` | Record Type | Reference | Route to specific queue |
| `Close_Codes__c` | Close Codes | Picklist | Resolution category |
| `Close_Reason__c` | Close Reason | Picklist | Why closed |
| `DP_Resolution__c` | Resolution | Textarea | How it was resolved |
| `Comments` | Internal Comments | Textarea | Admin notes |

### New Fields Required (to be created)

| API Name | Label | Type | Description |
|----------|-------|------|-------------|
| `Agent_Analysis__c` | Agent Analysis | Long Text (32000) | AI-generated analysis |
| `Agent_Analysis_Status__c` | Analysis Status | Picklist | Pending, Completed, Failed, Not_Applicable |
| `Agent_Analyzed_Date__c` | Analyzed Date | DateTime | When analysis completed |
| `Self_Resolvable__c` | Self Resolvable | Checkbox | Can user resolve without admin |

### Case Status Flow

```
┌─────────────┐     ┌──────────────────┐     ┌───────────────────┐
│     New     │────▶│  Agent_Analysis  │────▶│  Self_Resolved    │
└─────────────┘     └────────┬─────────┘     └───────────────────┘
                             │                         
                             │ (If AI cannot help)     
                             ▼                         
                    ┌──────────────────┐               
                    │   Admin_Router   │               
                    │ (Needs human)    │               
                    └──────────────────┘               
```

---

## Knowledge Base Content Strategy

### What to Sync to AWS Knowledge Base

#### 1. Closed Cases (Selective)
```sql
-- Query for KB-worthy closed cases
SELECT Id, CaseNumber, Subject, Description, 
       Type, Case_Type__c, Priority, Origin,
       Close_Codes__c, Close_Reason__c, DP_Resolution__c,
       Comments, RecordType.Name
FROM Case 
WHERE IsClosed = true
  AND (DP_Resolution__c != null OR Comments != null)
  AND RecordType.Name IN ('Tool Help', 'FinancialForce', 'Raptor Support', 
                          'Partner Portal', 'Bridge Team Intake Form')
  AND CreatedDate >= LAST_N_YEARS:2
```

#### 2. Knowledge Articles (All Published)
```sql
-- Query for Knowledge Articles
SELECT Id, ArticleNumber, Title, 
       Answer__c, Summary,
       PublishStatus, IsLatestVersion
FROM Knowledge__kav
WHERE PublishStatus = 'Online'
  AND IsLatestVersion = true
  AND Language = 'en_US'
```

### KB Sync Schedule
- **Full Sync**: Weekly (Sunday 2 AM)
- **Incremental Sync**: Daily (closed cases from last 24h)
- **Knowledge Articles**: On publish (triggered by SF workflow)

---

## Agent Instructions (Bedrock Agent)

The Bedrock Agent is configured with these instructions in `terraform/bedrock_agent.tf`:

```
You are a Salesforce Case Analysis Agent for Rackspace internal support.

Your role is to analyze newly created Cases and provide:
1. Immediate self-resolution guidance when possible
2. Similar past case references with what worked
3. Relevant Knowledge Article recommendations
4. Clear indication if admin intervention is required

ANALYSIS PROCESS:
1. Search Knowledge Base for:
   - Similar closed cases (match Subject, Description, Type)
   - Relevant Knowledge Articles
   
2. Evaluate self-resolution potential:
   - If similar cases were self-resolved → provide steps
   - If Knowledge Article addresses the issue → summarize and link
   - If requires admin access/approval → route to Admin_Router

3. Generate response with:
   - Summary of the issue
   - Recommended self-resolution steps (if applicable)
   - Links to similar cases/articles
   - Estimated resolution time
   - Clear next steps for the user

RECORD TYPE SPECIFIC INSTRUCTIONS:
- Tool Help: Focus on access requests, permissions, tool guides
- FinancialForce: Focus on FF-specific procedures, approval workflows
- Raptor Support: Focus on Raptor system configurations, common errors
- Partner Portal: Focus on partner-facing procedures, escalation paths

OUTPUT FORMAT:
Always structure your response as:
## Issue Summary
[Brief summary of what the user is asking for]

## Self-Resolution Steps
[Numbered steps the user can take, if applicable]

## Related Resources
- [Similar Case: #XXXXX - Brief description]
- [Knowledge Article: Title - Link]

## Recommendation
[Self_Resolvable: Yes/No]
[If No: Reason why admin is needed]
[Estimated Resolution Time: X hours/days]

IMPORTANT:
- Be concise and actionable
- Use bullet points for clarity
- Never expose internal system details
- Always provide a clear next step
```

---

## Security Architecture

### API Exposure Model

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                           API ACCESS CONTROL                                 │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  INTERNAL (Event-Driven - No Public Exposure)                               │
│  ─────────────────────────────────────────────                              │
│  • Lambda → Bedrock Agent: Direct invocation within AWS                     │
│  • Lambda → Salesforce: OAuth Client Credentials (server-to-server)        │
│  • No API Gateway endpoint exposed for event processing                     │
│  • All communication within AWS backbone                                    │
│                                                                              │
│  ┌──────────────────────────────────────────────────────────────────────┐  │
│  │  EventBridge → SQS → Lambda → Bedrock Agent                          │  │
│  │       ↑                            │                                  │  │
│  │  SF Event Relay                    ▼                                  │  │
│  │  (Authenticated)           Salesforce API                             │  │
│  │                           (OAuth 2.0 CC Flow)                         │  │
│  └──────────────────────────────────────────────────────────────────────┘  │
│                                                                              │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  EXTERNAL (Optional - Testing/Admin API)                                    │
│  ─────────────────────────────────────────                                  │
│  • API Gateway deployed for testing/admin use                               │
│  • Can be restricted to Rackspace IPs                                       │
│  • Rate limited                                                              │
│  • Audit logging enabled                                                    │
│                                                                              │
│  Endpoints:                                                                  │
│  • GET  /health        - Health check                                       │
│  • POST /agent/invoke  - Direct agent invocation                           │
│  • POST /case/analyze  - Case analysis                                      │
│  • POST /kb/search     - KB vector search                                   │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## Lambda Code for Event Processing

The event-driven Lambda (`case-analysis-processor`) invokes the Bedrock Agent:

```python
import json
import boto3
import os

bedrock_agent_runtime = boto3.client("bedrock-agent-runtime", region_name="us-east-1")

AGENT_ID = os.environ.get("BEDROCK_AGENT_ID")
AGENT_ALIAS_ID = os.environ.get("BEDROCK_AGENT_ALIAS_ID")

def lambda_handler(event, context):
    """Process Case creation events from SQS"""
    for record in event.get("Records", []):
        body = json.loads(record["body"])
        
        # Extract case details from Integration_Event__e
        case_id = body.get("detail", {}).get("payload", {}).get("Record_Id__c")
        subject = body.get("detail", {}).get("payload", {}).get("Subject__c", "")
        description = body.get("detail", {}).get("payload", {}).get("Description__c", "")
        
        # Build analysis prompt
        prompt = f"""Analyze this new Salesforce case:
        
Case ID: {case_id}
Subject: {subject}
Description: {description}

Search the Knowledge Base and provide:
1. Issue summary
2. Self-resolution steps (if applicable)
3. Similar cases found
4. Recommendation (self-resolvable or needs admin)"""
        
        # Invoke Bedrock Agent
        response = bedrock_agent_runtime.invoke_agent(
            agentId=AGENT_ID,
            agentAliasId=AGENT_ALIAS_ID,
            sessionId=f"case-{case_id}",
            inputText=prompt,
        )
        
        # Process streaming response
        result = ""
        for event in response["completion"]:
            if "chunk" in event:
                chunk_bytes = event["chunk"].get("bytes")
                if chunk_bytes:
                    result += chunk_bytes.decode("utf-8")
        
        # Update Salesforce Case with analysis
        update_salesforce_case(case_id, result)
    
    return {"statusCode": 200}


def update_salesforce_case(case_id, analysis):
    """Update Case with AI analysis via Salesforce API"""
    # Implementation: OAuth + PATCH to Salesforce REST API
    pass
```

---

## Implementation Checklist

### Phase 1: Salesforce Setup
- [ ] Create custom fields on Case object:
  - `Agent_Analysis__c` (Long Text Area 32000)
  - `Agent_Analysis_Status__c` (Picklist: Pending, Completed, Failed, Not_Applicable)
  - `Agent_Analyzed_Date__c` (DateTime)
  - `Self_Resolvable__c` (Checkbox)
- [ ] Create new Status values: `Agent_Analysis`, `Admin_Router`, `Self_Resolved`
- [ ] Create/Update Case trigger to publish `Integration_Event__e`
- [ ] Verify Event Relay `AWS_Integration_UAT_TEST` is working
- [ ] Create Connected App for Lambda callback (Client Credentials)
- [ ] Create email alert workflow for analysis completion

### Phase 2: AWS Infrastructure (Terraform)
- [ ] Deploy Bedrock Agent + KB association (done in this project!)
- [ ] Create EventBridge rule for Case events
- [ ] Create SQS queue + DLQ
- [ ] Create Lambda processor function (case-analysis-processor)
- [ ] Configure Lambda environment variables:
  - `BEDROCK_AGENT_ID`
  - `BEDROCK_AGENT_ALIAS_ID`
  - `SF_CLIENT_ID`, `SF_CLIENT_SECRET` (from Secrets Manager)
- [ ] Set up CloudWatch alarms

### Phase 3: Knowledge Base Population
- [ ] Export closed cases with resolutions (last 2 years)
- [ ] Export Knowledge Articles
- [ ] Format and upload to S3
- [ ] Trigger KB ingestion
- [ ] Validate search results

### Phase 4: Testing & Validation
- [ ] Test with sample cases in UAT
- [ ] Validate analysis quality
- [ ] Test status transitions
- [ ] Test email notifications
- [ ] Load test (100 cases/hour)
- [ ] Validate DLQ handling

### Phase 5: Production Rollout
- [ ] Deploy to production Salesforce org
- [ ] Configure production Event Relay
- [ ] Deploy production AWS infrastructure
- [ ] Monitor and tune

---

## Quick Reference Commands

```bash
# Check Event Relay status
sf data query -q "SELECT Id, DeveloperName, State FROM EventRelayConfig" -o UATDEC25 --use-tooling-api

# Publish test event
sf apex run -f scripts/test_platform_event.apex -o UATDEC25

# Query recent closed cases with resolutions
sf data query -q "SELECT CaseNumber, Subject, DP_Resolution__c FROM Case WHERE IsClosed=true AND DP_Resolution__c!=null LIMIT 10" -o UATDEC25

# Test the agent API (after deployment)
API_URL=$(cd terraform && terraform output -raw api_gateway_url)

curl -s "${API_URL}/health" | jq

curl -s -X POST "${API_URL}/agent/invoke" \
  -H "Content-Type: application/json" \
  -d '{"prompt": "Analyze case: Subject=Need FF access, Description=User needs FinancialForce access to log time"}' | jq

# Test case analysis endpoint
curl -s -X POST "${API_URL}/case/analyze" \
  -H "Content-Type: application/json" \
  -d '{
    "case_number": "00012345",
    "subject": "Need FF access",
    "description": "User needs FinancialForce access to log time",
    "priority": "Medium"
  }' | jq

# Check SQS queue depth (after event-driven infra deployed)
aws sqs get-queue-attributes \
  --queue-url https://sqs.us-east-1.amazonaws.com/914296863611/case-analysis-queue \
  --attribute-names ApproximateNumberOfMessages \
  --profile sandbox4
```

---

## Cost Estimation (1,000 cases/day)

| Service | Usage | Est. Cost/Month |
|---------|-------|-----------------|
| EventBridge | 30K events | $0.30 |
| SQS | 30K messages | $0.01 |
| Lambda (processor) | 30K × 30s | $3.00 |
| Lambda (API) | 5K invocations | $0.50 |
| Bedrock Agent | 35K invocations | ~$25.00 |
| API Gateway | 5K requests | $0.02 |
| Salesforce API | 30K calls | Included |
| **Total** | | **~$30/month** |

---

## Related Documentation

- [Main README](../README.md) - Project overview and deployment
- [Migration Analysis](MIGRATION_AGENTCORE_TO_BEDROCK_AGENT.md) - AgentCore → Bedrock Agent migration

---

**Version:** 2.0.0 (Bedrock Agent)  
**Created:** January 2026  
**Last Updated:** January 22, 2026  
**Author:** Platform Engineering Team
