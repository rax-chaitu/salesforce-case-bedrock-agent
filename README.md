# Salesforce AI Case Analysis Agent

Event-driven AI case analysis using **Amazon Bedrock Agent** with Knowledge Base integration.

## Architecture

```
┌─────────────────────────────────────────────────────────────────────────────────────┐
│                              END-TO-END FLOW                                         │
└─────────────────────────────────────────────────────────────────────────────────────┘

  SALESFORCE                           AWS                                    SALESFORCE
  ─────────                           ───                                    ──────────
                                                                              
  ┌─────────┐    ┌──────────────┐    ┌─────────────┐    ┌─────────┐    ┌─────────────┐
  │  Case   │───▶│  Platform    │───▶│   Event     │───▶│   SQS   │───▶│   Lambda    │
  │ Created │    │   Event      │    │   Relay     │    │  Queue  │    │  Handler    │
  └─────────┘    │Integration_  │    │(EventBridge)│    └─────────┘    └──────┬──────┘
                 │ Event__e     │    └─────────────┘                          │
                 └──────────────┘                                             │
                                                                              ▼
                                                                   ┌─────────────────┐
                                                                   │  Bedrock Agent  │
                                                                   │  (Nova Pro v1)  │
                                                                   │       +         │
                                                                   │ Knowledge Base  │
                                                                   └────────┬────────┘
                                                                            │
                        ┌───────────────────────────────────────────────────┘
                        ▼
  ┌─────────────────────────────────────────────────────────────────────────────────┐
  │                        Case Updated with AI Analysis                             │
  │  • AI_Analysis__c (Summary + Recommendation)                                     │
  │  • AI_Suggestions__c (Resolution Steps)                                          │
  │  • Self_Resolvable__c (Boolean)                                                  │
  │  • Similar_Cases__c (Related Cases from KB)                                      │
  │  • AI_Analysis_Status__c (Completed/Failed)                                      │
  │  • AI_Feedback__c (Agent Feedback Picklist)                                      │
  │  • AI_Feedback_Comments__c (Detailed Feedback)                                   │
  └─────────────────────────────────────────────────────────────────────────────────┘
```

---

## Project History & Migration

### Phase 1: AgentCore Attempt (Abandoned)

Initially tried **Amazon Bedrock AgentCore** - a more complex agent framework:

| Issue | Impact |
|-------|--------|
| Required ECR + Docker containers | Complex deployment |
| 465+ lines of Lambda code | Hard to maintain |
| Multiple dependencies (strands-agents, mcp, bedrock-agentcore) | Version conflicts |
| 8+ IAM policies | Security complexity |
| ~$15/month | Higher cost |

**Decision**: Abandoned AgentCore in favor of simpler **Bedrock Agents**.

### Phase 2: Bedrock Agent (Current)

Migrated to standard **Amazon Bedrock Agents**:

| Aspect | AgentCore (Old) | Bedrock Agent (Current) |
|--------|-----------------|-------------------------|
| Container Management | ECR + Docker | ❌ None |
| Lambda Code | 465 lines | ~150 lines |
| Dependencies | strands-agents, mcp | boto3 only |
| IAM Policies | 8+ | 3 |
| Monthly Cost | ~$15 | ~$8 |

### Phase 3: Salesforce Authentication (JWT)

**Problem**: Tried OAuth 2.0 Client Credentials flow - **Salesforce does NOT support it**.

**Failed Approach**:
```python
# ❌ DOES NOT WORK - Salesforce doesn't support Client Credentials
response = requests.post(token_url, data={
    "grant_type": "client_credentials",
    "client_id": consumer_key,
    "client_secret": consumer_secret
})
```

**Working Solution**: JWT Bearer Token flow with X.509 certificate

