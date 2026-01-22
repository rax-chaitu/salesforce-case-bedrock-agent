# Quick Redeployment Guide (AWS Sandbox Expiration)

When your AWS sandbox expires but Salesforce Full Sandbox persists.

## What Persists (No Action Needed)
- ✅ Salesforce metadata (Custom Fields, Platform Events, Apex classes)
- ✅ Connected App (Client ID and Secret remain same)
- ✅ Event Relay configuration (just update destination)

## What Needs Redeployment (AWS Only)
- ❌ Knowledge Base
- ❌ Bedrock Agent
- ❌ Lambda Function
- ❌ SQS Queue
- ❌ EventBridge Rules
- ❌ Secrets Manager

---

## Redeployment Steps (30 minutes)

### 1. Create Knowledge Base (AWS Console - 10 min)
```
1. Open Bedrock Console → Knowledge Bases → Create
2. Name: salesforceagent-kb
3. Embeddings: amazon.titan-embed-text-v2:0
4. Upload same case data as before
5. Copy new Knowledge Base ID
```

### 2. Update terraform.tfvars (2 min)
```bash
cd terraform
vim terraform.tfvars
```

Update only these values:
```hcl
aws_profile         = "new-sandbox-profile"  # New AWS profile
knowledge_base_id   = "NEW_KB_ID"            # From step 1
salesforce_event_source = ""                 # Will get after Event Relay update
```

Keep same (from Salesforce):
```hcl
salesforce_instance_url  = "..."  # Same
salesforce_client_id     = "..."  # Same
salesforce_client_secret = "..."  # Same
```

### 3. Deploy AWS Infrastructure (10 min)
```bash
# Set credentials for new sandbox
aws sso login --profile new-sandbox-profile
eval "$(aws configure export-credentials --profile new-sandbox-profile --format env)"

# Deploy
cd terraform
terraform init
terraform plan -out=plan.out
terraform apply plan.out
```

### 4. Associate Partner Event Source in AWS (5 min)

> ⚠️ **Manual step** - Cannot be automated

```
AWS Console:
1. EventBridge → Partner event sources
2. Find: aws.partner/salesforce.com/.../AWS_Sandbox4_Case_AI
3. Status should be "Pending"
4. Click "Associate with event bus"
5. Copy full event source name
```

**Why manual?** Salesforce Event Relay automatically creates the partner event source in your AWS account, but AWS requires you to manually accept/associate it.

### 5. Update terraform.tfvars with Event Source (2 min)
```bash
vim terraform/terraform.tfvars
```

Add:
```hcl
salesforce_event_source = "aws.partner/salesforce.com/00D.../AWS_Sandbox4_Case_AI"
```

Apply:
```bash
terraform apply
```

### 6. Test (5 min)
```bash
# Test API
API_URL=$(terraform output -raw api_gateway_url)
curl "${API_URL}/health"

# Test RAG
curl -X POST "${API_URL}/agent/invoke" \
  -H "Content-Type: application/json" \
  -d '{"prompt": "What are common password reset solutions?"}'

# Test end-to-end: Create Case in Salesforce
# Verify AI fields populate
```

---

## Checklist

- [ ] Create Knowledge Base in new AWS sandbox
- [ ] Update `terraform.tfvars` with new KB ID and AWS profile
- [ ] Run `terraform apply`
- [ ] Update Event Relay destination in Salesforce
- [ ] Get new event source name from AWS Console
- [ ] Update `terraform.tfvars` with event source
- [ ] Run `terraform apply` again
- [ ] Test API endpoints
- [ ] Test Case creation in Salesforce

---

## Time Savings

| Task | First Deployment | Redeployment |
|------|------------------|--------------|
| Salesforce Setup | 30 min | 0 min ✅ |
| AWS Setup | 30 min | 30 min |
| **Total** | **60 min** | **30 min** |

**50% faster** because Salesforce Full Sandbox persists! 🚀
