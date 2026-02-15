# Salesforce Bedrock Agent - Steering Guide

---
inclusion: always
---

## Project Overview

This is a **Salesforce AI Case Analysis Agent** using Amazon Bedrock Agent with Knowledge Base integration. Event-driven architecture: Salesforce Case → Platform Event → Event Relay → EventBridge → SQS → Lambda → Bedrock Agent → Update Case.

**Tech Stack**: Python 3.12, Terraform, AWS (Lambda, Bedrock, SQS, EventBridge), Salesforce (Apex, Platform Events)

## Agent Behavior Rules

1. **Always check AWS credentials first** - Run `aws sts get-caller-identity` before any AWS operation
2. **Ask for profile selection** on first AWS interaction each session
3. **Use python3** explicitly (never `python`)
4. **Check terraform.tfvars** before suggesting Terraform changes
5. **Verify Lambda dependencies** are in `lambda_package/` before deployment
6. **Parse nested JSON** correctly for Salesforce Event Relay payloads
7. **Use awscurl** for API Gateway testing (requires IAM auth)
8. **Check CloudWatch logs** when debugging Lambda issues

---

## 🎯 Common Workflows

### Workflow 1: Deploy Code Changes

```bash
# 1. Verify credentials
aws sts get-caller-identity --profile SANDBOX5JAN27

# 2. Quick Lambda deploy (bypasses Terraform)
cd lambda/case_processor
cd lambda_package && zip -rq /tmp/lambda.zip .
cd .. && zip -j /tmp/lambda.zip handler.py bedrock_client.py salesforce_client.py __init__.py
aws lambda update-function-code --function-name salesforceagent-api --zip-file fileb:///tmp/lambda.zip

# 3. Test
awscurl --service execute-api --region us-east-1 "$API_URL/health"

# 4. Check logs
aws logs tail /aws/lambda/salesforceagent-api --since 5m --format short
```

### Workflow 2: Update Bedrock Agent Instructions

```bash
# 1. Edit terraform/modules/bedrock_agent/main.tf
# 2. Apply changes
cd terraform && terraform apply -target=module.bedrock_agent

# 3. Prepare new version
aws bedrock-agent prepare-agent --agent-id $AGENT_ID

# 4. Test
awscurl -X POST "$API_URL/agent/invoke" \
  -H "Content-Type: application/json" \
  -d '{"prompt": "test query"}'
```

### Workflow 3: Sync Knowledge Base

```bash
# Manual sync
aws bedrock-agent start-ingestion-job \
  --knowledge-base-id $KB_ID \
  --data-source-id $DATASOURCE_ID

# Or trigger Step Functions (if enabled)
aws stepfunctions start-execution \
  --state-machine-arn "arn:aws:states:us-east-1:ACCOUNT:stateMachine:salesforceagent-kb-sync"
```

### Workflow 4: Debug Event Flow

```bash
# 1. Check SQS queue
aws sqs get-queue-attributes \
  --queue-url $SQS_QUEUE_URL \
  --attribute-names ApproximateNumberOfMessages

# 2. Check Lambda logs
aws logs tail /aws/lambda/salesforceagent-api --since 10m --format short

# 3. Test with manual SQS message
aws sqs send-message --queue-url $SQS_QUEUE_URL \
  --message-body '{"detail":{"payload":{"Record_Id__c":"500xxx","Payload__c":"{\"Case_Number__c\":\"00151191\"}"}}}'

# 4. Check Salesforce Case update
sf data query --query "SELECT AI_Analysis__c FROM Case WHERE CaseNumber='00151191'" --target-org UATDEC25
```

---

## ⚠️ CRITICAL: AWS Authentication

### AGENT INSTRUCTION: Profile Selection

**On FIRST interaction of each day involving AWS/Terraform commands:**

1. List available AWS profiles:
   ```bash
   aws configure list-profiles
   ```

2. **ASK the user**: "Which AWS profile should I use today? Here are your available profiles: [list them]"

3. **Remember the selected profile** for the entire session/day

4. Use the selected profile for ALL subsequent AWS commands

### Setting AWS Profile

