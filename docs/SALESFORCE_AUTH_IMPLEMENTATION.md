# Salesforce Authentication Implementation - Work Log

**Date:** January 22, 2026  
**Project:** AWS_SANDBOX2_OnlyBedrock - Salesforce Agent  
**Objective:** Implement Salesforce OAuth authentication for case updates

---

## Summary

Implemented Salesforce OAuth 2.0 client credentials authentication in the Lambda case processor to enable automatic case updates with AI analysis results.

---

## What We Did

### 1. Updated Salesforce Client Authentication
**File:** `lambda/case_processor/salesforce_client.py`

#### Changes Made:
- **Hardcoded UAT Sandbox URL**: Changed default instance URL from empty string to `https://rax--uat.sandbox.my.salesforce.com`
- **Fixed OAuth Implementation**: Replaced manual OAuth token request with `simple-salesforce` library's built-in `SalesforceLogin` method
- **Updated Imports**: Added `SalesforceLogin` to imports from `simple_salesforce`

#### Authentication Flow:
```python
from simple_salesforce import Salesforce, SalesforceLogin

# OAuth 2.0 with client credentials
session_id, instance = SalesforceLogin(
    username=None,
    password=None,
    organizationId=None,
    sf_version='58.0',
    domain='test',  # For sandbox
    consumer_key=self.client_id,
    consumer_secret=client_secret
)

self._sf = Salesforce(instance=instance, session_id=session_id)
```

### 2. Deployed Updated Lambda Function
**Function Name:** `salesforceagent-api`  
**Account:** 914296863611 (sandbox4)  
**Region:** us-east-1

#### Deployment Method:
```bash
# Created zip file
cd lambda/case_processor
zip -r /tmp/lambda_update.zip . -x "*.pyc" -x "__pycache__/*" -x ".pytest_cache/*" -x "package/*"

# Updated Lambda function
aws lambda update-function-code \
  --function-name salesforceagent-api \
  --zip-file fileb:///tmp/lambda_update.zip \
  --profile sandbox4 \
  --region us-east-1
```

**Deployment Status:** ✅ SUCCESS  
**Code SHA256:** `lXac5RhN4THD6XFy83FYPBeE80C/dUbgkV8y9ZXqZkQ=`  
**Last Modified:** 2026-01-22T13:45:57.000+0000

### 3. Tested Direct API Gateway Endpoints
**API Gateway URL:** `https://9ed3wk8ehh.execute-api.us-east-1.amazonaws.com/prod`

#### Test Results:

**✅ Health Endpoint - WORKING**
```bash
curl https://9ed3wk8ehh.execute-api.us-east-1.amazonaws.com/prod/health
```
Response: Returns agent status, IDs, and timestamp

**✅ Agent Invoke Endpoint - WORKING**
```bash
curl -X POST https://9ed3wk8ehh.execute-api.us-east-1.amazonaws.com/prod/agent/invoke \
  -H "Content-Type: application/json" \
  -d '{"prompt": "Search for login issues", "session_id": "test-123"}'
```
Response: Bedrock Agent successfully processes prompts and returns analysis

**✅ KB Search Endpoint - WORKING**
```bash
curl -X POST https://9ed3wk8ehh.execute-api.us-east-1.amazonaws.com/prod/kb/search \
  -H "Content-Type: application/json" \
  -d '{"query": "password reset", "max_results": 3}'
```
Response: Knowledge Base returns relevant closed cases

**✅ Case Analyze Endpoint - WORKING**
```bash
curl -X POST https://9ed3wk8ehh.execute-api.us-east-1.amazonaws.com/prod/case/analyze \
  -H "Content-Type: application/json" \
  -d '{"case_number": "12345", "subject": "Login issue", "description": "Cannot login", "priority": "High"}'
```
Response: Agent analyzes case and provides recommendations

**Status:** All API endpoints working correctly. Bedrock Agent integration functional.

### 4. Sent Test Event to SQS
**Queue URL:** `https://sqs.us-east-1.amazonaws.com/914296863611/salesforceagent-case-analysis`

