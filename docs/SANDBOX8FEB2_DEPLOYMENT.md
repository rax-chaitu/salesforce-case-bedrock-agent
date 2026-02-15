# SANDBOX8FEB2 Deployment Summary

**Date**: February 2, 2026  
**AWS Account**: 321528231668  
**Profile**: SANDBOX8FEB2  
**Project**: sf-case-analysis

---

## ✅ Deployment Status: SUCCESSFUL

All resources deployed with proper naming convention (`sf-case-analysis-*`).

---

## 📋 Configuration

### Terraform Variables
- **Project Name**: `sf-case-analysis` (follows naming convention)
- **AWS Region**: `us-east-1`
- **Knowledge Base ID**: `LJBM50RR0V`
- **AppFlow Name**: `SFCASESCLOSEDAPPFLOWKB`
- **KB Data Source ID**: `KZDT2HX02R`
- **Event Relay ARN**: `aws.partner/salesforce.com/00DgP0000023yjFUAQ/0YLgP00000072gDWAQ`

### Salesforce JWT Auth
- **Secret Name**: `salesforce-inttest-sandbox-jwt` (matches Glue pattern)
- **Environment**: `inttest`
- **Client ID**: `3MVG9oD5dheCKJmnu__qyWw0zs75_PBFRCGa3Dy1a5MrjSsiNEWJUpSRp3TK1vXWaFTBm1.aknc36wtUUV44n`
- **Username**: `sfdc_tes_admin@rackspace.com.uat`

---

## 🎯 Deployed Resources

### Bedrock Agent
- **Agent ID**: `0EMJPMPLKC`
- **Agent Name**: `sf-case-analysis`
- **DEV Alias ID**: `IHOFWOSJ16`
- **PROD Alias ID**: `8HOIGQAAGN`
- **Foundation Model**: `amazon.nova-pro-v1:0`
- **Knowledge Base**: `LJBM50RR0V` (associated)

### Lambda Function
- **Function Name**: `sf-case-analysis-api`
- **Runtime**: Python 3.11
- **Memory**: 512 MB
- **Timeout**: 300 seconds (5 minutes)
- **Concurrency**: 20
- **Handler**: `handler.lambda_handler`

### API Gateway
- **API URL**: `https://ugfloakho6.execute-api.us-east-1.amazonaws.com/prod`
- **Stage**: `prod`
- **Auth**: AWS IAM (requires SigV4)
- **Throttling**: 100 req/sec, burst 50

### SQS Queues
- **Main Queue**: `sf-case-analysis-case-analysis`
- **DLQ**: `sf-case-analysis-case-analysis-dlq`
- **Queue URL**: `https://sqs.us-east-1.amazonaws.com/321528231668/sf-case-analysis-case-analysis`
- **DLQ URL**: `https://sqs.us-east-1.amazonaws.com/321528231668/sf-case-analysis-case-analysis-dlq`

### EventBridge
- **Partner Bus**: `aws.partner/salesforce.com/00DgP0000023yjFUAQ/0YLgP00000072gDWAQ`
- **Rule**: `sf-case-analysis-case-created`
- **Target**: SQS Queue

### Step Functions (KB Sync)
- **State Machine**: `sf-case-analysis-kb-sync`
- **ARN**: `arn:aws:states:us-east-1:321528231668:stateMachine:sf-case-analysis-kb-sync`
- **Schedule**: Monday & Wednesday at 2am UTC
- **Schedule Rule ARN**: `arn:aws:events:us-east-1:321528231668:rule/sf-case-analysis-kb-sync-schedule`

---

## 🔄 Next Steps

### 1. Activate Event Relay in Salesforce
```
Setup → Event Relays → Your Relay → Activate
Partner Event Source: aws.partner/salesforce.com/00DgP0000023yjFUAQ/0YLgP00000072gDWAQ
```

