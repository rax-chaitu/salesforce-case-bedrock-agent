# Naming Conventions

## Pattern

```
sf-{object}-{function}-{resource}
```

| Component | Description | Examples |
|-----------|-------------|----------|
| `sf` | Salesforce prefix | Always `sf` |
| `{object}` | Salesforce object | `case`, `account`, `opp`, `lead` |
| `{function}` | What it does | `analysis`, `enrich`, `scoring`, `routing` |
| `{resource}` | AWS resource type | `agent`, `kb`, `processor`, `queue`, `gateway` |

---

## Resource Naming

| Resource | Pattern | Example |
|----------|---------|---------|
| Agent | `sf-{object}-{function}-agent` | `sf-case-analysis-agent` |
| Knowledge Base | `sf-{object}-{function}-kb` | `sf-case-analysis-kb` |
| Lambda | `sf-{object}-{function}-processor` | `sf-case-analysis-processor` |
| SQS Queue | `sf-{object}-{function}-queue` | `sf-case-analysis-queue` |
| SQS DLQ | `sf-{object}-{function}-dlq` | `sf-case-analysis-dlq` |
| API Gateway | `sf-{object}-{function}-gateway` | `sf-case-analysis-gateway` |
| Secrets | `sf-{object}-{function}/jwt-key` | `sf-case-analysis/jwt-key` |
| IAM Role | `sf-{object}-{function}-{service}-role` | `sf-case-analysis-lambda-role` |
| CloudWatch Logs | `/aws/lambda/sf-{object}-{function}-processor` | `/aws/lambda/sf-case-analysis-processor` |

---

## Terraform Configuration

```hcl
# terraform.tfvars
project_name = "sf-case-analysis"  # Pattern: sf-{object}-{function}
```

All resources automatically use this prefix.

---

## Examples by Use Case

### Case Analysis Agent
```
project_name = "sf-case-analysis"

Resources created:
- sf-case-analysis-agent
- sf-case-analysis-kb
- sf-case-analysis-processor
- sf-case-analysis-queue
- sf-case-analysis-gateway
```

### Account Enrichment Agent
```
project_name = "sf-account-enrich"

Resources created:
- sf-account-enrich-agent
- sf-account-enrich-kb
- sf-account-enrich-processor
- sf-account-enrich-queue
- sf-account-enrich-gateway
```

### Opportunity Scoring Agent
```
project_name = "sf-opp-scoring"

Resources created:
- sf-opp-scoring-agent
- sf-opp-scoring-kb
- sf-opp-scoring-processor
- sf-opp-scoring-queue
- sf-opp-scoring-gateway
```

### Multi-Object Support Agent
```
project_name = "sf-support-triage"

Resources created:
- sf-support-triage-agent
- sf-support-triage-kb
- sf-support-triage-processor
- sf-support-triage-queue
- sf-support-triage-gateway
```

---

## Agent Alias Naming

| Alias | Purpose |
|-------|---------|
| `DEV` | Development/testing - auto-updated by Terraform |
| `UAT` | User acceptance testing |
| `PROD` | Production - manually promoted |

---

## New Sandbox Setup Checklist

1. Copy `terraform.tfvars.example` to `terraform.tfvars`
2. Set `project_name` using convention: `sf-{object}-{function}`
3. Update AWS profile and region
4. Create KB manually in console with matching name
5. Run `terraform init && terraform apply`

---

## Migration Note

Existing `salesforceagent` setup uses old naming. For new sandboxes/agents, use this convention. Renaming existing resources requires destroy/recreate.
