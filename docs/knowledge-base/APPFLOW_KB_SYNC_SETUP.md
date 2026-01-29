# AppFlow + Knowledge Base Sync Setup Guide

This guide covers setting up the automated Salesforce → S3 → Bedrock KB sync pipeline.

## Architecture Overview

```
Salesforce (KAV) → AppFlow → S3 Bucket → Bedrock KB (S3 Data Source) → Agent
                      ↑                           ↑
                      └── Step Functions ─────────┘
                              (Orchestration)
```

**Why this approach?**
- Bedrock's native Salesforce connector pulls ALL objects (323K+ docs) - no PublishStatus filter
- AppFlow allows precise SOQL filtering (only published KAV articles)
- S3 data source gives full control over what's indexed

## Prerequisites

1. AWS Account with Bedrock access
2. Salesforce org with API access
3. S3 bucket for KB data source
4. Terraform deployed (creates Step Functions)

---

## ⚠️ S3 Vectors Limit: 50MB per File

Bedrock S3 Vectors has a **50MB limit per file** (not total bucket). Each file must be under 50MB, but you can have many files.

| Strategy | Pros | Cons |
|----------|------|------|
| Weekly incremental | Small files, history preserved | Many files over time |
| Rolling window | Single file, simple | Loses old data |
| Category-based splits | Organized by type | Multiple AppFlow flows |

**Recommended**: Weekly incremental sync with `LAST_N_DAYS:7` filter (see Step 3.2)

---

## Step 1: Create S3 Bucket (if not exists)

```bash
aws s3 mb s3://your-kb-bucket --region us-east-1 --profile YOUR_PROFILE
```

---

## Step 2: Create Bedrock Knowledge Base (Manual - Console)

> ⚠️ KB must be created manually due to AWS Organization SCP restrictions