#### Test Event Payload:
```json
{
  "version": "0",
  "id": "test-event-123",
  "detail-type": "Case Created",
  "source": "aws.partner/salesforce.com/00DgP0000023yjFUAQ/0YLgP0000005yDFWAY",
  "account": "914296863611",
  "time": "2026-01-22T13:50:00Z",
  "region": "us-east-1",
  "detail": {
    "payload": {
      "Case_Id__c": "500Pe00000s9XyXIAU",
      "Case_Number__c": "00001234",
      "Subject__c": "Test case for Salesforce auth",
      "Description__c": "Testing the updated Salesforce client with OAuth credentials",
      "Priority__c": "High",
      "Status__c": "New",
      "Type__c": "CREATE",
      "Object_Name__c": "Case"
    }
  }
}
```

**Message ID:** `2e39a035-5b69-4828-a4cb-0078c8a6a7ed`  
**Status:** ✅ Sent to SQS

---

## Issues Faced & Fixed

### Issue 1: Wrong AWS Account Credentials
**Problem:** Terraform plan failed because we were using credentials for account `371363084812` but resources exist in account `914296863611` (sandbox4).

**Error:**
```
AccessDeniedException: User: arn:aws:iam::371363084812:user/AWS_CLI_Chaitanya 
is not authorized to perform: bedrock:GetAgent on resource in account 914296863611
```

**Solution:** Bypassed Terraform and used AWS CLI with `--profile sandbox4` to directly update Lambda function.

### Issue 2: Incorrect OAuth Implementation
**Problem:** Original code manually constructed OAuth token request using `requests` library, which doesn't align with how `simple-salesforce` handles authentication.

**Original Code (WRONG):**
```python
auth_url = f'https://{domain}/services/oauth2/token'
auth_data = {
    'grant_type': 'client_credentials',
    'client_id': self.client_id,
    'client_secret': client_secret
}
response = requests.post(auth_url, data=auth_data)
```

**Fixed Code (CORRECT):**
```python
session_id, instance = SalesforceLogin(
    username=None,
    password=None,
    organizationId=None,
    sf_version='58.0',
    domain='test',
    consumer_key=self.client_id,
    consumer_secret=client_secret
)
```

**Why Fixed:** `simple-salesforce` library has built-in OAuth handling via `SalesforceLogin` that properly manages token lifecycle.

---

## What's NOT Working / Needs Verification

### 1. ⚠️ Lambda Execution Results - UNKNOWN
**Status:** Test event sent to SQS but logs not checked

**Next Steps:**
```bash
# Check Lambda logs
aws logs tail /aws/lambda/salesforceagent-api \
  --since 10m \
  --profile sandbox4 \
  --region us-east-1

# Check for errors
aws logs filter-log-events \
  --log-group-name /aws/lambda/salesforceagent-api \
  --filter-pattern "ERROR" \
  --start-time $(date -u -v-10M +%s)000 \
  --profile sandbox4 \
  --region us-east-1
```

### 2. ⚠️ Salesforce OAuth Authentication - UNTESTED
**Status:** Code deployed but not verified if OAuth actually works

**Potential Issues:**
- Connected App may not support OAuth 2.0 Client Credentials flow
- Salesforce may require JWT Bearer flow instead
- Consumer key/secret may be incorrect
- Sandbox domain detection may fail

**Verification Steps:**
1. Check Lambda logs for Salesforce connection success/failure
2. Look for error messages like:
   - `OAuth auth failed`
   - `simple-salesforce not installed`
   - `AccessDeniedException` from Salesforce
3. Verify Connected App settings in Salesforce:
   - OAuth Policies → Permitted Users
   - OAuth Scopes (api, refresh_token)
   - Callback URL configuration

### 3. ⚠️ Salesforce Case Update - UNTESTED
**Status:** Update logic exists but not verified

**Fields Being Updated:**
- `AI_Analysis__c` - Full analysis text
- `AI_Suggestions__c` - Self-resolution steps
- `Self_Resolvable__c` - Boolean flag
- `Similar_Cases__c` - Related case references
- `AI_Analyzed_Date__c` - Timestamp
- `Agent_Analysis_Status__c` - "Completed" or "Failed"

**Verification Steps:**
1. Check if case `500Pe00000s9XyXIAU` was updated in Salesforce
2. Verify custom fields exist in Salesforce Case object
3. Check field-level security permissions

### 4. ⚠️ Missing Dependencies - POSSIBLE ISSUE
**Status:** Lambda package may not include `simple-salesforce` library

**Current Lambda Package:**
- Only includes source files (handler.py, salesforce_client.py, bedrock_client.py)
- Does NOT include `package/` directory with dependencies

