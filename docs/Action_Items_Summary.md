# AWS Bedrock Agent - Action Items Summary

**Date:** January 29, 2026

---

## Critical Actions (Fix This Week)

### 1. Fix CORS Wildcard - SECURITY CRITICAL
**File:** `lambda/case_processor/handler.py` line 236
**Current:** `"Access-Control-Allow-Origin": "*"`
**Fix:** Restrict to specific Salesforce domain

### 2. Move Private Key Out of Terraform - SECURITY CRITICAL
**Files:** `terraform/variables.tf`, `terraform.tfvars`
**Action:** Store JWT private key directly in Secrets Manager, not through Terraform

### 3. Increase Lambda Concurrency - PERFORMANCE CRITICAL
**File:** `terraform/modules/lambda/main.tf` line 100
**Current:** `reserved_concurrent_executions = 2`
**Fix:** Change to 20

### 4. Add Input Validation - SECURITY HIGH
**File:** `lambda/case_processor/handler.py` lines 277-305
**Action:** Add string length limits (5000 chars) and format validation

### 5. Fix SQL Injection - SECURITY HIGH
**File:** `lambda/case_processor/salesforce_client.py` line 125
**Action:** Validate case ID format before query or use parameterized queries

### 6. Restrict KMS Policy - SECURITY HIGH
**File:** `terraform/modules/lambda/main.tf` lines 234-238
**Action:** Change wildcard `key/*` to specific Secrets Manager KMS key

---

## Quick Wins (Low Effort, High Impact)

| Task | File | Effort | Impact |
|------|------|--------|--------|
| Add security headers | handler.py:232 | 15 min | Medium |
| Enable CloudWatch Insights | terraform | 30 min | High |
| Add DLQ SNS notification | sqs/main.tf | 30 min | Medium |
| Reduce log retention to 7 days | lambda/main.tf:73 | 5 min | $0.40/mo savings |

---

## Monitoring Commands

```bash
# Check Lambda errors
aws logs tail /aws/lambda/salesforceagent-api --since 5m --format short

# Check SQS depth
aws sqs get-queue-attributes --queue-url $SQS_URL --attribute-names ApproximateNumberOfMessages

# Check DLQ
aws sqs get-queue-attributes --queue-url $DLQ_URL --attribute-names ApproximateNumberOfMessages

# Redeploy Lambda after code fix
cd lambda/case_processor/package && zip -rq /tmp/lambda.zip .
cd .. && zip -j /tmp/lambda.zip handler.py bedrock_client.py salesforce_client.py
aws lambda update-function-code --function-name salesforceagent-api --zip-file fileb:///tmp/lambda.zip
```

---

## Key Metrics to Monitor

| Metric | Current | Target | Alert Threshold |
|--------|---------|--------|-----------------|
| E2E Latency | ~20s | <30s | >60s |
| Lambda Concurrency | 2 | 20 | >15 |
| DLQ Messages | 0 | 0 | >0 |
| Bedrock Throttling | Low | 0 | >5/hour |
| Cold Start | ~5s | <5s | >10s |

---

## Issue Priority Matrix

```
IMPACT
  ^
  │  ┌─────────────────┬─────────────────┐
  │  │ CRITICAL:       │ HIGH:           │
  │  │ 1. CORS         │ 3. Concurrency  │
H │  │ 2. Private Key  │ 4. Input Valid  │
I │  │                 │ 5. SQL Inject   │
G │  │                 │ 6. KMS Policy   │
H │  ├─────────────────┼─────────────────┤
  │  │ MEDIUM:         │ LOW:            │
  │  │ - VPC Isolation │ - Security Hdrs │
L │  │ - Type Hints    │ - Request IDs   │
O │  │ - Token Cache   │ - Concurrency   │
W │  │ - Error Handle  │   Provisioned   │
  │  └─────────────────┴─────────────────┘
  └────────────────────────────────────────> EFFORT
           LOW              HIGH
```

---

## Estimated Effort Summary

| Phase | Items | Total Hours |
|-------|-------|-------------|
| Phase 1 (Critical) | 6 | 8 hours |
| Phase 2 (High) | 3 | 8 hours |
| Phase 3 (Medium) | 4 | 8 hours |
| **Total** | **13** | **24 hours** |

---

*For detailed analysis, see: `AWS_Bedrock_Agent_Analysis_Report.md`*