### 2. Test the Agent
```bash
# Set AWS profile
export AWS_PROFILE=SANDBOX8FEB2
eval $(aws configure export-credentials --profile SANDBOX8FEB2 --format env)

# Test API health
awscurl --service execute-api --region us-east-1 --profile SANDBOX8FEB2 \
  "https://ugfloakho6.execute-api.us-east-1.amazonaws.com/prod/health"

# Test agent invoke
awscurl --service execute-api --region us-east-1 --profile SANDBOX8FEB2 \
  -X POST "https://ugfloakho6.execute-api.us-east-1.amazonaws.com/prod/agent/invoke" \
  -H "Content-Type: application/json" \
  -d '{"prompt": "Search for login issues"}'
```

### 3. Create Test Case in Salesforce
```bash
sf data create record --sobject Case \
  --values "Subject='Test AI Analysis' Description='User cannot login' Priority='High' Origin='Web'" \
  --target-org SANDBOX8FEB2 --json
```

### 4. Monitor Lambda Logs
```bash
aws logs tail /aws/lambda/sf-case-analysis-api --since 10m --format short --follow
```

### 5. Trigger KB Sync Manually (Optional)
```bash
aws stepfunctions start-execution \
  --state-machine-arn arn:aws:states:us-east-1:321528231668:stateMachine:sf-case-analysis-kb-sync \
  --name manual-sync-$(date +%s)
```

---

## 📊 Resource Naming Convention

All resources follow the `sf-{object}-{function}` pattern:

| Resource Type | Name |
|---------------|------|
| Agent | `sf-case-analysis` |
| Lambda | `sf-case-analysis-api` |
| SQS Queue | `sf-case-analysis-case-analysis` |
| DLQ | `sf-case-analysis-case-analysis-dlq` |
| EventBridge Rule | `sf-case-analysis-case-created` |
| Step Function | `sf-case-analysis-kb-sync` |
| IAM Roles | `sf-case-analysis-*-role` |
| CloudWatch Logs | `/aws/lambda/sf-case-analysis-api` |

**JWT Secret**: `salesforce-inttest-sandbox-jwt` (matches Glue pattern, not renamed)

---

## 🔐 IAM Permissions

Lambda has permissions for:
- Bedrock Agent invocation
- Bedrock KB retrieval
- Secrets Manager (salesforce-*)
- SQS read/write
- CloudWatch Logs
- X-Ray tracing

---

## 📝 Important Notes

1. **Old State Files Backed Up**: 
   - `terraform.tfstate.SANDBOX5JAN27.backup`
   - `terraform.tfstate.backup.SANDBOX5JAN27`

2. **Event Relay**: Must be activated in Salesforce Setup

3. **API Authentication**: Requires AWS SigV4 signing (use `awscurl`)

4. **KB Sync**: Runs automatically Mon/Wed at 2am UTC, or trigger manually

5. **AppFlow**: Ensure `SFCASESCLOSEDAPPFLOWKB` is configured and working

---

## 🐛 Troubleshooting

### Check Lambda Logs
```bash
aws logs tail /aws/lambda/sf-case-analysis-api --since 30m
```

### Check SQS Messages
```bash
aws sqs get-queue-attributes \
  --queue-url https://sqs.us-east-1.amazonaws.com/321528231668/sf-case-analysis-case-analysis \
  --attribute-names ApproximateNumberOfMessages
```

### Check DLQ for Failed Messages
```bash
aws sqs receive-message \
  --queue-url https://sqs.us-east-1.amazonaws.com/321528231668/sf-case-analysis-case-analysis-dlq
```

### Test Bedrock Agent Directly
```bash
aws bedrock-agent-runtime invoke-agent \
  --agent-id 0EMJPMPLKC \
  --agent-alias-id IHOFWOSJ16 \
  --session-id test-$(date +%s) \
  --input-text "Analyze case about login issues" \
  /tmp/agent-response.txt
```

---

## 📚 Documentation

- [Deployment Guide](docs/deployment/DEPLOYMENT_GUIDE.md)
- [Quick Redeploy](docs/deployment/QUICK_REDEPLOY.md)
- [Naming Conventions](docs/NAMING_CONVENTIONS.md)
- [Event Architecture](docs/architecture/EVENT_DRIVEN_ARCHITECTURE.md)
- [AppFlow KB Sync](docs/knowledge-base/APPFLOW_KB_SYNC_SETUP.md)