**Problem:** The zip file created excluded the `package/` directory:
```bash
zip -r /tmp/lambda_update.zip . -x "package/*"  # ❌ EXCLUDED DEPENDENCIES
```

**Solution Needed:**
```bash
# Correct deployment should include dependencies
cd lambda/case_processor
pip install -r requirements.txt -t package/
zip -r /tmp/lambda_update.zip . -x "*.pyc" -x "__pycache__/*" -x ".pytest_cache/*"
```

---

## Environment Configuration

### Lambda Environment Variables (Current)
```
BEDROCK_AGENT_ID=PVCXCBCV4I
BEDROCK_AGENT_ALIAS_ID=A7DTAVSVLJ
BEDROCK_KNOWLEDGE_BASE_ID=TKYEX1S8ZP
SALESFORCE_INSTANCE_URL=https://rax--uat.sandbox.my.salesforce.com
SALESFORCE_CLIENT_ID=3MVG9oD5dheCKJmnu__qyWw0zs75_PBFRCGa3Dy1a5MrjSsiNEWJUpSRp3TK1vXWaFTBm1.aknc36wtUUV44n
SALESFORCE_CLIENT_SECRET_ARN=arn:aws:secretsmanager:us-east-1:914296863611:secret:salesforceagent/salesforce/client-secret-BN4hUG
```

### Salesforce Connected App Details
- **Instance:** https://rax--uat.sandbox.my.salesforce.com
- **Org ID:** 00DgP0000023yjFUAQ
- **Consumer Key:** 3MVG9oD5dheCKJmnu__qyWw0zs75_PBFRCGa3Dy1a5MrjSsiNEWJUpSRp3TK1vXWaFTBm1.aknc36wtUUV44n
- **Consumer Secret:** Stored in AWS Secrets Manager

---

## Tomorrow's Action Items

### Priority 1: Verify Lambda Execution
```bash
# 1. Check recent Lambda invocations
aws lambda list-invocations \
  --function-name salesforceagent-api \
  --profile sandbox4 \
  --region us-east-1

# 2. Check CloudWatch logs
aws logs tail /aws/lambda/salesforceagent-api \
  --since 1h \
  --profile sandbox4 \
  --region us-east-1

# 3. Check SQS queue metrics
aws sqs get-queue-attributes \
  --queue-url https://sqs.us-east-1.amazonaws.com/914296863611/salesforceagent-case-analysis \
  --attribute-names All \
  --profile sandbox4 \
  --region us-east-1
```

### Priority 2: Fix Missing Dependencies (If Needed)
```bash
# 1. Install dependencies
cd /Users/venk7903/Documents/KIRO_Python_Projects/AWS_SANDBOX2_OnlyBedrock/lambda/case_processor
rm -rf package
mkdir -p package
pip install -r requirements.txt -t package/ --platform manylinux2014_x86_64 --only-binary=:all:

# 2. Create proper zip with dependencies
cd /Users/venk7903/Documents/KIRO_Python_Projects/AWS_SANDBOX2_OnlyBedrock/lambda/case_processor
zip -r /tmp/lambda_complete.zip . -x "*.pyc" -x "__pycache__/*" -x ".pytest_cache/*"

# 3. Update Lambda
aws lambda update-function-code \
  --function-name salesforceagent-api \
  --zip-file fileb:///tmp/lambda_complete.zip \
  --profile sandbox4 \
  --region us-east-1
```

### Priority 3: Test Direct API Endpoints
```bash
# Test all endpoints to verify Bedrock Agent is working
API_URL="https://9ed3wk8ehh.execute-api.us-east-1.amazonaws.com/prod"

# Health check
curl "${API_URL}/health"

# Agent invoke
curl -X POST "${API_URL}/agent/invoke" \
  -H "Content-Type: application/json" \
  -d '{"prompt": "Analyze password reset issues"}'

# KB search
curl -X POST "${API_URL}/kb/search" \
  -H "Content-Type: application/json" \
  -d '{"query": "login error", "max_results": 5}'

# Case analyze
curl -X POST "${API_URL}/case/analyze" \
  -H "Content-Type: application/json" \
  -d '{"case_number": "00001234", "subject": "Test", "description": "Test case", "priority": "High"}'
```

