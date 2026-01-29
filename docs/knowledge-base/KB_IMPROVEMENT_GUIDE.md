# Knowledge Base Improvement Guide

**Date:** January 29, 2026  
**Current KB ID:** LJSELALSFJ  
**Data Source:** AppFlow from Salesforce → S3 → Bedrock KB

---

## Recommended Case Fields for AppFlow

### Core Fields (Must Have)
| Field | API Name | Type | Purpose |
|-------|----------|------|---------|
| Case Number | `CaseNumber` | String | Reference ID for matching |
| Subject | `Subject` | String | Primary search text |
| Description | `Description` | Text Area | Detailed issue context |
| Priority | `Priority` | Picklist | Severity matching |
| Status | `Status` | Picklist | Filter closed only |
| Origin | `Origin` | Picklist | Web, Email, Phone, etc. |

### Resolution Fields (Critical for KB Quality)
| Field | API Name | Type | Purpose |
|-------|----------|------|---------|
| Case Closure Notes | `Case_Closure_Notes__c` | Text Area | How it was resolved |
| Close Codes | `Close_Codes__c` | Picklist | Resolution category |
| Admin Notes | `Admin_Notes__c` | Text Area | Additional resolution info |

### Categorization Fields (For Filtering & Matching)
| Field | API Name | Type | Purpose |
|-------|----------|------|---------|
| Case Type | `Case_Type__c` | Picklist | Request category |
| Department | `Department__c` | Picklist | Team routing |
| Tool | `Tool__c` | Picklist | System involved (SF, QM, Raptor) |
| Support Reason | `Support_Reason__c` | Picklist | Why case was created |

### User & Source Fields (For Pattern Analysis)
| Field | API Name | Type | Purpose |
|-------|----------|------|---------|
| Created By | `CreatedById` | Reference | Who created the case |
| Created By Role | `Created_By_Role__c` | String | Requestor's role |
| Owner | `OwnerId` | Reference | Assigned admin |
| Owner Role | `Owner_Role__c` | String | Admin's role |
| Requestor's Team | `Requestor_s_Team__c` | String | Team making request |
| Requestor's Region | `Requestor_s_Region__c` | String | Geographic region |
| Requestor's Location | `Requestor_s_Location__c` | String | Office location |
| Region | `Region__c` | Picklist | Business region |
| Team | `Team__c` | String | Team name |

### Context Fields (For Similar Case Matching)
| Field | API Name | Type | Purpose |
|-------|----------|------|---------|
| Opportunity | `Opportunity_Name__c` | Reference | Link to Opp if relevant |
| Account | `Account__c` | Reference | Customer context |
| Created Date | `CreatedDate` | DateTime | Recency |
| Closed Date | `ClosedDate` | DateTime | Resolution timeline |
| Age Days | `Age_Days__c` | String | Time to resolve |

### Total: 24 Fields (vs current 177)

---

## AppFlow Configuration

### SOQL Query for AppFlow
```sql
SELECT 
  CaseNumber, Subject, Description, Priority, Status, Origin,
  Case_Closure_Notes__c, Close_Codes__c, Admin_Notes__c,
  Case_Type__c, Department__c, Tool__c, Support_Reason__c,
  CreatedById, Created_By_Role__c, OwnerId, Owner_Role__c,
  Requestor_s_Team__c, Requestor_s_Region__c, Requestor_s_Location__c,
  Region__c, Team__c,
  Opportunity_Name__c, Account__c, CreatedDate, ClosedDate, Age_Days__c
FROM Case
WHERE Status = 'Closed'
  AND ClosedDate >= LAST_N_DAYS:90
ORDER BY ClosedDate DESC
```

---

## Current Issues

### 1. Poor Chunking of AppFlow JSON
- AppFlow outputs 177 fields per case as JSON
- Bedrock KB chunks this into meaningless fragments
- Results include field names like `"Target_Platform__c":""` instead of useful content

### 2. Low Relevance Scores
| Query | Best Score | Expected |
|-------|------------|----------|
| "password reset" | 0.39 | 0.70+ |
| "opportunity amount" | 0.61 | 0.75+ |
| "user access" | 0.52 | 0.70+ |
| "Raptor DDI" | 0.47 | 0.70+ |

### 3. No Metadata Filtering
- Can't filter by Category, Priority, Tool
- Agent searches entire KB for every query
- Irrelevant results mixed with relevant ones

### 4. Duplicate Results
- Same chunk appearing multiple times
- Wastes result slots

---

## Recommended Improvements

### Phase 1: Improve AppFlow Output Format

**Current Format (Bad):**
```json
{"Id":"500Pe...","CaseNumber":"00145956","Subject":"Change email","Description":"...","Case_Type__c":"","Close_Codes__c":"","...177 more fields..."}
```

**Recommended Format (Good):**
```
=== CASE 00145956 ===
SUBJECT: Change User email for Partner Portal
PRIORITY: High
CATEGORY: User_Access
TOOL: Salesforce
STATUS: Closed

DESCRIPTION:
Hello, The email partnerportaldemo@rackspace.com associated with user Rackspace Partner Help is not valid and needs to be updated to raxpartnerhelp@rackspace.com.

RESOLUTION:
Email changed successfully.

RESOLUTION STEPS:
1. Navigate to User record
2. Update email field
3. Reset password
4. Notify requestor
===
```

**Why This Works:**
- Clear section headers for semantic search
- Each case is a complete, self-contained chunk
- Human-readable format that LLM understands
- Keywords like "RESOLUTION" help matching

### Phase 2: Configure KB Chunking

**Current Settings (Default):**
- Fixed-size chunking (300 tokens)
- No overlap
- Splits cases across multiple chunks

