# Bedrock Knowledge Base - Salesforce Connector Setup

## Overview
Amazon Bedrock Knowledge Base can connect directly to Salesforce to index data (Cases, Knowledge Articles, etc.) using the native Salesforce data source connector.

> **Note**: This connector is in preview and only supports OpenSearch Serverless as the vector store.

---

## Prerequisites

### Salesforce Requirements
1. Connected App with OAuth2 Client Credentials Flow enabled
2. Integration user configured as "Run As" user
3. API access enabled for the integration user

### AWS Requirements
1. Secrets Manager secret with Salesforce credentials
2. OpenSearch Serverless collection (auto-created with KB)
3. IAM permissions for Bedrock to access Secrets Manager

---

## Step 1: Configure Salesforce Connected App

### Option A: Modify Existing Connected App (JWT-based)

If you already have a Connected App for JWT Bearer flow:

1. **Enable Client Credentials Flow**:
   - Setup → OAuth and OpenID Connect Settings
   - Toggle ON: **"Allow OAuth Client Credentials Flow"**

2. **Configure Run As User**:
   - Setup → App Manager → Your App → **Manage**
   - Click **Edit Policies**
   - Under "Client Credentials Flow" section:
     - **Run As**: Enter the username of your integration user
       - Example: `integration.user@yourcompany.com.sandbox`
   - Click **Save**

3. **Copy Consumer Secret**:
   - App Manager → Your App → **View**
   - Click "Click to reveal" next to Consumer Secret
   - Copy the value

### Option B: Create New Connected App

1. Setup → App Manager → **New Connected App**

2. **Basic Information**:
   - Connected App Name: `Bedrock KB Integration`
   - API Name: `Bedrock_KB_Integration`
   - Contact Email: your-email@company.com

3. **API (Enable OAuth Settings)**:
   - ✅ Enable OAuth Settings
   - Callback URL: `https://localhost`
   - Selected OAuth Scopes:
     - `Access and manage your data (api)`
     - `Perform requests at any time (refresh_token, offline_access)`

4. **Save** and copy Consumer Key & Consumer Secret

5. **Enable Client Credentials Flow**:
   - Setup → OAuth and OpenID Connect Settings
   - Toggle ON: **"Allow OAuth Client Credentials Flow"**

6. **Configure Run As User**:
   - App Manager → Your App → Manage → Edit Policies
   - Under "Client Credentials Flow":
     - Run As: `your.integration.user@company.com`
   - Save

---

## Step 2: Create AWS Secrets Manager Secret

### Required Secret Format
```json
{
  "consumerKey": "3MVG9...<your_consumer_key>",
  "consumerSecret": "ABC123...<your_consumer_secret>",
  "authenticationUrl": "https://yourorg.my.salesforce.com/services/oauth2/token"
}
```

### For Sandbox Orgs
```json
{
  "consumerKey": "3MVG9...",
  "consumerSecret": "ABC123...",
  "authenticationUrl": "https://yourorg--sandbox.sandbox.my.salesforce.com/services/oauth2/token"
}
```

### Create via AWS CLI
```bash
aws secretsmanager create-secret \
  --name "salesforceagent/salesforce/kb-connector-credentials" \
  --description "Salesforce OAuth2 credentials for Bedrock KB connector" \
  --secret-string '{
    "consumerKey": "YOUR_CONSUMER_KEY",
    "consumerSecret": "YOUR_CONSUMER_SECRET",
    "authenticationUrl": "https://yourorg.my.salesforce.com/services/oauth2/token"
  }' \
  --profile YOUR_AWS_PROFILE
```

### Create via Terraform
Add to `terraform.tfvars`:
```hcl
salesforce_kb_consumer_key    = "3MVG9..."
salesforce_kb_consumer_secret = "ABC123..."
salesforce_kb_auth_url        = "https://yourorg.my.salesforce.com/services/oauth2/token"
```

---

## Step 3: Create Knowledge Base with Salesforce Data Source

### Via AWS Console

1. **Bedrock Console** → Knowledge bases → **Create knowledge base**

2. **Knowledge base details**:
   - Name: `salesforce-kb`
   - IAM role: Create new or use existing

3. **Data source**:
   - Select: **Salesforce**
   - Name: `salesforce-connector`
   - Salesforce instance URL: `https://yourorg.my.salesforce.com`

4. **Authentication**:
   - Select your Secrets Manager secret ARN

5. **Content filters** (optional):
   - Include pattern: `.*` (all content)
   - Or specific: `Case.*`, `Knowledge__kav.*`

6. **Vector store**:
   - Only OpenSearch Serverless is supported
   - Select: Quick create new vector store

7. **Create** and wait for KB to be ready

### Via AWS CLI
```bash
# Create KB first, then add Salesforce data source
aws bedrock-agent create-data-source \
  --knowledge-base-id YOUR_KB_ID \
  --name "salesforce-connector" \
  --data-source-configuration '{
    "type": "SALESFORCE",
    "salesforceConfiguration": {
      "sourceConfiguration": {
        "authType": "OAUTH2_CLIENT_CREDENTIALS",
        "credentialsSecretArn": "arn:aws:secretsmanager:us-east-1:ACCOUNT:secret:your-secret",
        "hostUrl": "https://yourorg.my.salesforce.com"
      }
    }
  }' \
  --profile YOUR_AWS_PROFILE
```