1. Open [Amazon Bedrock Console](https://console.aws.amazon.com/bedrock)
2. Navigate to **Knowledge Bases** → **Create**
3. Configure:
   - Name: `salesforceagent-kb`
   - Embeddings model: `amazon.titan-embed-text-v2:0`
   - Vector store: `Quick create` (creates S3 Vectors automatically)
4. Add Data Source:
   - Type: **S3**
   - S3 URI: `s3://your-kb-bucket/`
   - Sync schedule: Manual (Step Functions handles this)
5. **Save Knowledge Base ID and Data Source ID**

---

## Step 3: Create AppFlow Flow (Manual - Console)

> ⚠️ AppFlow requires OAuth authentication - must be created in Console

### 3.1 Create Salesforce Connection

1. Open [Amazon AppFlow Console](https://console.aws.amazon.com/appflow)
2. Go to **Connections** → **Create connection**
3. Select **Salesforce**
4. Configure:
   - Connection name: `Salesforce-UAT` (or your org name)
   - Environment: **Sandbox** or **Production**
5. Click **Continue** → Authenticate with Salesforce OAuth
6. Authorize the connection

### 3.2 Create Flow

1. Go to **Flows** → **Create flow**
2. Configure flow details:
   - Flow name: `SYNCCASESWITHS3` (must match `appflow_flow_name` in terraform.tfvars)
   - Description: `Sync Salesforce Knowledge Articles to S3 for Bedrock KB`

3. Configure source:
   - Source: **Salesforce**
   - Connection: Select your connection
   - Object: **Knowledge__kav**

4. Configure destination:
   - Destination: **Amazon S3**
   - Bucket: `your-kb-bucket`
   - File format: **JSON** (recommended) or CSV
   - **S3 bucket prefix**: `cases/` (optional, for organization)
   - **Aggregation**: **None** (creates timestamped files each run)

5. Configure flow trigger:
   - Trigger type: **Run on demand**
   - (Step Functions will trigger this)

6. Configure field mapping:
   - Map essential fields only (reduces file size):
     - `Id`
     - `CaseNumber`
     - `Subject`
     - `Description`
     - `Status`
     - `Priority`
     - `Resolution__c`
     - `Close_Notes__c`
     - `ClosedDate`
     - `Category__c` (if exists)

7. **Add filters (CRITICAL for 50MB limit)**:

   **For Closed Cases (Incremental Weekly Sync):**
   ```
   Status = 'Closed'
   AND LastModifiedDate >= LAST_N_DAYS:7    (weekly incremental)
   AND Resolution__c != null                 (only cases with resolutions)
   ```

   **For Knowledge Articles (KAV):**
   ```
   PublishStatus = 'Online'
   AND Language = 'en_US'
   ```

   > 💡 **Strategy**: Each weekly sync creates a small file (~few KB-MB). Files accumulate in S3, Bedrock KB indexes all of them. Monitor total bucket size to stay under 50MB.

   > ⚠️ **First Run**: For initial load, temporarily remove `LAST_N_DAYS:7` filter to get all historical closed cases, then re-add for subsequent runs.

8. **Save and activate** the flow

### 3.3 Test Flow Manually

1. Click **Run flow**
2. Verify data appears in S3 bucket
3. Check record count matches expected KAV articles

---

## Step 4: Update Terraform Variables

Edit `terraform/terraform.tfvars`:

```hcl
# Knowledge Base (from Step 2)
knowledge_base_id = "YOUR_KB_ID"

# AppFlow + Step Functions KB Sync
appflow_flow_name        = "SYNCCASESWITHS3"
kb_data_source_id        = "YOUR_DATASOURCE_ID"
sync_schedule_expression = "cron(0 2 * * ? *)"  # Daily at 2am UTC
enable_scheduled_sync    = false  # Enable after testing
```

---

## Step 5: Deploy Step Functions

```bash
cd terraform
source aws-auth.sh  # Or manually set AWS credentials
terraform plan
terraform apply
```

This creates:
- Step Functions state machine: `salesforceagent-kb-sync`
- IAM role with AppFlow + Bedrock permissions
- CloudWatch log group

---

## Step 6: Test the Pipeline

### Manual Execution

```bash
aws stepfunctions start-execution \
  --state-machine-arn "arn:aws:states:us-east-1:ACCOUNT:stateMachine:salesforceagent-kb-sync" \
  --profile YOUR_PROFILE
```

### Monitor Execution

```bash
# Get execution ARN from start-execution output, then:
aws stepfunctions describe-execution \
  --execution-arn "arn:aws:states:us-east-1:ACCOUNT:execution:salesforceagent-kb-sync:EXECUTION_ID" \
  --profile YOUR_PROFILE
```

Or view in AWS Console: Step Functions → State machines → salesforceagent-kb-sync → Executions

### Expected Flow

1. **StartAppFlowExecution** - Triggers AppFlow
2. **WaitForAppFlow** (30s) - Polls for completion
3. **CheckAppFlowStatus** - Verifies success
4. **StartBedrockKBSync** - Triggers KB ingestion
5. **WaitForKBSync** (60s) - Polls for completion
6. **CheckKBSyncStatus** - Verifies success
7. **SyncSuccess** - Done!

---

## Step 7: Enable Scheduled Sync (Optional)

Once tested, enable automatic daily sync:

```hcl
# terraform.tfvars
enable_scheduled_sync = true
```

```bash
terraform apply
```

This creates an EventBridge rule that triggers the state machine daily at 2am UTC.

---

## Troubleshooting

### AppFlow Fails

1. Check Salesforce connection is active
2. Verify SOQL filters are valid
3. Check S3 bucket permissions
4. Review AppFlow execution logs in Console

### KB Sync Fails

1. Verify S3 bucket has data from AppFlow
2. Check KB data source configuration
3. Verify IAM permissions for Bedrock
4. Review KB sync job in Bedrock Console

### Step Functions Fails

```bash
# Check execution history
aws stepfunctions get-execution-history \
  --execution-arn "EXECUTION_ARN" \
  --profile YOUR_PROFILE
```

### Common Errors

| Error | Cause | Fix |
|-------|-------|-----|
| `AccessDenied` on AppFlow | IAM permissions | Check sfn_appflow policy |
| `ResourceNotFoundException` | Wrong KB/DataSource ID | Verify IDs in tfvars |
| `ValidationException` | AppFlow not found | Create AppFlow in Console first |
| `ThrottlingException` | Too many API calls | Increase wait times in state machine |

---

## Key IDs Reference

| Resource | ID | Description |
|----------|-----|-------------|
| Knowledge Base | `LJSELALSFJ` | S3-based KB (active) |
| Data Source | `KZDT2HX02R` | S3 data source |
| AppFlow | `SYNCCASESWITHS3` | SF → S3 flow |
| S3 Bucket | `sftestcasess3` | KB data storage |
| Agent | `PWILBVBXT2` | Bedrock Agent |
| State Machine | `salesforceagent-kb-sync` | Orchestration |

---

## Deprecated: Salesforce Connector KB

Previously tried Bedrock's native Salesforce connector (`QEGLQXSCQP`), but abandoned due to:
- Pulled 323K+ documents instead of 46 KAV articles
- No PublishStatus filter support
- Included Attachments and ContentVersion objects

The S3 + AppFlow approach provides precise control over what's indexed.