```python
# ✅ WORKS - JWT Bearer Token Flow
payload = {
    "iss": client_id,      # Consumer Key from Connected App
    "sub": username,       # Salesforce username
    "aud": login_url,      # https://test.salesforce.com (sandbox)
    "exp": int(time.time()) + 180
}
jwt_token = jwt.encode(payload, private_key, algorithm="RS256")

response = requests.post(f"{login_url}/services/oauth2/token", data={
    "grant_type": "urn:ietf:params:oauth:grant-type:jwt-bearer",
    "assertion": jwt_token
})
```

### Phase 4: Enhanced Context & KB-First Analysis (Feb 2026)

| Enhancement | Impact |
|-------------|--------|
| 11 additional case fields | Richer context (Tool, Support Reason, Department, Segment, etc.) |
| Description limit: 5000 → 32000 chars | Handle complex case descriptions |
| KB-first agent instructions | Agent MUST search KB before responding |
| User permission awareness | Distinguishes admin vs self-service actions |
| HTML hyperlinks in Similar Cases | Clickable case references in Salesforce |
| Plain text formatting | Proper rendering in Long Text Area fields |
| Anti-hallucination rules | Never fabricate case numbers or KB articles |
| KB source citations | Shows which SOP docs informed the recommendation |
| AI Feedback loop | Picklist + comments for agents to rate AI accuracy |
| Permission set | `AI_Case_Analysis_User` - read AI fields, edit feedback |

---

## Knowledge Base Content

The agent's recommendations are powered by **80+ SOP documents** organized by category:

| Category | Count | Examples |
|----------|-------|----------|
| Tools Access | 13 | Revegy, Outreach, Sales Navigator, ZoomInfo |
| Opportunities | 12 | Creation, amounts, SOW approval, debook |
| Knowledge Articles | 18 | Self-service guides, team member requests |
| Users | 5 | Onboarding, terminations, audits |
| Companies | 8 | GAR tool, merges, reassignment |
| Accounts | 5 | Creation, sync with CORE/Encore |
| Leads | 3 | Upload, update owner, reject |

**Location**: `docs/SOP_FOR_DS/`