---

## Step 4: Sync Data Source

### Via Console
1. Knowledge bases → Select your KB
2. Data sources tab → Select Salesforce source
3. Click **Sync**

### Via CLI
```bash
# List data sources to get ID
aws bedrock-agent list-data-sources \
  --knowledge-base-id YOUR_KB_ID \
  --profile YOUR_AWS_PROFILE

# Start sync
aws bedrock-agent start-ingestion-job \
  --knowledge-base-id YOUR_KB_ID \
  --data-source-id YOUR_DATASOURCE_ID \
  --profile YOUR_AWS_PROFILE

# Check status
aws bedrock-agent get-ingestion-job \
  --knowledge-base-id YOUR_KB_ID \
  --data-source-id YOUR_DATASOURCE_ID \
  --ingestion-job-id YOUR_JOB_ID \
  --profile YOUR_AWS_PROFILE
```

---

## Step 5: Associate KB with Bedrock Agent

```bash
# Associate
aws bedrock-agent associate-agent-knowledge-base \
  --agent-id YOUR_AGENT_ID \
  --agent-version DRAFT \
  --knowledge-base-id YOUR_KB_ID \
  --description "Salesforce data for case lookups" \
  --profile YOUR_AWS_PROFILE

# Prepare agent to publish changes
aws bedrock-agent prepare-agent \
  --agent-id YOUR_AGENT_ID \
  --profile YOUR_AWS_PROFILE
```

---

## Troubleshooting

### Error: "Issue connecting to data source - check credentials"

**Cause 1: Client Credentials Flow not enabled**
- Fix: Setup → OAuth and OpenID Connect Settings → Enable "Allow OAuth Client Credentials Flow"

**Cause 2: Run As user not configured**
- Fix: App Manager → Your App → Manage → Edit Policies → Set Run As user

**Cause 3: Wrong secret format**
- Fix: Ensure secret has exactly these keys:
  - `consumerKey` (not `ClientID`)
  - `consumerSecret` (not `ClientSecret`)
  - `authenticationUrl` (not `instanceUrl`)

**Cause 4: Wrong authentication URL**
- Production: `https://yourorg.my.salesforce.com/services/oauth2/token`
- Sandbox: `https://yourorg--sandboxname.sandbox.my.salesforce.com/services/oauth2/token`

### Error: "Invalid regex pattern: *"

**Cause**: Using glob pattern instead of regex
- Wrong: `*`
- Correct: `.*`

### Sync stuck in "STARTING"

- Salesforce connector syncs take longer than S3 (5-10+ minutes)
- Check CloudWatch logs for the KB
- Verify Salesforce org is accessible (not in maintenance)

### No documents indexed

**Cause 1: No matching content**
- Check inclusion/exclusion filters
- Verify Salesforce has data in the objects being crawled

**Cause 2: Permission issues**
- Run As user needs read access to target objects
- Check Profile/Permission Set assignments

---

## Supported Salesforce Objects

The connector can index:
- Standard Objects: Case, Account, Contact, Opportunity, etc.
- Knowledge Articles (Knowledge__kav)
- Custom Objects

---

## Limitations

1. **Vector Store**: Only OpenSearch Serverless supported
2. **Auth Type**: Only OAuth2 Client Credentials (no JWT Bearer)
3. **Preview**: Feature is in preview, subject to change
4. **No Multimodal**: Tables, charts, images not supported
5. **Quotas**: Check Bedrock KB quotas for file limits

---

## Cost Considerations

| Component | Cost |
|-----------|------|
| OpenSearch Serverless | ~$0.24/hr (OCU) |
| Bedrock KB | Per query pricing |
| Secrets Manager | $0.40/secret/month |

---

## Security Best Practices

1. **Dedicated Integration User**: Don't use admin accounts
2. **Least Privilege**: Grant only read access to required objects
3. **Rotate Secrets**: Regularly rotate Consumer Secret
4. **Audit Logs**: Monitor Salesforce API usage
5. **IP Restrictions**: Consider Connected App IP restrictions

---

## Quick Reference

### Secret Format
```json
{
  "consumerKey": "...",
  "consumerSecret": "...",
  "authenticationUrl": "https://yourorg.my.salesforce.com/services/oauth2/token"
}
```

### Salesforce Setup Checklist
- [ ] Connected App created/modified
- [ ] OAuth Client Credentials Flow enabled (org-level setting)
- [ ] Run As user configured in Connected App policies
- [ ] Integration user has API access
- [ ] Integration user has read access to target objects

### AWS Setup Checklist
- [ ] Secrets Manager secret created with correct format
- [ ] Knowledge Base created with OpenSearch Serverless
- [ ] Salesforce data source added
- [ ] Data source synced successfully
- [ ] KB associated with Bedrock Agent