```bash
# List available profiles
aws configure list-profiles

# Set the selected profile (replace YOUR_PROFILE with user's choice)
export AWS_PROFILE=YOUR_PROFILE
eval $(aws configure export-credentials --profile YOUR_PROFILE --format env)

# Or use the helper script (edit AWS_PROFILE in script first)
source terraform/aws-auth.sh
```

### Token Expiration Fix

If you see `InvalidClientTokenId`, `ExpiredToken`, or `AccessDenied`:

```bash
aws sso login --profile YOUR_PROFILE
eval $(aws configure export-credentials --profile YOUR_PROFILE --format env)
```

### Verify Credentials

```bash
aws sts get-caller-identity
# Should show correct account ID
```

---

## 🔧 Known Issues & Solutions

### 1. Salesforce OAuth - Client Credentials NOT Supported

**WRONG** (Salesforce doesn't support this):
```python
response = requests.post(token_url, data={
    "grant_type": "client_credentials",
    "client_id": consumer_key,
    "client_secret": consumer_secret
})
```

**CORRECT** - Use JWT Bearer Token flow:
```python
payload = {
    "iss": client_id,
    "sub": username,
    "aud": login_url,  # https://test.salesforce.com for sandbox
    "exp": int(time.time()) + 180
}
jwt_token = jwt.encode(payload, private_key, algorithm="RS256")
response = requests.post(f"{login_url}/services/oauth2/token", data={
    "grant_type": "urn:ietf:params:oauth:grant-type:jwt-bearer",
    "assertion": jwt_token
})
```

### 2. Lambda Dependencies Not Loading

**Problem**: `No module named 'jwt'` or similar

**Solution**: Deploy Lambda directly (bypasses Terraform archive issues):
```bash
cd lambda/case_processor
cd lambda_package && zip -rq /tmp/lambda.zip .
cd .. && zip -j /tmp/lambda.zip handler.py bedrock_client.py salesforce_client.py __init__.py
aws lambda update-function-code --function-name salesforceagent-api --zip-file fileb:///tmp/lambda.zip
```

### 3. Event Relay Payload - Double-Nested JSON

**Structure** (Payload__c is a JSON STRING inside JSON):
```json
{
  "detail": {
    "payload": {
      "Record_Id__c": "500xxx",
      "Payload__c": "{\"Case_Number__c\":\"00151198\",\"Subject__c\":\"Test\"}"
    }
  }
}
```

**Parse correctly**:
```python
event_payload = detail.get("payload", {})
case_id = event_payload.get("Record_Id__c")
payload_str = event_payload.get("Payload__c", "{}")
case_data = json.loads(payload_str)  # Parse the nested JSON STRING
```

### 4. KMS Permission Error on Secrets Manager

**Problem**: Lambda can't decrypt secret

**Solution**: Recreate secret with AWS-managed key (not custom KMS):
```bash
aws secretsmanager delete-secret --secret-id OLD_ARN --force-delete-without-recovery
aws secretsmanager create-secret \
  --name "salesforce-inttest-sandbox-jwt" \
  --secret-string '{"client_id":"...","username":"...","private_key":"..."}'
# No --kms-key-id = uses AWS-managed key
```

### 5. Bedrock Agent Not Using Knowledge Base

**Problem**: Agent says "I do not have access to a Knowledge Base"

**Solution**: Update alias to use latest prepared version:
```bash
aws bedrock-agent update-agent-alias \
  --agent-id $AGENT_ID \
  --agent-alias-id $ALIAS_ID \
  --agent-alias-name DEV \
  --routing-configuration '[{"agentVersion":"LATEST"}]'
```

### 6. API Gateway Requires IAM Auth

**Problem**: `curl` returns 403 Forbidden

**Solution**: Use `awscurl` with SigV4:
```bash
awscurl --service execute-api --region us-east-1 --profile $AWS_PROFILE \
  -X POST "$API_URL/agent/invoke" \
  -H "Content-Type: application/json" \
  -d '{"prompt": "Search for login issues"}'
```

Or install awscurl: `pip3 install awscurl`

---

## 📁 Key Files Reference

| File | Purpose |
|------|---------|
| `terraform/terraform.tfvars` | Your configuration (NEVER commit) |
| `terraform/terraform.tfvars.example` | Template for tfvars |
| `lambda/case_processor/handler.py` | Lambda handler (SQS + API) |
| `lambda/case_processor/salesforce_client.py` | SF JWT auth client |
| `lambda/case_processor/bedrock_client.py` | Bedrock Agent client |
| `salesforce.key` | JWT private key (DO NOT COMMIT) |
| `salesforce.crt` | JWT certificate (upload to SF) |

---

## 🚀 Quick Commands

### Terraform Operations

```bash
# Always authenticate first!
source terraform/aws-auth.sh

cd terraform
terraform init
terraform plan
terraform apply
terraform output  # Get API URL, Agent ID, etc.
```

### Lambda Deployment (Quick - Bypasses Terraform)

```bash
cd lambda/case_processor
cd lambda_package && zip -rq /tmp/lambda.zip .
cd .. && zip -j /tmp/lambda.zip handler.py bedrock_client.py salesforce_client.py __init__.py
aws lambda update-function-code --function-name salesforceagent-api --zip-file fileb:///tmp/lambda.zip
```

### Check Lambda Logs

```bash
aws logs tail /aws/lambda/salesforceagent-api --since 10m --format short
```

### Sync Knowledge Base

```bash
aws bedrock-agent start-ingestion-job \
  --knowledge-base-id $KB_ID \
  --data-source-id $DATASOURCE_ID
```

### Test API Endpoints

```bash
# Health check
awscurl --service execute-api --region us-east-1 --profile $AWS_PROFILE \
  "$API_URL/health"

# Agent invoke
awscurl --service execute-api --region us-east-1 --profile $AWS_PROFILE \
  -X POST "$API_URL/agent/invoke" \
  -H "Content-Type: application/json" \
  -d '{"prompt": "Search for login issues"}'
```

### Create Test Case in Salesforce

```bash
sf data create record --sobject Case \
  --values "Subject='Test AI Analysis' Description='User cannot login' Priority='High' Origin='Web'" \
  --target-org UATDEC25 --json
```

---

## 🏗️ Architecture Quick Reference

```
Salesforce Case → CaseHandler.cls → Integration_Event__e → Event Relay →
EventBridge Partner Bus → SQS Queue → Lambda → Bedrock Agent (+ KB) →
Lambda → Update Case AI Fields in Salesforce
```

### Key AWS Resources

| Resource | Name/ID |
|----------|---------|
| Lambda | `salesforceagent-api` |
| SQS Queue | `salesforceagent-case-analysis` |
| Bedrock Agent | Check `terraform output` |
| Knowledge Base | Check `terraform output` |
| API Gateway | Check `terraform output` |
| SF Secret | `salesforce-inttest-sandbox-jwt` |

---

## 📋 Terraform Troubleshooting

### State Lock Error

```bash
terraform force-unlock LOCK_ID
```

### Resource Already Exists

```bash
terraform import aws_sqs_queue.main https://sqs.us-east-1.amazonaws.com/ACCOUNT/queue-name
```

### Ignore Lambda Code Changes (Prevent Overwrites)

Already configured in `terraform/modules/lambda/main.tf`:
```hcl
lifecycle {
  ignore_changes = [filename, source_code_hash]
}
```

---

## 🔐 Salesforce JWT Setup Checklist

1. Generate RSA key pair:
   ```bash
   openssl genrsa -out salesforce.key 2048
   openssl req -new -x509 -key salesforce.key -out salesforce.crt -days 365
   ```

2. Salesforce Connected App:
   - Enable OAuth, scopes: `api`, `refresh_token`
   - Check "Use digital signatures", upload `salesforce.crt`
   - Manage → Edit Policies → "Admin approved users are pre-authorized"
   - Add integration user's profile

3. AWS Secret (JSON format):
   ```json
   {
     "client_id": "3MVG9...",
     "username": "user@company.com.sandbox",
     "private_key": "-----BEGIN PRIVATE KEY-----\n...\n-----END PRIVATE KEY-----"
   }
   ```

---

## 🔄 Terraform Drift Workflow

**Drift** = AWS resources differ from your Terraform code (someone changed AWS manually)

### Step 1: Detect Drift

```bash
cd terraform
terraform refresh   # Pull latest AWS state
terraform plan      # Shows differences
```

Output shows:
- `~` = Will be updated (drift detected)
- `+` = Will be created
- `-` = Will be destroyed

### Step 2: Review Each Drifted Resource

```bash
# See what's currently in AWS for a specific resource
terraform state show module.bedrock_agent.aws_bedrockagent_agent.agent
terraform state show module.lambda.aws_lambda_function.api
```

### Step 3: Decide - Keep or Override

**To KEEP manual change** → Update your `.tf` file:
```bash
# Copy values from state show output to your .tf file
# Then plan again - should show no changes for that resource
```

**To OVERRIDE manual change** → Just apply:
```bash
terraform apply
# AWS will match your code
```

### Step 4: Selective Apply (Advanced)

Override specific resources only:
```bash
# Override only Lambda, keep other drift
terraform apply -target=module.lambda.aws_lambda_function.api

# Override only SQS
terraform apply -target=module.sqs.aws_sqs_queue.main
```

### Common Drift Scenarios

| Scenario | Action |
|----------|--------|
| Lambda timeout changed in console | Override (apply) or update `lambda_timeout` in tfvars |
| Agent instructions tweaked in Bedrock console | Copy from `state show` to `bedrock_agent/main.tf` |
| Secret value rotated | Usually ignore - use `lifecycle { ignore_changes }` |
| Someone added tags manually | Override or add tags to your .tf |

### Prevent Future Drift

For resources that change outside Terraform:
```hcl
lifecycle {
  ignore_changes = [tags, description]  # Won't override these
}
```

---

## 🔄 Terraform Drift Workflow

**Drift** = AWS resources differ from your Terraform code (someone changed AWS manually)

### Step 1: Detect Drift

```bash
cd terraform
terraform refresh   # Pull latest AWS state
terraform plan      # Shows differences
```

Output shows:
- `~` = Will be updated (drift detected)
- `+` = Will be created
- `-` = Will be destroyed

### Step 2: Review Each Drifted Resource

```bash
# See what's currently in AWS for a specific resource
terraform state show module.bedrock_agent.aws_bedrockagent_agent.agent
terraform state show module.lambda.aws_lambda_function.api
```

### Step 3: Decide - Keep or Override

**To KEEP manual change** → Update your `.tf` file:
```bash
# Copy values from state show output to your .tf file
# Then plan again - should show no changes for that resource
```

**To OVERRIDE manual change** → Just apply:
```bash
terraform apply
# AWS will match your code
```

### Step 4: Selective Apply (Advanced)

Override specific resources only:
```bash
# Override only Lambda, keep other drift
terraform apply -target=module.lambda.aws_lambda_function.api

# Override only SQS
terraform apply -target=module.sqs.aws_sqs_queue.main
```

### Common Drift Scenarios

| Scenario | Action |
|----------|--------|
| Lambda timeout changed in console | Override (apply) or update `lambda_timeout` in tfvars |
| Agent instructions tweaked in Bedrock console | Copy from `state show` to `bedrock_agent/main.tf` |
| Secret value rotated | Usually ignore - use `lifecycle { ignore_changes }` |
| Someone added tags manually | Override or add tags to your .tf |

### Prevent Future Drift

For resources that change outside Terraform:
```hcl
lifecycle {
  ignore_changes = [tags, description]  # Won't override these
}
```

---

## 📚 Documentation Reference

| Topic | File |
|-------|------|
| Full deployment | `docs/DEPLOYMENT_GUIDE.md` |
| Quick redeploy | `docs/QUICK_REDEPLOY.md` |
| Troubleshooting | `docs/IMPLEMENTATION_NOTES.md` |
| Event architecture | `docs/EVENT_DRIVEN_ARCHITECTURE.md` |
| AppFlow KB sync | `docs/APPFLOW_KB_SYNC_SETUP.md` |
| Terraform basics | `docs/TERRAFORM_BASICS.md` |
| Naming conventions | `docs/NAMING_CONVENTIONS.md` |