**Sync**: Automated via AppFlow + Step Functions (see [Automated KB Sync](#automated-kb-sync-appflow--step-functions) section)

---

## Current Deployment

> **Secret Architecture**: Uses consolidated JSON secret matching AWS Glue pattern:
> - Secret name: `salesforce-inttest-sandbox-jwt` (sandbox) or `salesforce-production-jwt` (prod)
> - Format: `{ "client_id", "username", "private_key" }`
> - Lambda reads all credentials from single secret (no separate env vars for each field)

| Resource | Value |
|----------|-------|
| AWS Account | `<YOUR_AWS_ACCOUNT_ID>` |
| Bedrock Agent ID | `<FROM_TERRAFORM_OUTPUT>` |
| Agent Alias (DEV) | `<FROM_TERRAFORM_OUTPUT>` |
| Knowledge Base ID | `<YOUR_KB_ID>` |
| Data Source ID | `<YOUR_DATASOURCE_ID>` |
| API Gateway | `<FROM_TERRAFORM_OUTPUT>` |
| SQS Queue | `salesforceagent-case-analysis` |
| Lambda Function | `salesforceagent-api` |
| SF Secret Name | `salesforce-inttest-sandbox-jwt` |
| SF Environment | `inttest` or `production` |

> **Note**: Get actual values from `terraform output` after deployment.

---

## Testing Options

### Option 1: Create Case in Salesforce (Production Flow)

```bash
sf data create record --sobject Case \
  --values "Subject='Test AI Analysis' Description='User cannot login after password reset' Priority='High' Origin='Web'" \
  --target-org UATDEC25 --json
```

Triggers full flow: Case → Platform Event → Event Relay → SQS → Lambda → Bedrock → Update Case

### Option 2: Manual API Testing (Bypass Salesforce)

```bash
# Health Check
curl $API_GATEWAY_URL/health

# Direct Agent Invocation
curl -X POST $API_GATEWAY_URL/agent/invoke \
  -H "Content-Type: application/json" \
  -d '{"prompt": "Search for cases about login issues"}'

# Case Analysis (without SF update)
curl -X POST $API_GATEWAY_URL/case/analyze \
  -H "Content-Type: application/json" \
  -d '{
    "case_number": "TEST-001",
    "subject": "Cannot login to portal",
    "description": "User reports unable to login after password reset",
    "priority": "High"
  }'

# Direct KB Search
curl -X POST $API_GATEWAY_URL/kb/search \
  -H "Content-Type: application/json" \
  -d '{"query": "password reset", "max_results": 5}'
```

> **Note**: API now requires IAM auth. Use `awscurl` with AWS credentials:
> ```bash
> awscurl --service execute-api --region us-east-1 $API_GATEWAY_URL/health
> ```

### Option 3: Send Message Directly to SQS

```bash
eval $(aws configure export-credentials --profile YOUR_PROFILE --format env)

aws sqs send-message \
  --queue-url $SQS_QUEUE_URL \
  --message-body '{
    "version": "0",
    "id": "test-event",
    "detail-type": "Case Created",
    "source": "aws.partner/salesforce.com",
    "detail": {
      "payload": {
        "Record_Id__c": "500xxxxxxxxxx",
        "Payload__c": "{\"Case_Number__c\":\"00151191\",\"Subject__c\":\"Test Case\",\"Description__c\":\"Testing Lambda\",\"Type__c\":\"Problem\",\"Priority__c\":\"High\"}"
      }
    }
  }'
```

---

## Disabling Manual API Access (Production)

### Option A: Remove API Gateway
Delete `terraform/api_gateway.tf` and redeploy - Lambda only triggered by SQS.

### Option B: Add API Key Requirement
Add to `terraform/api_gateway.tf`:
```hcl
resource "aws_api_gateway_api_key" "api_key" {
  name = "${var.project_name}-api-key"
}
```
Then set `api_key_required = true` on methods.

### Option C: Restrict by IP (WAF)
Add AWS WAF to API Gateway to allow only specific IPs.

---

## Deployment to New Sandbox

### Prerequisites
- AWS Account with Bedrock access enabled
- Salesforce org with Event Relay capability
- Terraform >= 1.2
- SF CLI (`sf`)

### Step 1: Create Knowledge Base (AWS Console - Manual)

> ⚠️ KB must be created manually due to AWS Organization SCP restrictions

1. Open [Amazon Bedrock Console](https://console.aws.amazon.com/bedrock)
2. Navigate to **Knowledge Bases** → **Create**
3. Configure:
   - Name: `salesforceagent-kb`
   - Embeddings: `amazon.titan-embed-text-v2:0`
   - Vector store: `Quick create` (S3 Vectors)
4. Add data source with closed case data
5. **Copy Knowledge Base ID and Data Source ID**

### Step 2: Generate JWT Certificate

```bash
# Generate RSA key pair
openssl genrsa -out salesforce.key 2048

# Create self-signed certificate (valid 1 year)
openssl req -new -x509 -key salesforce.key -out salesforce.crt -days 365 \
  -subj "/CN=SalesforceAgent/O=YourOrg/C=US"
```

### Step 3: Configure Salesforce Connected App

1. Setup → App Manager → New Connected App
2. Enable OAuth Settings:
   - Callback URL: `https://localhost/callback`
   - Selected OAuth Scopes: `api`, `refresh_token`
3. **Use digital signatures**: Upload `salesforce.crt`
4. Save and wait 10 minutes
5. Manage → Edit Policies:
   - Permitted Users: **Admin approved users are pre-authorized**
   - Add user profile
6. **Copy Consumer Key**

### Step 4: Configure Salesforce JWT Secret

The secret format matches AWS Glue jobs for consistency across projects:

**Secret Naming Convention:**
- Sandbox/Inttest: `salesforce-inttest-sandbox-jwt`
- Production: `salesforce-production-jwt`

**Secret Format (JSON):**
```json
{
  "client_id": "3MVG9...",
  "username": "integration-user@company.com.sandbox",
  "private_key": "-----BEGIN PRIVATE KEY-----\n...\n-----END PRIVATE KEY-----"
}
```

**Option A: Create new secret (new AWS accounts)**
```bash
# Terraform handles this automatically when create_sf_secret = true
# Set in terraform.tfvars:
salesforce_environment = "inttest"
create_sf_secret       = true
salesforce_client_id   = "3MVG9..."
salesforce_username    = "your-user@company.com.sandbox"
salesforce_private_key = <<-EOT
-----BEGIN PRIVATE KEY-----
...
-----END PRIVATE KEY-----
EOT
```

**Option B: Use existing secret (main AWS account with Glue)**
```bash
# If salesforce-inttest-sandbox-jwt or salesforce-production-jwt already exists
# Set in terraform.tfvars:
salesforce_environment = "inttest"  # or "production"
create_sf_secret       = false      # Use existing secret
```

### Step 5: Configure Terraform

```bash
cd terraform
cp terraform.tfvars.example terraform.tfvars
```

Edit `terraform.tfvars`:
```hcl
project_name      = "salesforceagent"
aws_region        = "us-east-1"
aws_profile       = "your-aws-profile"
knowledge_base_id = "YOUR_KB_ID"

# Salesforce JWT Config (matches Glue job pattern)
salesforce_environment = "inttest"    # or "production"
create_sf_secret       = true         # false if using existing secret
salesforce_client_id   = "YOUR_CONSUMER_KEY"
salesforce_username    = "your-user@example.com.sandbox"
salesforce_private_key = <<-EOT
-----BEGIN PRIVATE KEY-----
...contents of salesforce.key...
-----END PRIVATE KEY-----
EOT
```

### Step 6: Deploy AWS Infrastructure

```bash
eval $(aws configure export-credentials --profile YOUR_PROFILE --format env)
cd terraform
terraform init
terraform plan
terraform apply
```

### Step 7: Create Salesforce Platform Event

1. Setup → Platform Events → New Platform Event
   - Label: `Integration Event`
   - API Name: `Integration_Event__e`
2. Add Custom Fields:
   - `Object_Name__c` (Text, 255)
   - `Type__c` (Text, 50)
   - `Record_Id__c` (Text, 18)
   - `Payload__c` (Long Text Area, 32000)

### Step 8: Create Platform Event Channel

1. Setup → Platform Event Channels → New
   - Channel Name: `Case_AI_Analysis_Channel`
   - API Name: `Case_AI_Analysis_Channel__chn`
2. Add Channel Member: `Integration_Event__e`

### Step 9: Create Event Relay

1. Setup → Event Relays → New Event Relay
   - Label: `AWS_Sandbox_Case_AI`
   - Event Channel: `Case_AI_Analysis_Channel__chn`
   - State: `STOP` (required initially)
2. Save and **copy Partner Event Source ARN**

### Step 10: Associate Partner Event Bus in AWS

```bash
# Extract event source name from ARN
EVENT_SOURCE="aws.partner/salesforce.com/00DgP.../0YLgP..."

aws events create-event-bus \
  --name "$EVENT_SOURCE" \
  --event-source-name "$EVENT_SOURCE" \
  --region us-east-1
```

### Step 11: Update Terraform with Event Source

```hcl
# terraform.tfvars
salesforce_event_source = "aws.partner/salesforce.com/00DgP.../0YLgP..."
```

```bash
terraform apply
```

### Step 12: Start Event Relay

1. Setup → Event Relays → Open your relay
2. Change State from `STOP` to `RUN`
3. Save

### Step 13: Deploy Salesforce Apex & Permission Set

```bash
sf project deploy start --source-dir salesforce/force-app --target-org YOUR_ORG

# Assign permission set to case agents
sf org assign permset --name AI_Case_Analysis_User --target-org YOUR_ORG
```

### Step 14: Verify

```bash
curl https://YOUR_API_GATEWAY_URL/prod/health

sf data create record --sobject Case \
  --values "Subject='Test' Description='Test' Priority='High' Origin='Web'" \
  --target-org YOUR_ORG
```

---

## Test Results (January 22, 2026)

### ✅ End-to-End Flow Verified

| Step | Status |
|------|--------|
| Case Created → Platform Event | ✅ |
| Event Relay → EventBridge | ✅ |
| EventBridge → SQS | ✅ |
| SQS → Lambda | ✅ |
| Lambda → Bedrock Agent | ✅ |
| Agent → Knowledge Base | ✅ |
| Lambda → Salesforce Update | ✅ |

### Performance

| Operation | Time |
|-----------|------|
| Health Check | ~100ms |
| KB Search | ~1.5s |
| Agent Invocation | ~15s |
| Full E2E | ~20s |

---

## Issues Fixed & Solutions

### 1. Salesforce OAuth - Client Credentials Not Supported
**Solution**: JWT Bearer Token flow with X.509 certificate

### 2. Lambda Dependencies Not Loading (`No module named 'jwt'`)
**Solution**: Direct Lambda deployment bypassing Terraform:
```bash
cd lambda/case_processor/package && zip -rq /tmp/lambda.zip .
cd .. && zip -j /tmp/lambda.zip handler.py bedrock_client.py salesforce_client.py __init__.py
aws lambda update-function-code --function-name salesforceagent-api --zip-file fileb:///tmp/lambda.zip
```

### 3. Event Relay Payload Parsing (Double-Nested JSON)
**Problem**: `Payload__c` is a JSON string inside `detail.payload`
**Solution**: Parse nested JSON in handler.py:
```python
payload_str = event_payload.get("Payload__c", "{}")
case_data = json.loads(payload_str)
```

### 4. KMS Permission Error on Secrets Manager
**Solution**: Recreate secret with AWS-managed key (not custom KMS)

### 5. Bedrock Agent Not Using Knowledge Base
**Solution**: Update alias to use latest prepared version:
```bash
aws bedrock-agent update-agent-alias --agent-id $AGENT_ID --agent-alias-id $ALIAS_ID \
  --agent-alias-name DEV --routing-configuration '[{"agentVersion":"LATEST"}]'
```

See [docs/IMPLEMENTATION_NOTES.md](docs/IMPLEMENTATION_NOTES.md) for detailed troubleshooting.

---

## Quick Commands

### AWS Credentials (IMPORTANT - Tokens Expire!)

AWS SSO tokens expire periodically. If you see `InvalidClientTokenId` error, refresh credentials:

```bash
# Option 1: SSO Login (if using IAM Identity Center)
aws sso login --profile SANDBOX5JAN27

# Option 2: Export credentials to environment (temporary session)
eval $(aws configure export-credentials --profile SANDBOX5JAN27 --format env)

# Verify credentials work
aws sts get-caller-identity --profile SANDBOX5JAN27
```

> **Tip**: Add to your `.zshrc` or `.bashrc`:
> ```bash
> alias awslogin='aws sso login --profile SANDBOX5JAN27 && eval $(aws configure export-credentials --profile SANDBOX5JAN27 --format env)'
> ```

### Common Operations

```bash
# Set AWS credentials
eval $(aws configure export-credentials --profile YOUR_PROFILE --format env)

# Check Lambda logs
aws logs tail /aws/lambda/salesforceagent-api --since 5m --format short

# Redeploy Lambda (quick - bypasses Terraform)
cd lambda/case_processor/package && zip -rq /tmp/lambda.zip .
cd .. && zip -j /tmp/lambda.zip handler.py bedrock_client.py salesforce_client.py __init__.py
aws lambda update-function-code --function-name salesforceagent-api --zip-file fileb:///tmp/lambda.zip

# Sync Knowledge Base
aws bedrock-agent start-ingestion-job --knowledge-base-id $KB_ID --data-source-id $DATASOURCE_ID

# Check SQS queue
aws sqs get-queue-attributes \
  --queue-url $SQS_QUEUE_URL \
  --attribute-names ApproximateNumberOfMessages
```

---

## Files Structure

```
├── README.md                    # This file
├── TEST_RESULTS.md              # Test results
├── docs/
│   ├── IMPLEMENTATION_NOTES.md  # Detailed troubleshooting
│   ├── DEPLOYMENT_GUIDE.md      # Full deployment guide
│   └── ...
├── lambda/
│   └── case_processor/
│       ├── handler.py           # Lambda handler (SQS + API Gateway)
│       ├── bedrock_client.py    # Bedrock Agent client
│       ├── salesforce_client.py # SF JWT auth client
│       └── package/             # Python dependencies
├── salesforce/
│   └── force-app/               # SF metadata (Apex, fields, events)
│       └── main/default/
│           ├── classes/CaseHandler.cls
│           ├── objects/Case/
│           ├── objects/Integration_Event__e/
│           ├── permissionsets/
│           ├── eventRelays/
│           └── platformEventChannels/
├── terraform/
│   ├── main.tf                  # Main config
│   ├── api_gateway.tf           # API Gateway
│   ├── variables.tf             # Variable definitions
│   ├── terraform.tfvars         # Your values
│   └── modules/                 # Modular resources
├── salesforce.key               # JWT private key (DO NOT COMMIT)
└── salesforce.crt               # JWT certificate (upload to SF)
```

---

## Automated KB Sync (AppFlow + Step Functions)

Automates Knowledge Base synchronization from Salesforce using AppFlow and Step Functions.

### Architecture

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                        KB SYNC ORCHESTRATION                                 │
└─────────────────────────────────────────────────────────────────────────────┘

  EventBridge          Step Functions                    AWS Services
  ──────────          ───────────────                   ────────────
                                                        
  ┌──────────┐       ┌─────────────────────────────────────────────────────┐
  │ Schedule │──────▶│  StartAppFlow → Poll → StartKBSync → Poll → Done   │
  │(Daily 2am)│       └──────────┬────────────────────────────┬───────────┘
  └──────────┘                   │                            │
                                 ▼                            ▼
                        ┌───────────────┐            ┌───────────────┐
                        │   AppFlow     │            │  Bedrock KB   │
                        │ (SF → S3)     │            │  Ingestion    │
                        └───────────────┘            └───────────────┘
```

### Prerequisites (IMPORTANT)

> ⚠️ **AppFlow must be created manually in AWS Console first** - OAuth connection to Salesforce requires interactive authentication that cannot be automated via Terraform.

1. **Create AppFlow Flow in AWS Console**:
   - Go to Amazon AppFlow → Create flow
   - Source: Salesforce (authenticate with OAuth)
   - Destination: S3 bucket used by Bedrock KB
   - Trigger type: OnDemand
   - Flow name: `SYNCCASESWITHS3` (or update `appflow_flow_name` variable)

2. **Verify Salesforce Connection**:
   - AppFlow → Connections → Verify Salesforce connection is active
   - Test the flow manually once before enabling automation

### Configuration

Update `terraform/terraform.tfvars`:

```hcl
# AppFlow + Step Functions KB Sync
appflow_flow_name        = "SYNCCASESWITHS3"      # Your AppFlow flow name
kb_data_source_id        = "KZDT2HX02R"           # Bedrock KB Data Source ID
sync_schedule_expression = "cron(0 2 * * ? *)"   # Daily at 2am UTC
enable_scheduled_sync    = false                  # Set true to enable
```

### Deploy

```bash
cd terraform
terraform plan
terraform apply
```

### Manual Execution

Test the state machine before enabling scheduled sync:

```bash
# Start execution
aws stepfunctions start-execution \
  --state-machine-arn "arn:aws:states:us-east-1:ACCOUNT:stateMachine:salesforceagent-kb-sync" \
  --profile SANDBOX5JAN27

# Check execution status
aws stepfunctions describe-execution \
  --execution-arn "arn:aws:states:us-east-1:ACCOUNT:execution:salesforceagent-kb-sync:EXECUTION_ID" \
  --profile SANDBOX5JAN27
```

### Enable Scheduled Sync

Once tested, enable automatic daily sync:

```hcl
# terraform.tfvars
enable_scheduled_sync = true
```

```bash
terraform apply
```

### Terraform Resources Created

| Resource | Description |
|----------|-------------|
| `aws_sfn_state_machine.kb_sync` | Orchestrates AppFlow → KB Sync |
| `aws_iam_role.sfn_role` | IAM role for Step Functions |
| `aws_cloudwatch_log_group.sfn_logs` | Execution logs |
| `aws_cloudwatch_event_rule.kb_sync_schedule` | Daily trigger (if enabled) |
| `aws_iam_role.eventbridge_sfn_role` | IAM role for EventBridge |

---

## Cost Estimate (Monthly)

| Component | Cost |
|-----------|------|
| Bedrock Agent | ~$5 |
| Lambda | ~$3 |
| API Gateway | ~$1 |
| SQS | <$1 |
| Knowledge Base | ~$2 |
| Step Functions | <$1 |
| AppFlow | ~$1 |
| **Total** | **~$14** |

---

## Documentation

| Document | Description |
|----------|-------------|
| [AppFlow KB Sync Setup](docs/APPFLOW_KB_SYNC_SETUP.md) | Complete guide for AppFlow + Step Functions KB sync pipeline |
| [Sandbox Refresh Guide](docs/SANDBOX_REFRESH_GUIDE.md) | Post-refresh setup steps for new sandbox |
| [Salesforce Connected App Guide](docs/SALESFORCE_CONNECTED_APP_GUIDE.md) | Setting up Salesforce Connected App for JWT auth |
| [Salesforce Auth Implementation](docs/SALESFORCE_AUTH_IMPLEMENTATION.md) | JWT Bearer Token flow implementation details |
| [Deployment Guide](docs/DEPLOYMENT_GUIDE.md) | Full deployment instructions |
| [Quick Redeploy](docs/QUICK_REDEPLOY.md) | Fast redeployment commands |
| [Implementation Notes](docs/IMPLEMENTATION_NOTES.md) | Troubleshooting and lessons learned |
| [Event Driven Architecture](docs/EVENT_DRIVEN_ARCHITECTURE.md) | EventBridge + SQS + Lambda flow |
| [API Summary](docs/API_SUMMARY.md) | API Gateway endpoints reference |
| [Terraform Basics](docs/TERRAFORM_BASICS.md) | Terraform commands and tips |
| [Naming Conventions](docs/NAMING_CONVENTIONS.md) | Resource naming standards |

### Historical / Reference

| Document | Description |
|----------|-------------|
| [AgentCore vs Bedrock Agents](docs/AGENTCORE_VS_BEDROCK_AGENTS.md) | Comparison (AgentCore abandoned) |
| [Migration AgentCore to Bedrock](docs/MIGRATION_AGENTCORE_TO_BEDROCK_AGENT.md) | Migration notes |
| [Bedrock KB Salesforce Connector](docs/BEDROCK_KB_SALESFORCE_CONNECTOR.md) | Native SF connector (abandoned - use AppFlow) |
| [README PKCE](docs/README_PKCE.md) | PKCE auth flow (not used) |
| [Salesforce Deployment](docs/SALESFORCE_DEPLOYMENT.md) | SF metadata deployment |

---

## License

Internal use only - Rackspace Technology