**Recommended Settings:**
```json
{
  "chunkingConfiguration": {
    "chunkingStrategy": "SEMANTIC",
    "semanticChunkingConfiguration": {
      "maxTokens": 1000,
      "bufferSize": 50,
      "breakpointPercentileThreshold": 95
    }
  }
}
```

**Or use Fixed with larger size:**
```json
{
  "chunkingConfiguration": {
    "chunkingStrategy": "FIXED_SIZE",
    "fixedSizeChunkingConfiguration": {
      "maxTokens": 800,
      "overlapPercentage": 10
    }
  }
}
```

### Phase 3: Add Metadata for Filtering

**Step 1: Create metadata JSON alongside each case**
```json
{
  "metadataAttributes": {
    "case_number": "00145956",
    "category": "User_Access",
    "priority": "High",
    "tool": "Salesforce",
    "status": "Closed"
  }
}
```

**Step 2: Configure KB metadata fields**
```bash
aws bedrock-agent update-data-source \
  --knowledge-base-id LJSELALSFJ \
  --data-source-id KZDT2HX02R \
  --data-source-configuration '{
    "s3Configuration": {
      "bucketArn": "arn:aws:s3:::sftestcasess3"
    }
  }' \
  --vectorIngestionConfiguration '{
    "parsingConfiguration": {
      "parsingStrategy": "BEDROCK_FOUNDATION_MODEL"
    }
  }'
```

**Step 3: Use metadata filters in queries**
```python
response = bedrock.retrieve(
    knowledgeBaseId=kb_id,
    retrievalQuery={"text": "password reset"},
    retrievalConfiguration={
        "vectorSearchConfiguration": {
            "numberOfResults": 5,
            "filter": {
                "equals": {"key": "category", "value": "User_Access"}
            }
        }
    }
)
```

### Phase 4: Separate Data Sources

Create separate data sources for different content types:

| Data Source | Content | S3 Path |
|-------------|---------|---------|
| `cases-structured` | Closed cases with resolutions | `s3://bucket/cases/` |
| `kav-articles` | Knowledge Articles | `s3://bucket/kav/` |
| `email-threads` | Email-based resolutions | `s3://bucket/emails/` |

**Benefits:**
- Better chunking per content type
- Can weight sources differently
- Easier to update/refresh

---

## Implementation Steps

### Step 1: Update AppFlow (Salesforce Side)

1. Modify AppFlow to select only needed fields:
   - CaseNumber, Subject, Description, Priority
   - Case_Type__c, Close_Codes__c, Case_Closure_Notes__c
   - Tool__c, Support_Reason__c, Department__c

2. Add a Lambda transformation to convert JSON → structured text

### Step 2: Create Transformation Lambda

```python
def transform_case(case_json):
    return f"""=== CASE {case_json['CaseNumber']} ===
SUBJECT: {case_json['Subject']}
PRIORITY: {case_json['Priority']}
CATEGORY: {categorize(case_json['Subject'])}
TOOL: {case_json.get('Tool__c', 'Salesforce')}

DESCRIPTION:
{case_json['Description']}

RESOLUTION:
{case_json.get('Case_Closure_Notes__c', 'N/A')}
==="""
```

### Step 3: Update KB Data Source

```bash
# Delete old data source
aws bedrock-agent delete-data-source \
  --knowledge-base-id LJSELALSFJ \
  --data-source-id KZDT2HX02R

# Create new with better config
aws bedrock-agent create-data-source \
  --knowledge-base-id LJSELALSFJ \
  --name "cases-structured" \
  --data-source-configuration '{
    "type": "S3",
    "s3Configuration": {
      "bucketArn": "arn:aws:s3:::sftestcasess3",
      "inclusionPrefixes": ["cases-structured/"]
    }
  }' \
  --vectorIngestionConfiguration '{
    "chunkingConfiguration": {
      "chunkingStrategy": "FIXED_SIZE",
      "fixedSizeChunkingConfiguration": {
        "maxTokens": 800,
        "overlapPercentage": 10
      }
    }
  }'
```

### Step 4: Re-sync KB

```bash
aws bedrock-agent start-ingestion-job \
  --knowledge-base-id LJSELALSFJ \
  --data-source-id NEW_DATASOURCE_ID
```

### Step 5: Test and Validate

```bash
# Test KB search
awscurl --service execute-api --region us-east-1 \
  -X POST "$API_URL/kb/search" \
  -d '{"query": "password reset", "max_results": 5}'

# Verify scores improved (should be 0.70+)
```

---

## Expected Improvements

| Metric | Before | After |
|--------|--------|-------|
| Avg relevance score | 0.45 | 0.75+ |
| Useful results in top 3 | 1-2 | 3 |
| Agent finds KB match | 40% | 80%+ |
| Response quality | B | A |

---

## Timeline

| Phase | Task | Effort | Priority |
|-------|------|--------|----------|
| 1 | Update AppFlow fields | 1 hour | High |
| 2 | Create transformation Lambda | 2 hours | High |
| 3 | Reconfigure KB chunking | 1 hour | High |
| 4 | Add metadata filtering | 2 hours | Medium |
| 5 | Separate data sources | 2 hours | Low |

---

## References

- [Bedrock KB Chunking Strategies](https://docs.aws.amazon.com/bedrock/latest/userguide/kb-chunking-parsing.html)
- [Metadata Filtering](https://docs.aws.amazon.com/bedrock/latest/userguide/kb-test-config.html)
- [AppFlow Salesforce Connector](https://docs.aws.amazon.com/appflow/latest/userguide/salesforce.html)
