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
  │  • Agent_Analysis_Status__c (Completed/Failed)                                   │
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

---

## Current Deployment (sandbox4)

| Resource | Value |
|----------|-------|
| AWS Account | 914296863611 |
| Bedrock Agent ID | PVCXCBCV4I |
| Agent Alias (DEV) | LTXGEQVZ2P |
| Knowledge Base ID | TKYEX1S8ZP |
| Data Source ID | VRYU906VZJ |
| API Gateway | https://9ed3wk8ehh.execute-api.us-east-1.amazonaws.com/prod |
| SQS Queue | salesforceagent-case-analysis |
| Lambda Function | salesforceagent-api |
| SF Instance | https://rax--uat.sandbox.my.salesforce.com |
| SF Org Alias | UATDEC25 |
| Consumer Key | 3MVG9oD5dheCKJmnu__qyWw0zs75... |
| Private Key ARN | arn:aws:secretsmanager:us-east-1:914296863611:secret:salesforceagent/salesforce/jwt-private-key-2KZifp |

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
curl https://9ed3wk8ehh.execute-api.us-east-1.amazonaws.com/prod/health

# Direct Agent Invocation
curl -X POST https://9ed3wk8ehh.execute-api.us-east-1.amazonaws.com/prod/agent/invoke \
  -H "Content-Type: application/json" \
  -d '{"prompt": "Search for cases about login issues"}'

# Case Analysis (without SF update)
curl -X POST https://9ed3wk8ehh.execute-api.us-east-1.amazonaws.com/prod/case/analyze \
  -H "Content-Type: application/json" \
  -d '{
    "case_number": "TEST-001",
    "subject": "Cannot login to portal",
    "description": "User reports unable to login after password reset",
    "priority": "High"
  }'

# Direct KB Search
curl -X POST https://9ed3wk8ehh.execute-api.us-east-1.amazonaws.com/prod/kb/search \
  -H "Content-Type: application/json" \
  -d '{"query": "password reset", "max_results": 5}'
```

### Option 3: Send Message Directly to SQS

```bash
eval $(aws configure export-credentials --profile sandbox4 --format env)

aws sqs send-message \
  --queue-url https://sqs.us-east-1.amazonaws.com/914296863611/salesforceagent-case-analysis \
  --message-body '{
    "version": "0",
    "id": "test-event",
    "detail-type": "Case Created",
    "source": "aws.partner/salesforce.com",
    "detail": {
      "payload": {
        "Record_Id__c": "500gP00000CknWtQAJ",
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

### Step 4: Store JWT Private Key in Secrets Manager

```bash
eval $(aws configure export-credentials --profile YOUR_PROFILE --format env)

# Create secret with AWS-managed key (NOT custom KMS - avoids permission issues)
aws secretsmanager create-secret \
  --name "salesforceagent/salesforce/jwt-private-key" \
  --secret-string file://salesforce.key
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

# Salesforce JWT Config
salesforce_instance_url = "https://your-instance.sandbox.my.salesforce.com"
salesforce_client_id    = "YOUR_CONSUMER_KEY"
salesforce_username     = "your-user@example.com.sandbox"
```

Update `terraform/main.tf` with secret ARN:
```hcl
salesforce_private_key_arn = "arn:aws:secretsmanager:REGION:ACCOUNT:secret:salesforceagent/salesforce/jwt-private-key-XXXXXX"
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

### Step 13: Deploy Salesforce Apex

```bash
sf project deploy start --source-dir salesforce/force-app --target-org YOUR_ORG
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
aws bedrock-agent update-agent-alias --agent-id PVCXCBCV4I --agent-alias-id LTXGEQVZ2P \
  --agent-alias-name DEV --routing-configuration '[{"agentVersion":"6"}]'
```

See [docs/IMPLEMENTATION_NOTES.md](docs/IMPLEMENTATION_NOTES.md) for detailed troubleshooting.

---

## Quick Commands

```bash
# Set AWS credentials
eval $(aws configure export-credentials --profile sandbox4 --format env)

# Check Lambda logs
aws logs tail /aws/lambda/salesforceagent-api --since 5m --format short

# Redeploy Lambda (quick - bypasses Terraform)
cd lambda/case_processor/package && zip -rq /tmp/lambda.zip .
cd .. && zip -j /tmp/lambda.zip handler.py bedrock_client.py salesforce_client.py __init__.py
aws lambda update-function-code --function-name salesforceagent-api --zip-file fileb:///tmp/lambda.zip

# Sync Knowledge Base
aws bedrock-agent start-ingestion-job --knowledge-base-id TKYEX1S8ZP --data-source-id VRYU906VZJ

# Check SQS queue
aws sqs get-queue-attributes \
  --queue-url https://sqs.us-east-1.amazonaws.com/914296863611/salesforceagent-case-analysis \
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

## Cost Estimate (Monthly)

| Component | Cost |
|-----------|------|
| Bedrock Agent | ~$5 |
| Lambda | ~$3 |
| API Gateway | ~$1 |
| SQS | <$1 |
| Knowledge Base | ~$2 |
| **Total** | **~$12** |

---

## License

Internal use only - Rackspace Technology
