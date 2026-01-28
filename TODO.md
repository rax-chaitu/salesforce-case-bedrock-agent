# TODO - Before Deploying to New Sandbox

## Resource Naming Refactor

Current naming uses `salesforceagent` prefix. Should follow `sf-{object}-{function}` convention per [docs/NAMING_CONVENTIONS.md](docs/NAMING_CONVENTIONS.md).

### Current vs Target Naming

| Resource | Current Name | Target Name |
|----------|--------------|-------------|
| Project | `salesforceagent` | `sf-case-analysis` |
| Lambda | `salesforceagent-api` | `sf-case-analysis-processor` |
| SQS Queue | `salesforceagent-case-analysis` | `sf-case-analysis-queue` |
| SQS DLQ | `salesforceagent-case-analysis-dlq` | `sf-case-analysis-dlq` |
| Step Function | `salesforceagent-kb-sync` | `sf-case-analysis-kb-sync` |
| EventBridge Rule | `salesforceagent-kb-sync-schedule` | `sf-case-analysis-kb-sync-schedule` |
| IAM Roles | `salesforceagent-*-role` | `sf-case-analysis-*-role` |
| CloudWatch Logs | `/aws/lambda/salesforceagent-api` | `/aws/lambda/sf-case-analysis-processor` |
| API Gateway | `salesforceagent-api` | `sf-case-analysis-gateway` |
| Bedrock Agent | `salesforceagent-agent` | `sf-case-analysis-agent` |

### Steps to Refactor

1. Update `terraform.tfvars`:
   ```hcl
   project_name = "sf-case-analysis"
   ```

2. Update Lambda handler name in `terraform/modules/lambda/main.tf`:
   - Change `${var.project_name}-api` to `${var.project_name}-processor`

3. Update API Gateway name in `terraform/api_gateway.tf`:
   - Change to `${var.project_name}-gateway`

4. Run `terraform plan` to see all resource recreations

5. **Note**: This will destroy and recreate resources. For existing sandbox, may need to:
   - Export any state/data
   - Update Salesforce Event Relay with new EventBridge bus name
   - Re-sync Knowledge Base

### For New Sandbox Deployment

Simply set `project_name = "sf-case-analysis"` in `terraform.tfvars` before first `terraform apply`.

---

## Other TODOs

- [ ] Rename resources to follow naming convention
- [ ] Test full E2E flow after rename
- [ ] Update Salesforce Event Relay if EventBridge bus name changes
- [ ] Document any manual steps needed for migration

---

## AppFlow Data Sync Optimization

### Current Issue
- AppFlow creates new timestamped files each run → duplicates in S3
- S3 Vectors has **50MB limit** per data source

### Recommended Setup

1. **Configure AppFlow for Incremental Sync:**
   - Aggregation: None (creates new timestamped file each run)
   - Filter: `LastModifiedDate >= LAST_N_DAYS:7`

2. **Weekly Sync Strategy:**
   - Each run creates small file with last 7 days of closed cases
   - Files accumulate: `cases-20260127T020000.json`, `cases-20260203T020000.json`
   - Bedrock KB indexes all files in bucket

3. **Initial Load (One-Time):**
   - Remove `LAST_N_DAYS:7` filter
   - Run AppFlow to get all historical closed cases
   - Re-add filter for subsequent weekly runs

4. **Monitor File Sizes:**
   - S3 Vectors limit: **50MB per file** (not total bucket)
   - Weekly files should be well under this
   - Archive old files periodically if needed for cleanup

See [docs/APPFLOW_KB_SYNC_SETUP.md](docs/APPFLOW_KB_SYNC_SETUP.md) for details.
