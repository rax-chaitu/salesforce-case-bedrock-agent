# TODO - Salesforce AI Case Analysis Agent

## ✅ Completed (Jan 29, 2026)

- [x] Security fixes: CORS restricted, KMS wildcard removed, input validation
- [x] Lambda concurrency increased 2 → 20 (~4,800 cases/hour)
- [x] Lazy client initialization for better cold starts
- [x] Type hints and custom `BedrockAgentError` exception
- [x] Retry logic with exponential backoff
- [x] Agent instructions updated with category-specific guidance
- [x] AI disclaimer added to all responses
- [x] Case data analysis report created (2000 cases analyzed)
- [x] KB improvement guide created

---

## 🔴 High Priority - KB Improvements

### KB Data Quality Issues
Current KB has poor search results due to:
- AppFlow outputs 177 fields as raw JSON
- Bedrock chunks JSON into meaningless fragments
- Low relevance scores (0.4-0.5 instead of 0.7+)

### Action Items

- [ ] **Update AppFlow to select only needed fields:**
  - CaseNumber, Subject, Description, Priority
  - Case_Type__c, Close_Codes__c, Case_Closure_Notes__c
  - Tool__c, Support_Reason__c, Department__c

- [ ] **Create transformation Lambda** to convert JSON → structured text format:
  ```
  === CASE 00145956 ===
  SUBJECT: Change User email
  PRIORITY: High
  CATEGORY: User_Access
  RESOLUTION: Email changed.
  ===
  ```

- [ ] **Reconfigure KB chunking** - increase chunk size to 800 tokens

- [ ] **Add metadata filtering** for Category, Priority, Tool

See [docs/KB_IMPROVEMENT_GUIDE.md](docs/KB_IMPROVEMENT_GUIDE.md) for details.

---

## 🟡 Medium Priority - Before Production

### Resource Naming Refactor

Current naming uses `salesforceagent` prefix. Should follow `sf-{object}-{function}` convention.

| Resource | Current Name | Target Name |
|----------|--------------|-------------|
| Project | `salesforceagent` | `sf-case-analysis` |
| Lambda | `salesforceagent-api` | `sf-case-analysis-processor` |
| SQS Queue | `salesforceagent-case-analysis` | `sf-case-analysis-queue` |

**Steps:**
1. Update `terraform.tfvars`: `project_name = "sf-case-analysis"`
2. Run `terraform plan` to see resource recreations
3. Update Salesforce Event Relay with new EventBridge bus name

### Salesforce Field Population

- [ ] Ensure `Case_Type__c` is populated consistently
- [ ] Add `Case_Closure_Notes__c` to case close process
- [ ] Train users to fill resolution fields

---

## 🟢 Low Priority - Future Enhancements

- [ ] Separate KB data sources (Cases, KAV, Emails)
- [ ] Add metadata filtering to agent queries
- [ ] Create resolution templates for common request types
- [ ] Add monitoring dashboard for agent performance
- [ ] Implement feedback loop for response quality

---

## AppFlow Data Sync Optimization

### Current Issue
- AppFlow creates new timestamped files each run → duplicates in S3
- S3 Vectors has **50MB limit** per data source

### Recommended Setup

1. **Configure AppFlow for Incremental Sync:**
   - Filter: `LastModifiedDate >= LAST_N_DAYS:7`

2. **Weekly Sync Strategy:**
   - Each run creates small file with last 7 days of closed cases
   - Bedrock KB indexes all files in bucket

See [docs/APPFLOW_KB_SYNC_SETUP.md](docs/APPFLOW_KB_SYNC_SETUP.md) for details.

---

## Documentation

| Doc | Purpose |
|-----|---------|
| [analysis/CASE_DATA_ANALYSIS_REPORT.md](docs/analysis/CASE_DATA_ANALYSIS_REPORT.md) | Analysis of 2000 closed cases |
| [knowledge-base/KB_IMPROVEMENT_GUIDE.md](docs/knowledge-base/KB_IMPROVEMENT_GUIDE.md) | Steps to improve KB quality |
| [deployment/DEPLOYMENT_GUIDE.md](docs/deployment/DEPLOYMENT_GUIDE.md) | Full deployment instructions |
| [architecture/EVENT_DRIVEN_ARCHITECTURE.md](docs/architecture/EVENT_DRIVEN_ARCHITECTURE.md) | System architecture |
| [salesforce/SALESFORCE_AUTH_IMPLEMENTATION.md](docs/salesforce/SALESFORCE_AUTH_IMPLEMENTATION.md) | JWT auth setup |

---

## Docs Structure

```
docs/
├── analysis/           # Data analysis reports
├── architecture/       # System design docs
├── deployment/         # Deploy & terraform guides
├── knowledge-base/     # KB setup & improvement
└── salesforce/         # SF config & auth
```
