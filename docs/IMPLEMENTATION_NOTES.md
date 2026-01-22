# Salesforce AI Case Analysis - Implementation Notes

## Architecture Overview

```
Salesforce Case → CaseHandler.cls → Integration_Event__e → Event Relay → 
EventBridge Partner Bus → SQS Queue → Lambda → Bedrock Agent (+ KB) → 
Lambda → Update Case AI Fields in Salesforce
```

## Issues Fixed & Solutions

### 1. Salesforce OAuth Authentication

**Problem**: Salesforce does NOT support OAuth 2.0 Client Credentials flow  
**Solution**: JWT Bearer Token flow with X.509 certificate

**Setup Steps**:
```bash
# 1. Generate RSA key pair
openssl genrsa -out salesforce.key 2048

# 2. Create self-signed certificate
openssl req -new -x509 -key salesforce.key -out salesforce.crt -days 365 \
  -subj "/CN=SalesforceAgent/O=Rackspace/C=US"

# 3. Upload salesforce.crt to Connected App in Salesforce Setup
# 4. Store private key in AWS Secrets Manager (use AWS-managed key, NOT custom KMS)
aws secretsmanager create-secret \
  --name "salesforceagent/salesforce/jwt-private-key" \
  --secret-string file://salesforce.key

# 5. Pre-authorize user in Connected App:
#    Manage → Edit Policies → "Admin approved users are pre-authorized"
#    Add user profile to Connected App
```

### 2. Lambda Dependencies Not Loading

**Problem**: `No module named 'jwt'` error  
**Root Cause**: Terraform `archive_file` wasn't detecting package changes

**Solution**: Direct Lambda deployment bypassing Terraform:
```bash
cd lambda/case_processor/package && zip -rq /tmp/lambda.zip .
cd .. && zip -j /tmp/lambda.zip handler.py bedrock_client.py salesforce_client.py __init__.py
eval $(aws configure export-credentials --profile sandbox4 --format env)
aws lambda update-function-code --function-name salesforceagent-api --zip-file fileb:///tmp/lambda.zip
```

### 3. Event Relay Payload Structure (CRITICAL)

**Problem**: Lambda couldn't parse case data - getting "Missing case number"  
**Root Cause**: Event Relay structure is double-nested with JSON string inside

**Event Relay Structure**:
```json
{
  "detail": {
    "payload": {
      "Record_Id__c": "500gP00000CknWtQAJ",
      "Payload__c": "{\"Case_Number__c\":\"00151198\",\"Subject__c\":\"Test\",\"Description__c\":\"...\",\"Type__c\":\"Problem\",\"Priority__c\":\"High\"}"
    }
  }
}
```

**Solution** (handler.py):
```python
event_payload = detail.get("payload", {})
case_id = event_payload.get("Record_Id__c")
payload_str = event_payload.get("Payload__c", "{}")
case_data = json.loads(payload_str)  # Parse nested JSON STRING
case_number = case_data.get("Case_Number__c", "")
```

### 4. KMS Permission Error

**Problem**: Lambda couldn't read Secrets Manager secret - AccessDeniedException  
**Root Cause**: Secret was created with custom KMS key, Lambda role didn't have decrypt permission

**Solution**: Delete and recreate secret with AWS-managed key (default):
```bash
aws secretsmanager delete-secret --secret-id OLD_SECRET_ARN --force-delete-without-recovery
aws secretsmanager create-secret \
  --name "salesforceagent/salesforce/jwt-private-key" \
  --secret-string file://salesforce.key
# No --kms-key-id = uses AWS-managed key
```

### 5. Bedrock Agent Not Using Knowledge Base

**Problem**: Agent responding "I do not have access to a Knowledge Base"  
**Root Cause**: DEV alias pointed to old agent version without KB association

**Solution**: Update alias to use latest prepared version:
```bash
# Check current version
aws bedrock-agent get-agent --agent-id PVCXCBCV4I --query 'agent.agentVersion'

# Update alias to use version with KB
aws bedrock-agent update-agent-alias \
  --agent-id PVCXCBCV4I \
  --agent-alias-id LTXGEQVZ2P \
  --agent-alias-name DEV \
  --routing-configuration '[{"agentVersion":"6"}]'
```

---

## Key Configuration Values

| Component | Value |
|-----------|-------|
| AWS Account | 914296863611 |
| AWS Profile | sandbox4 |
| AWS Region | us-east-1 |
| Salesforce Instance | https://rax--uat.sandbox.my.salesforce.com |
| Salesforce Username | sfdc_tes_admin@rackspace.com.uat |
| SF Org Alias | UATDEC25 |
| Consumer Key | 3MVG9oD5dheCKJmnu__qyWw0zs75_PBFRCGa3Dy1a5MrjSsiNEWJUpSRp3TK1vXWaFTBm1.aknc36wtUUV44n |
| Bedrock Agent ID | PVCXCBCV4I |
| Bedrock Agent Alias (DEV) | LTXGEQVZ2P |
| Knowledge Base ID | TKYEX1S8ZP |
| Data Source ID | VRYU906VZJ |
| SQS Queue | salesforceagent-case-analysis |
| API Gateway | https://9ed3wk8ehh.execute-api.us-east-1.amazonaws.com/prod |
| Private Key ARN | arn:aws:secretsmanager:us-east-1:914296863611:secret:salesforceagent/salesforce/jwt-private-key-2KZifp |