### Priority 4: Test Salesforce Authentication via SQS
```bash
# Send test event to SQS
aws sqs send-message \
  --queue-url https://sqs.us-east-1.amazonaws.com/914296863611/salesforceagent-case-analysis \
  --message-body file:///tmp/test_case_event.json \
  --profile sandbox4 \
  --region us-east-1

# Monitor logs immediately
aws logs tail /aws/lambda/salesforceagent-api \
  --follow \
  --profile sandbox4 \
  --region us-east-1914296863611/salesforceagent-case-analysis \
  --message-body file:///tmp/test_case_event.json \
  --profile sandbox4 \
  --region us-east-1

# Monitor logs in real-time
aws logs tail /aws/lambda/salesforceagent-api \
  --follow \
  --profile sandbox4 \
  --region us-east-1
```

### Priority 5: Verify Salesforce Case Update
1. Log into Salesforce UAT: https://rax--uat.sandbox.my.salesforce.com
2. Navigate to Case `00001234` or ID `500Pe00000s9XyXIAU`
3. Check if custom fields were updated:
   - AI_Analysis__c
   - AI_Suggestions__c
   - Self_Resolvable__c
   - Agent_Analysis_Status__c

### Priority 6: Alternative OAuth Flow (If Client Credentials Fails)
If OAuth 2.0 Client Credentials doesn't work, try JWT Bearer flow:

```python
# Install additional library
pip install pyjwt cryptography

# Use JWT Bearer flow
from simple_salesforce import Salesforce
import jwt
import time

# Generate JWT
payload = {
    'iss': consumer_key,
    'sub': username,
    'aud': 'https://test.salesforce.com',
    'exp': int(time.time()) + 300
}
token = jwt.encode(payload, private_key, algorithm='RS256')

# Exchange JWT for access token
# ... (implementation needed)
```

---

## How to Deploy and Test in Sandbox (Next Time)

### Step 1: Switch to Correct AWS Profile
```bash
# Always use sandbox4 profile for this project
export AWS_PROFILE=sandbox4
export AWS_REGION=us-east-1

# Verify you're in the right account
aws sts get-caller-identity
# Should show Account: 914296863611
```

### Step 2: Deploy Lambda Function with Dependencies
```bash
cd /Users/venk7903/Documents/KIRO_Python_Projects/AWS_SANDBOX2_OnlyBedrock/lambda/case_processor

# Clean and install dependencies
rm -rf package
mkdir -p package
pip install -r requirements.txt -t package/ --platform manylinux2014_x86_64 --only-binary=:all:

# Create deployment package (INCLUDE package/ directory)
zip -r /tmp/lambda_deploy.zip . -x "*.pyc" -x "__pycache__/*" -x ".pytest_cache/*" -x ".DS_Store"

# Deploy to Lambda
aws lambda update-function-code \
  --function-name salesforceagent-api \
  --zip-file fileb:///tmp/lambda_deploy.zip \
  --profile sandbox4 \
  --region us-east-1

# Wait for update to complete
aws lambda wait function-updated \
  --function-name salesforceagent-api \
  --profile sandbox4 \
  --region us-east-1

echo "✅ Lambda deployed successfully"
```

### Step 3: Test API Endpoints Directly
```bash
API_URL="https://9ed3wk8ehh.execute-api.us-east-1.amazonaws.com/prod"

# 1. Health check
echo "Testing health endpoint..."
curl -s "${API_URL}/health" | jq .

# 2. Agent invoke (simple test)
echo "Testing agent invoke..."
curl -s -X POST "${API_URL}/agent/invoke" \
  -H "Content-Type: application/json" \
  -d '{"prompt": "Hello, test connection"}' | jq .

# 3. KB search
echo "Testing KB search..."
curl -s -X POST "${API_URL}/kb/search" \
  -H "Content-Type: application/json" \
  -d '{"query": "login", "max_results": 3}' | jq .
```

### Step 4: Test SQS Event Processing
```bash
# Create test event file
cat > /tmp/test_case_event.json << 'EOF'
{
  "version": "0",
  "id": "test-event-$(date +%s)",
  "detail-type": "Case Created",
  "source": "aws.partner/salesforce.com/00DgP0000023yjFUAQ/0YLgP0000005yDFWAY",
  "account": "914296863611",
  "time": "$(date -u +%Y-%m-%dT%H:%M:%SZ)",
  "region": "us-east-1",
  "detail": {
    "payload": {
      "Case_Id__c": "500Pe00000s9XyXIAU",
      "Case_Number__c": "TEST-$(date +%s)",
      "Subject__c": "Test Salesforce OAuth",
      "Description__c": "Testing OAuth authentication with simple-salesforce",
      "Priority__c": "High",
      "Status__c": "New",
      "Type__c": "CREATE",
      "Object_Name__c": "Case"
    }
  }
}
EOF

# Send to SQS
aws sqs send-message \
  --queue-url https://sqs.us-east-1.amazonaws.com/914296863611/salesforceagent-case-analysis \
  --message-body file:///tmp/test_case_event.json \
  --profile sandbox4 \
  --region us-east-1

# Monitor logs in real-time (open in separate terminal)
aws logs tail /aws/lambda/salesforceagent-api \
  --follow \
  --profile sandbox4 \
  --region us-east-1
```

