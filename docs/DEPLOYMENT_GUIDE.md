# Salesforce Agent - Complete Deployment Guide

## Prerequisites
- AWS CLI configured with SSO
- Terraform >= 1.2
- Salesforce org with admin access
- Python 3.x (for data formatting)

---

## Part 1: AWS Setup (Manual Steps)

### Step 1: Create Knowledge Base (MANUAL - Required)
> ⚠️ Must be done via AWS Console due to SCP restrictions

1. Go to [Amazon Bedrock Console](https://console.aws.amazon.com/bedrock) → Knowledge Bases
2. Click **Create knowledge base**
3. Configure:
   - **Name**: `salesforceagent-kb` (or any name)
   - **Embeddings model**: `amazon.titan-embed-text-v2:0`
   - **Vector store**: `Quick create a new vector store` (uses S3 Vectors)
4. Add data source:
   - Create S3 bucket or use existing
   - Upload formatted case data (see Data Preparation below)
5. **Copy the Knowledge Base ID** (e.g., `<KB_ID>`)
6. **Copy the S3 bucket name** for data source

### Step 2: Prepare Case Data for KB
```bash
# Format CSV to include Case IDs in text
python3 << 'EOF'
import csv

with open('cases.csv', 'r') as f:
    reader = csv.DictReader(f)
    with open('formatted_cases.txt', 'w') as out:
        for row in reader:
            case_id = row.get('Id', '')
            description = row.get('Description', '')
            resolution = row.get('Case_Closure_Notes__c', '')
            
            if case_id and case_id.startswith('500'):
                text = f"""Case ID: {case_id}

Description: {description}

Resolution: {resolution}

---
"""
                out.write(text)
EOF

# Upload to KB S3 bucket
aws s3 cp formatted_cases.txt s3://YOUR_KB_BUCKET/ --profile YOUR_PROFILE

# Sync KB
aws bedrock-agent start-ingestion-job \
  --knowledge-base-id YOUR_KB_ID \
  --data-source-id YOUR_DATA_SOURCE_ID \
  --region us-east-1 \
  --profile YOUR_PROFILE
```

---

## Part 2: Terraform Deployment

### Step 1: Configure Variables
```bash
cd terraform
cp terraform.tfvars.example terraform.tfvars
vim terraform.tfvars
```

Update `terraform.tfvars`:
```hcl
project_name      = "salesforceagent"
aws_region        = "us-east-1"
aws_profile       = "YOUR_AWS_PROFILE"  # e.g., sandbox4

# From Step 1
knowledge_base_id = "<KB_ID>"  # Your KB ID

# Agent config
foundation_model   = "amazon.nova-pro-v1:0"
agent_session_ttl  = 1800
lambda_timeout     = 300
log_retention_days = 14

# Salesforce Event Relay (set after Salesforce setup)
salesforce_event_source = ""  # Will update later

# Salesforce API (optional - for case updates)
salesforce_instance_url = ""
salesforce_client_id    = ""
salesforce_client_secret = ""
```

### Step 2: Deploy Infrastructure
```bash
# Login to AWS SSO
aws sso login --profile YOUR_PROFILE

# Export credentials
eval "$(aws configure export-credentials --profile YOUR_PROFILE --format env)"

# Initialize Terraform
terraform init

# Plan
terraform plan -out=plan.out

# Apply
terraform apply plan.out
```

### Step 3: Note Outputs
```bash
terraform output
```

Save these values:
- `api_gateway_url`
- `bedrock_agent_id`
- `bedrock_agent_dev_alias_id`
- `bedrock_agent_prod_alias_id`
- `sqs_queue_url`

---

## Part 3: Salesforce Setup (Manual Steps)

### Step 1: Create Platform Event
1. Setup → Platform Events → New Platform Event
2. Configure:
   - **Label**: `Integration Event`
   - **Plural Label**: `Integration Events`
   - **API Name**: `Integration_Event__e`
3. Add Custom Fields:
   - `Object_Name__c` (Text, 255)
   - `Type__c` (Text, 50)
   - `Record_Id__c` (Text, 18)
   - `Payload__c` (Long Text Area, 32000)

### Step 2: Create Platform Event Channel
1. Setup → Platform Event Channels → New
2. Configure:
   - **Channel Name**: `Case_AI_Analysis_Channel`
   - **API Name**: `Case_AI_Analysis_Channel__chn`

### Step 3: Add Channel Member
1. Open the channel → Channel Members → New
2. Select: `Integration_Event__e`
3. Save

### Step 4: Create Named Credential (for Event Relay)
1. Setup → Named Credentials → New Legacy
2. Configure:
   - **Label**: `AWS Sandbox4`
   - **Name**: `AWS_Sandbox4`
   - **URL**: `https://events.us-east-1.amazonaws.com`
   - **Identity Type**: `Named Principal`
   - **Authentication Protocol**: `AWS Signature Version 4`
   - **AWS Access Key ID**: Your AWS access key
   - **AWS Secret Access Key**: Your AWS secret key
   - **AWS Region**: `us-east-1`
   - **AWS Service**: `events`

### Step 5: Create Event Relay
1. Setup → Event Relays → New Event Relay
2. Configure:
   - **Event Relay Label**: `AWS Sandbox4 Case AI Analysis`
   - **Event Channel**: `Case_AI_Analysis_Channel__chn`
   - **Destination**: `callout:AWS_Sandbox4`
   - **State**: `STOP` (required for initial creation)
3. Save
4. **Copy the Partner Event Source ARN** from the Event Relay details

### Step 6: Associate Partner Event Bus in AWS
```bash
# The ARN looks like: arn:aws:events:us-east-1::event-source/aws.partner/salesforce.com/00DgP.../0YLgP...
# Extract the event source name (everything after event-source/)

export AWS_PROFILE=YOUR_PROFILE
export EVENT_SOURCE="aws.partner/salesforce.com/<SF_ORG_ID>/<EVENT_RELAY_ID>"

# Create event bus
aws events create-event-bus \
  --name "$EVENT_SOURCE" \
  --event-source-name "$EVENT_SOURCE" \
  --region us-east-1
```

### Step 7: Update Terraform with Event Source
```bash
cd terraform
vim terraform.tfvars
```

Update:
```hcl
salesforce_event_source = "aws.partner/salesforce.com/<SF_ORG_ID>/<EVENT_RELAY_ID>"
```

Apply:
```bash
eval "$(aws configure export-credentials --profile YOUR_PROFILE --format env)"
terraform apply -auto-approve
```

### Step 8: Start Event Relay in Salesforce
1. Setup → Event Relays → Open your relay
2. Change **State** from `STOP` to `RUN`
3. Save

---

## Part 4: Testing

### Test 1: Health Check
```bash
API_URL=$(cd terraform && terraform output -raw api_gateway_url)
curl "${API_URL}/health"
```

### Test 2: Agent Invocation
```bash
curl -X POST "${API_URL}/agent/invoke" \
  -H "Content-Type: application/json" \
  -d '{"prompt": "What are common login issues?"}'
```

### Test 3: Case Analysis
```bash
curl -X POST "${API_URL}/case/analyze" \
  -H "Content-Type: application/json" \
  -d '{
    "case_number": "TEST001",
    "subject": "Cannot login to portal",
    "description": "User unable to access after password reset",
    "priority": "High"
  }'
```

### Test 4: KB Search
```bash
curl -X POST "${API_URL}/kb/search" \
  -H "Content-Type: application/json" \
  -d '{"query": "password reset", "max_results": 3}'
```

### Test 5: Event Flow (from Salesforce)
```apex
// Execute in Salesforce Developer Console
Integration_Event__e evt = new Integration_Event__e(
    Object_Name__c = 'Case',
    Type__c = 'CREATE',
    Record_Id__c = '500Pe00000TEST',
    Payload__c = '{"Subject":"Test Case","Description":"Testing event flow"}'
);
EventBus.publish(evt);
```

Check SQS queue:
```bash
export AWS_PROFILE=YOUR_PROFILE
aws sqs receive-message \
  --queue-url $(cd terraform && terraform output -raw sqs_queue_url) \
  --region us-east-1
```

---

## Part 5: Troubleshooting

### Issue: Agent Access Denied
```bash
# Add InvokeAgent permission
export AWS_PROFILE=YOUR_PROFILE
export AGENT_ID=$(cd terraform && terraform output -raw bedrock_agent_id)

aws iam put-role-policy \
  --role-name salesforceagent-lambda-role \
  --policy-name bedrock-invoke-agent \
  --policy-document "{
    \"Version\": \"2012-10-17\",
    \"Statement\": [{
      \"Effect\": \"Allow\",
      \"Action\": \"bedrock:InvokeAgent\",
      \"Resource\": [
        \"arn:aws:bedrock:us-east-1:ACCOUNT_ID:agent/${AGENT_ID}\",
        \"arn:aws:bedrock:us-east-1:ACCOUNT_ID:agent-alias/${AGENT_ID}/*\"
      ]
    }]
  }" \
  --region us-east-1
```

### Issue: KB Access Denied
```bash
# Add KB permissions to agent role
export KB_ID=$(cd terraform && terraform output -raw knowledge_base_id)

aws iam put-role-policy \
  --role-name salesforceagent-bedrock-agent-role \
  --policy-name kb-retrieve \
  --policy-document "{
    \"Version\": \"2012-10-17\",
    \"Statement\": [{
      \"Effect\": \"Allow\",
      \"Action\": [\"bedrock:Retrieve\", \"bedrock:RetrieveAndGenerate\"],
      \"Resource\": \"arn:aws:bedrock:us-east-1:ACCOUNT_ID:knowledge-base/${KB_ID}\"
    }]
  }" \
  --region us-east-1
```

### Issue: Model Access Denied
```bash
aws iam put-role-policy \
  --role-name salesforceagent-bedrock-agent-role \
  --policy-name model-invoke \
  --policy-document '{
    "Version": "2012-10-17",
    "Statement": [{
      "Effect": "Allow",
      "Action": ["bedrock:InvokeModel"],
      "Resource": [
        "arn:aws:bedrock:us-east-1::foundation-model/amazon.nova-pro-v1:0",
        "arn:aws:bedrock:us-east-1::foundation-model/amazon.titan-embed-text-v2:0"
      ]
    }]
  }' \
  --region us-east-1
```

### Issue: Agent Not Prepared
```bash
export AGENT_ID=$(cd terraform && terraform output -raw bedrock_agent_id)
aws bedrock-agent prepare-agent --agent-id $AGENT_ID --region us-east-1
```

---

## Architecture Summary

```
Salesforce → Event Relay → AWS EventBridge Partner Bus → EventBridge Rule → SQS → Lambda → Bedrock Agent → Knowledge Base
                                                                                      ↓
                                                                                 API Gateway (for testing)
```

---

## Resources Created

### AWS Resources (via Terraform)
- Bedrock Agent with DEV/PROD aliases
- Lambda function (API handler)
- API Gateway REST API
- SQS Queue + DLQ
- EventBridge Rule (on partner bus)
- IAM Roles and Policies
- CloudWatch Log Groups
- Secrets Manager (for Salesforce credentials)

### Salesforce Resources (Manual)
- Platform Event: `Integration_Event__e`
- Platform Event Channel: `Case_AI_Analysis_Channel__chn`
- Channel Member
- Named Credential: `AWS_Sandbox4`
- Event Relay

### Manual AWS Resources
- Knowledge Base (Bedrock)
- S3 Bucket (for KB data)
- Partner Event Bus

---

## Cost Estimate (Monthly)

| Component | Cost |
|-----------|------|
| Bedrock Agent | ~$5 |
| Lambda | ~$3 |
| API Gateway | ~$1 |
| SQS | <$1 |
| EventBridge | <$1 |
| Knowledge Base | ~$2 |
| **Total** | **~$12** |

---

## Maintenance

### Update Agent Instructions
```bash
cd terraform/modules/bedrock_agent
vim main.tf  # Edit instruction block
cd ../..
terraform apply
```

### Sync KB Data
```bash
aws bedrock-agent start-ingestion-job \
  --knowledge-base-id YOUR_KB_ID \
  --data-source-id YOUR_DATA_SOURCE_ID \
  --region us-east-1
```

### View Logs
```bash
aws logs tail /aws/lambda/salesforceagent-api --follow --region us-east-1
```

---

## Known Limitations

1. **Case ID Search**: Vector search doesn't work well with exact Case IDs. Users should search by description/symptoms.
2. **KB Data Format**: Case data must be formatted with "Case ID:" prefix in text for better retrieval.
3. **Event Relay State**: Must be created in STOP state, then manually started.
4. **Partner Event Bus**: Must be manually created via CLI after Event Relay setup.

---

## Support

For issues:
1. Check CloudWatch Logs: `/aws/lambda/salesforceagent-api`
2. Verify agent status: `aws bedrock-agent get-agent --agent-id AGENT_ID`
3. Test KB directly: `aws bedrock-agent-runtime retrieve --knowledge-base-id KB_ID --retrieval-query text="query"`
