# Salesforce Case Data Analysis Report

**Date:** January 29, 2026  
**Sample Size:** 2,000 closed cases (2025)  
**Total Closed Cases in 2025:** 10,771  

---

## Executive Summary

This analysis examines closed Salesforce cases to understand common request types and improve the AI Agent's response quality. The cases are primarily **internal Salesforce administration requests** from sales teams, not customer support tickets.

---

## Case Category Distribution

| Category | Count | % | Description |
|----------|-------|---|-------------|
| **OPPORTUNITY** | 725 | 36.2% | Opp changes, ownership, amounts, status |
| **OTHER** | 345 | 17.2% | Miscellaneous requests |
| **USER_ACCESS** | 155 | 7.8% | User permissions, login, deactivation |
| **ACCOUNT_COMPANY** | 147 | 7.3% | Account updates, company changes |
| **UPDATE_CHANGE** | 133 | 6.7% | General data modifications |
| **PRICING_AMOUNT** | 125 | 6.2% | MRR, ACV, quote, amount changes |
| **FIELD_CONFIG** | 110 | 5.5% | Picklist values, field layouts |
| **CREATE_ADD** | 65 | 3.2% | New records, additions |
| **TEAM_OWNERSHIP** | 53 | 2.6% | Team member changes, reassignments |
| **APPROVAL_WORKFLOW** | 41 | 2.1% | Approval process issues |
| **INTEGRATION** | 27 | 1.4% | QM, Raptor, API, JIRA sync |
| **LEAD** | 23 | 1.1% | Lead management |
| **REPORTING** | 15 | 0.8% | Reports, dashboards |
| **MARKETPLACE_PARTNER** | 11 | 0.5% | WorkSpan, partner portal |
| **DELETE_REMOVE** | 11 | 0.5% | Record deletion |
| **QUEUE_ASSIGNMENT** | 9 | 0.4% | Queue management |
| **EMAIL_NOTIFICATION** | 5 | 0.2% | Email alerts |

---

## Key Findings

### 1. Primary Use Case: Internal SF Admin Requests
- **36%** of cases are Opportunity-related (amount changes, ownership transfers, status updates)
- These are NOT customer support tickets - they're internal requests from sellers to SF admins
- Most require admin action, not self-service resolution

### 2. Common Request Patterns
| Pattern | Count | Example |
|---------|-------|---------|
| Email threads (Re:/Fw:) | 222 | Ongoing conversations |
| Explicit requests ("please") | 208 | "Please update the amount" |
| Need statements | 120 | "Need access to..." |
| Issue reports | 78 | "Cannot login", "Unable to..." |
| How-to questions | 1 | Rare - users know what they want |

### 3. Integration Systems Mentioned
- **QM (Quote Management)** - Quote edits, PDF generation
- **Raptor** - Data sync issues, DDI not showing
- **JIRA** - Status sync
- **WorkSpan** - Partner marketplace
- **Financial Force** - Permissions

### 4. Priority Distribution
- Low: 733 (37%)
- Medium: 685 (34%)
- High: 582 (29%)

### 5. Data Quality
- 99.9% of cases have descriptions (avg 828 chars)
- Case_Type__c, Department__c, Close_Codes__c fields are mostly NULL
- Close notes (Case_Closure_Notes__c) not consistently populated

---

## Sample Subjects by Category

### OPPORTUNITY (36.2%)
- "Please add opportunity members"
- "Correction Needed – Missing Opportunities on Commissions Statement"
- "October 2025 - Missing Opportunity"
- "Please change the Opp amount"
- "Mark this opp as ODR"

### USER_ACCESS (7.8%)
- "Salesforce Access For Priyanka Sharma on my team"
- "GTMO access"
- "Salesforce Financial Force Permission"
- "Need access user in line is deactive"

### INTEGRATION (1.4%)
- "QM case for pdf edit for Delta Capita Ltd-CSP Resale O+ PS contract"
- "Sync Raptor with Core"
- "DDI not showing in Raptor"

### PRICING_AMOUNT (6.2%)
- "Request to update the salesforce amount to zero as per the migration contract"
- "Amount Change"
- "Contract edits required for QM quote"

---

## Recommendations for Agent Training

### 1. Update Agent Instructions to Reflect Actual Use Cases

The agent should understand these are **internal SF admin requests**, not customer support:

```
Primary case types:
- Opportunity management (36%): Amount changes, ownership transfers, status updates
- User access (8%): Permission requests, login issues, deactivation
- Account/Company (7%): Name changes, DDI updates, account merges
- Data updates (7%): Field changes, record modifications
- Pricing (6%): MRR/ACV updates, quote corrections
- Configuration (5%): Picklist values, page layouts
```

### 2. Add Integration System Context

Agent should know about:
- **QM (Quote Management)**: For quote/contract edits
- **Raptor**: For data sync and DDI issues
- **JIRA**: For development ticket tracking
- **WorkSpan**: For partner marketplace
- **Financial Force**: For finance-related permissions

### 3. Recognize Request Patterns

Most cases are:
- Direct requests ("Please update X")
- Need statements ("Need access to Y")
- Issue reports ("Cannot do Z")

NOT:
- How-to questions (rare)
- Complex troubleshooting (admin handles it)

### 4. Add AI Disclaimer

Every response should include:
```
---
⚠️ AI-Generated Analysis: Please verify before taking action.
```

### 5. Improve KB Data

Current KB has unstructured text. Recommend adding:
- Case_Type__c (populate consistently)
- Resolution steps (structured)
- Time to resolve
- Required permissions/access level

---

## Next Steps

1. ✅ Update agent instructions with category-specific guidance
2. ✅ Add AI disclaimer to all responses
3. ⬜ Improve KB data structure with Case_Type__c
4. ⬜ Add integration system documentation to KB
5. ⬜ Create resolution templates for common request types