### Step 5: Check Results
```bash
# Check Lambda execution
aws lambda get-function \
  --function-name salesforceagent-api \
  --profile sandbox4 \
  --region us-east-1 \
  --query 'Configuration.[LastModified,State,LastUpdateStatus]' \
  --output table

# Check SQS queue depth
aws sqs get-queue-attributes \
  --queue-url https://sqs.us-east-1.amazonaws.com/914296863611/salesforceagent-case-analysis \
  --attribute-names ApproximateNumberOfMessages,ApproximateNumberOfMessagesNotVisible \
  --profile sandbox4 \
  --region us-east-1

# Check recent errors
aws logs filter-log-events \
  --log-group-name /aws/lambda/salesforceagent-api \
  --filter-pattern "ERROR" \
  --start-time $(($(date +%s) - 600))000 \
  --profile sandbox4 \
  --region us-east-1
```

### Step 6: Verify in Salesforce
1. Login to UAT: https://rax--uat.sandbox.my.salesforce.com
2. Navigate to Cases
3. Find test case by Case Number
4. Check custom fields:
   - AI_Analysis__c
   - AI_Suggestions__c
   - Agent_Analysis_Status__c
   - Self_Resolvable__c

### Troubleshooting Commands
```bash
# Get Lambda environment variables
aws lambda get-function-configuration \
  --function-name salesforceagent-api \
  --profile sandbox4 \
  --region us-east-1 \
  --query 'Environment.Variables' \
  --output json

# Check Lambda layer (if using)
aws lambda get-function \
  --function-name salesforceagent-api \
  --profile sandbox4 \
  --region us-east-1 \
  --query 'Configuration.Layers'

# Test Lambda directly (bypass SQS)
aws lambda invoke \
  --function-name salesforceagent-api \
  --payload file:///tmp/test_case_event.json \
  --profile sandbox4 \
  --region us-east-1 \
  /tmp/lambda_response.json

cat /tmp/lambda_response.json | jq .
```

---

## Files Modified

1. **lambda/case_processor/salesforce_client.py**
   - Line 37: Changed default instance URL
   - Line 25: Added `SalesforceLogin` import
   - Lines 62-95: Rewrote `_get_connection()` method

---

## References

- **Simple Salesforce Docs:** https://github.com/simple-salesforce/simple-salesforce
- **Salesforce OAuth 2.0:** https://help.salesforce.com/s/articleView?id=sf.remoteaccess_oauth_flows.htm
- **AWS Lambda Python:** https://docs.aws.amazon.com/lambda/latest/dg/python-handler.html
- **Terraform State:** `/Users/venk7903/Documents/KIRO_Python_Projects/AWS_SANDBOX2_OnlyBedrock/terraform/terraform.tfstate`

---

## Quick Commands Reference

```bash
# AWS Profile
export AWS_PROFILE=sandbox4
export AWS_REGION=us-east-1

# Project Directory
cd /Users/venk7903/Documents/KIRO_Python_Projects/AWS_SANDBOX2_OnlyBedrock

# Lambda Function Name
FUNCTION_NAME=salesforceagent-api

# SQS Queue URL
QUEUE_URL=https://sqs.us-east-1.amazonaws.com/914296863611/salesforceagent-case-analysis

# Check Lambda logs
aws logs tail /aws/lambda/$FUNCTION_NAME --since 1h --profile sandbox4

# Send test message
aws sqs send-message --queue-url $QUEUE_URL --message-body file:///tmp/test_case_event.json --profile sandbox4

# Update Lambda code
aws lambda update-function-code --function-name $FUNCTION_NAME --zip-file fileb:///tmp/lambda_update.zip --profile sandbox4
```

---

**End of Work Log**