---

## Salesforce Components

### Platform Event: Integration_Event__e

| Field | Type | Purpose |
|-------|------|---------|
| Record_Id__c | Text | Case ID (18-char) |
| Payload__c | Long Text | JSON string with case data |
| Type__c | Text | Event type (CREATE/UPDATE/DELETE) |
| Object_Name__c | Text | Object API name |

### Case AI Fields

| Field | Type | Purpose |
|-------|------|---------|
| AI_Analysis__c | Long Text Area | Summary + Recommendation |
| AI_Suggestions__c | Long Text Area | Resolution steps |
| Self_Resolvable__c | Checkbox | Can user self-resolve? |
| Similar_Cases__c | Long Text Area | Related cases from KB |
| Agent_Analysis_Status__c | Picklist | Pending/Completed/Failed |
| AI_Analyzed_Date__c | DateTime | When analyzed |

### CaseHandler.cls (Apex Trigger Handler)

Publishes Integration_Event__e on Case insert with:
- Record_Id__c = Case.Id
- Payload__c = JSON.serialize(case fields)
- Type__c = 'CREATE'
- Object_Name__c = 'Case'

### Event Relay Configuration

- **Name**: AWS_Sandbox4_Case_AI
- **Channel**: Case_AI_Analysis_Channel__chn
- **State**: Must be `RUN` (start via Setup → Event Relay)
- **Partner Event Bus**: aws.partner/salesforce.com/00DgP0000023yjFUAQ/0YLgP0000005yDFWAY

---

## Quick Commands

### Test Lambda Health
```bash
eval $(aws configure export-credentials --profile sandbox4 --format env)
curl https://9ed3wk8ehh.execute-api.us-east-1.amazonaws.com/prod/health
```

### Create Test Case in Salesforce
```bash
sf data create record --sobject Case \
  --values "Subject='Test AI Analysis' Description='User cannot login' Priority='High' Origin='Web'" \
  --target-org UATDEC25 --json
```

### Check Lambda Logs
```bash
eval $(aws configure export-credentials --profile sandbox4 --format env)
aws logs tail /aws/lambda/salesforceagent-api --since 10m --format short
```

### Redeploy Lambda (Quick)
```bash
cd lambda/case_processor/package && zip -rq /tmp/lambda.zip .
cd .. && zip -j /tmp/lambda.zip handler.py bedrock_client.py salesforce_client.py __init__.py
eval $(aws configure export-credentials --profile sandbox4 --format env)
aws lambda update-function-code --function-name salesforceagent-api --zip-file fileb:///tmp/lambda.zip
```

### Sync Knowledge Base
```bash
eval $(aws configure export-credentials --profile sandbox4 --format env)
aws bedrock-agent start-ingestion-job --knowledge-base-id TKYEX1S8ZP --data-source-id VRYU906VZJ
```

### Check SQS Queue
```bash
eval $(aws configure export-credentials --profile sandbox4 --format env)
aws sqs get-queue-attributes \
  --queue-url https://sqs.us-east-1.amazonaws.com/914296863611/salesforceagent-case-analysis \
  --attribute-names ApproximateNumberOfMessages,ApproximateNumberOfMessagesNotVisible
```

### Test Direct SQS Message
```bash
eval $(aws configure export-credentials --profile sandbox4 --format env)
aws sqs send-message \
  --queue-url https://sqs.us-east-1.amazonaws.com/914296863611/salesforceagent-case-analysis \
  --message-body '{"version":"0","id":"test","detail-type":"Case Created","source":"test","detail":{"payload":{"Record_Id__c":"500gP00000CknWtQAJ","Payload__c":"{\"Case_Number__c\":\"00151191\",\"Subject__c\":\"Test\",\"Description__c\":\"Testing\",\"Type__c\":\"Problem\",\"Priority__c\":\"High\"}"}}}'
```

---

## Terraform State Management

### Ignore Changes (Prevent Overwrites)

Lambda and Bedrock alias have `lifecycle { ignore_changes }` to prevent Terraform from overwriting working deployments:

```hcl
# terraform/modules/lambda/main.tf
lifecycle {
  ignore_changes = [filename, source_code_hash]
}

# terraform/modules/bedrock_agent/main.tf  
lifecycle {
  ignore_changes = [routing_configuration]
}
```

### Import Existing Resources

If deploying to environment with existing resources:
```bash
terraform import module.secrets.aws_secretsmanager_secret.salesforce_private_key "ARN"
terraform import module.secrets.aws_secretsmanager_secret_version.salesforce_private_key[0] "ARN|VERSION_ID"
terraform import aws_lambda_permission.api_gw "function-name/statement-id"
```

---

## Known Limitations

1. **KB Search by Case ID**: Vector search doesn't work well with exact Case IDs - search by description keywords instead
2. **Event Relay Latency**: ~2-5 seconds from Case creation to Lambda invocation
3. **Agent Response Time**: ~15 seconds for full analysis with KB search
4. **Session TTL**: Bedrock Agent sessions expire after 30 minutes (configurable)
