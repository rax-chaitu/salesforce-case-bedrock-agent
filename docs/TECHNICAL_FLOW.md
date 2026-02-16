# Technical Flow Documentation

## End-to-End Case Analysis Flow

### 1. Event Trigger (Salesforce → AWS)

```
Salesforce Case Created
    ↓
CaseHandler.cls (Apex Trigger)
    ↓
Integration_Event__e (Platform Event)
    ↓
Event Relay: Case_AI_Analysis_15Feb__chn
    ↓
EventBridge Partner Bus: aws.partner/salesforce.com/00DOx00000H4fXRMAZ/0YLOx000000EZ17OAG
    ↓
EventBridge Rule: sf-case-event-rule (filters: Object_Name__c=Case, Type__c=CREATE)
    ↓
SQS Queue: sf-case-queue
    ↓
Lambda: sf-case-processor (triggered by SQS)
```

**Event Payload Structure:**
```json
{
  "detail": {
    "payload": {
      "Record_Id__c": "500xxx",
      "Payload__c": "{\"Case_Number__c\":\"00151191\",\"Subject__c\":\"Test\",\"Tool__c\":\"Salesforce\",...}"
    }
  }
}
```

**Note:** `Payload__c` is a JSON STRING inside JSON - requires double parsing.

---

## 2. Case Processor Lambda Flow

### A. Extract Case Data

**File:** `lambda/case_processor/handler.py` (lines 218-230)

```python
# Parse nested JSON
event_payload = detail.get("payload", {})
case_id = event_payload.get("Record_Id__c")
payload_str = event_payload.get("Payload__c", "{}")
case_data = json.loads(payload_str)  # Parse the nested JSON STRING

# Extract key fields
subject = case_data.get("Subject__c", "")
support_reason = case_data.get("Support_Reason__c", "")
tool = case_data.get("Tool__c", "")
```

### B. Deterministic Knowledge Article Search

**File:** `lambda/case_processor/handler.py` (lines 231-249)

**Why?** Nova Pro picks poor keywords. We do a deterministic SOQL search first.

```python
# Extract words from subject + support_reason + tool (words > 3 chars)
search_words = set()
for text in [subject, support_reason, tool]:
    search_words.update(w for w in re.findall(r'\w+', text.replace("-", " ").replace("/", " ")) if len(w) > 3)

# Build SOQL query
like_clauses = [f"Title LIKE '%{w}%'" for w in list(search_words)[:8]]
kav_query = (
    f"SELECT Title FROM KnowledgeArticleVersion "
    f"WHERE PublishStatus = 'Online' AND Language = 'en_US' "
    f"AND ({' OR '.join(like_clauses)}) LIMIT 10"
)
kav_results = sf.query(kav_query)
ka_titles = [r["Title"] for r in kav_results.get("records", [])]
```

**Result:** Up to 10 Knowledge Article titles stored in `ka_titles`.

### C. Build Agent Prompt

**File:** `lambda/case_processor/handler.py` (lines 254-276)

```python
prompt = f"""Analyze this Salesforce case. Use these search parameters:
- searchSimilarCases: keywords="{keywords}", support_reason="{support_reason}", case_tool="{tool}"
- searchKnowledgeArticles: keywords="{keywords}"

Case data:
{json.dumps(case_data, indent=2, default=str)}

Search the SOP Knowledge Base first, then call searchSimilarCases, then call searchKnowledgeArticles...
"""
```

**Key:** Prompt tells agent to use `case_tool` parameter (not `tool` - reserved word in Bedrock).

---

## 3. Bedrock Agent Invocation

### A. Automatic Vector Search (Bedrock KB)

**When:** Happens automatically when agent is invoked
**Source:** 72 SOP documents in `s3://sfkaandsop-783330585869/SOP_FOR_DS/`
**How:**
- Bedrock uses entire prompt as semantic search query
- Titan Embeddings v2 converts prompt → vector
- Searches vector store for similar chunks
- Returns top chunks as "retrieved references" to agent

**No code needed** - Bedrock handles this automatically.

### B. Agent Calls Action Groups

**Agent ID:** `FHMNVBFZDE`
**Model:** Nova Pro v1 (`us.amazon.nova-pro-v1:0`)
**Guardrail:** `0wamk3wf1hk1` (PROMPT_ATTACK=LOW, others MEDIUM/HIGH)

Agent makes 2 function calls:

#### 1. searchSimilarCases

**Lambda:** `sf-case-action-group`
**File:** `lambda/action_group/handler.py` (lines 28-127)

**Parameters received:**
```json
{
  "keywords": "Add Client Partner",
  "support_reason": "Opportunity - Add/Change Team Member or Split",
  "case_tool": "Salesforce",
  "max_results": 10
}
```

**SOQL Query Built:**
```sql
SELECT Id, CaseNumber, Subject, Support_Reason__c, Description, 
       Case_Closure_Notes__c, ClosedDate, Close_Codes__c, Close_Reason__c,
       Root_Cause_of_Inquiry__c, Tool__c, Department__c, Segment__c,
       DP_Resolution__c, Admin_Notes__c,
       (SELECT CommentBody FROM CaseComments ORDER BY CreatedDate DESC LIMIT 3),
       (SELECT Subject, TextBody FROM EmailMessages ORDER BY CreatedDate DESC LIMIT 3)
FROM Case 
WHERE Status IN ('Closed', 'Closed Resolved')
  AND Support_Reason__c = 'Opportunity - Add/Change Team Member or Split'
  AND (Subject LIKE '%Add%' OR Subject LIKE '%Client%' OR Subject LIKE '%Partner%')
  AND Tool__c = 'Salesforce'
  AND Status = 'Closed'
  AND ClosedDate != null
ORDER BY ClosedDate DESC NULLS LAST 
LIMIT 30
```

**Content-Prioritized Ranking (lines 73-82):**
```python
def content_score(r):
    comments = len((r.get("CaseComments") or {}).get("records", []))
    emails = len((r.get("EmailMessages") or {}).get("records", []))
    has_closure = 1 if r.get("Case_Closure_Notes__c") else 0
    has_resolution = 1 if r.get("DP_Resolution__c") else 0
    return (comments * 3) + (emails * 2) + has_closure + has_resolution

all_records.sort(key=content_score, reverse=True)
all_records = all_records[:max_results]  # Take top 10 after ranking
```

**Why fetch 3x?** Recent cases have no emails/comments. Fetching 30 and ranking ensures we get content-rich cases.

**Chatter Fetch (lines 84-99):**
```python
# FeedItem doesn't support subqueries - batch fetch separately
fr = sf.query(
    f"SELECT ParentId, Body FROM FeedItem "
    f"WHERE ParentId IN ('{id_list}') AND Type = 'TextPost' "
    f"ORDER BY CreatedDate DESC"
)
```

**Returns to agent:**
```json
{
  "cases": [
    {
      "case_number": "00144236",
      "subject": "Please add name in OPPURTUNITY TEAM...",
      "support_reason": "Opportunity - Add/Change Team Member or Split",
      "tool": "Salesforce",
      "description": "...",
      "closure_notes": "...",
      "comments": "Comment 1 | Comment 2 | Comment 3",
      "emails": "Subject: Re: ... Body: ...",
      "chatter": "Chatter post 1 | Chatter post 2",
      "closed_date": "2025-05-09T09:33:55.000+0000"
    }
  ],
  "total_found": 10
}
```

#### 2. searchKnowledgeArticles

**Lambda:** `sf-case-action-group`
**File:** `lambda/action_group/handler.py` (lines 160-184)

**Parameters received:**
```json
{
  "keywords": "Add Client Partner",
  "support_reason": "Opportunity - Add/Change Team Member or Split",
  "max_results": 5
}
```

**SOQL Query:**
```sql
SELECT Title, UrlName, ArticleNumber, Summary
FROM KnowledgeArticleVersion
WHERE PublishStatus = 'Online' 
  AND Language = 'en_US'
  AND (Title LIKE '%Add%' OR Title LIKE '%Client%' OR Title LIKE '%Partner%' 
       OR Title LIKE '%Opportunity%' OR Title LIKE '%Team%' OR Title LIKE '%Member%')
ORDER BY LastModifiedDate DESC
LIMIT 5
```

**Returns to agent:**
```json
{
  "articles": [
    {
      "title": "Submit an Opportunity Team Member Request",
      "url_name": "Submit-an-Opportunity-Team-Member-Request",
      "article_number": "KA-01234",
      "summary": "How to request changes to opportunity team..."
    }
  ],
  "total_found": 2
}
```

---

## 4. Agent Response Processing

### A. Parse Agent JSON

**File:** `lambda/case_processor/handler.py` (lines 306-327)

```python
# Agent returns JSON (sometimes with markdown code fences)
response_text = bedrock.invoke_agent(prompt, session_id)
json_match = re.search(r'```json\s*(\{.*?\})\s*```', response_text, re.DOTALL)
if json_match:
    analysis = json.loads(json_match.group(1))
else:
    analysis = json.loads(response_text)
```

**Expected fields:**
- `summary`, `category`, `severity`, `root_cause`
- `admin_steps`, `user_steps` (arrays)
- `similar_cases` (array of case numbers)
- `kb_articles` (array of titles/names)
- `estimated_resolution`, `recommendation`

### B. KB Article Scoring & Deduplication

**File:** `lambda/case_processor/handler.py` (lines 334-360)

**Step 1: Merge & Dedupe (case-insensitive)**
```python
# Combine deterministic KA titles + agent's articles
seen_lower = set()
all_articles = []
for t in list(ka_titles) + agent_articles:
    if t.lower() not in seen_lower:
        seen_lower.add(t.lower())
        all_articles.append(t)
```

**Step 2: Score by keyword overlap**
```python
# Extract case words (subject + description + support_reason)
combined = f"{subject} {desc_text} {support_reason}"
case_words = {w.lower() for w in re.findall(r'\w+', combined) if len(w) >= 3}

# Score each article
scored = []
for article in all_articles:
    title_words = {w.lower() for w in re.findall(r'\w+', article) if len(w) >= 3}
    score = len(case_words & title_words)  # Count overlapping words
    if score >= 2:
        scored.append((score, article))

# Sort by score descending
scored.sort(reverse=True, key=lambda x: x[0])
final_articles = [a for _, a in scored]
```

**Step 3: Fallback if no high-scoring articles**
```python
if not final_articles:
    # Fallback: top 3 with score >= 1
    fallback = [(s, a) for s, a in scored_all if s >= 1][:3]
    final_articles = [a for _, a in fallback]
```

**Result:** Only relevant KB articles with keyword overlap ≥ 2 (or top 3 with ≥ 1).

### C. Steps Merge & Formatting

**File:** `lambda/case_processor/handler.py` (lines 363-389)

**Step 1: Filter out "create a case" user_steps**
```python
# Strip circular advice (user already created the case!)
user_steps = analysis.get("user_steps", [])
if user_steps:
    filtered = []
    for step in user_steps:
        step_lower = step.lower()
        if any(phrase in step_lower for phrase in [
            "create a new case", "submit the case", "create a case",
            "open a case", "save and submit", "submit a case"
        ]):
            continue  # Skip this step
        filtered.append(step)
    user_steps = filtered
```

**Step 2: Merge admin_steps + user_steps with section headers**
```python
merged_steps = []
admin_steps = analysis.get("admin_steps", [])
if admin_steps:
    merged_steps.append("ADMIN STEPS:")
    merged_steps.extend(admin_steps)
if user_steps:
    merged_steps.append("USER SELF-SERVICE STEPS:")
    merged_steps.extend(user_steps)
```

**Step 3: Set self_resolvable**
```python
# Only set true if user_steps exist after filtering
if user_steps:
    analysis["self_resolvable"] = True
```

---

## 5. Salesforce Field Population

### A. AI_Analysis__c (Rich Text)

**File:** `lambda/case_processor/salesforce_client.py` (lines 103-133)

**Format:**
```html
<b>Summary</b><br>
Request to add user as Client Partner on opportunity...<br><br>

<b>Root Cause</b><br>
User needs to be added to opportunity team...<br><br>

<b>Recommendation</b><br>
Admin to add user to Opportunity Team...<br><br>

<b>Estimated Resolution</b><br>
15 minutes - field update...<br><br>

<b>Category</b><br>
Opportunity<br><br>

<b>Severity</b><br>
Medium<br><br>

<b>KB Sources</b>
<ul>
<li><a href="https://rax--inttest.sandbox.my.salesforce.com/articles/Knowledge/Submit-an-Opportunity-Team-Member-Request" target="_blank">Submit an Opportunity Team Member Request</a></li>
<li>SOP: Opportunity Team Changes Process</li>
</ul>
```

**KB Hyperlink Logic (lines 118-132):**
```python
# Only hyperlink REAL Salesforce Knowledge Articles
# SOP docs show as plain text
_real_ka_titles = {t.lower() for t in ka_titles}  # From deterministic search

for article in kb_articles:
    if article.lower() in _real_ka_titles:
        # Real SF KA - create hyperlink
        url_name = article.replace(" ", "-").replace("'", "")
        url = f"{instance_url}/articles/Knowledge/{url_name}"
        kb_html += f'<li><a href="{url}" target="_blank">{article}</a></li>'
    else:
        # SOP doc from Bedrock KB - plain text
        kb_html += f'<li>{article}</li>'
```

**Why?** SOP docs don't have SF URLs. Only real KAs get hyperlinks.

### B. AI_Suggestions__c (Rich Text)

**File:** `lambda/case_processor/salesforce_client.py` (lines 135-158)

**Format:**
```html
<br><b>ADMIN STEPS:</b>
<ol>
<li>Navigate to the Opportunity record with ID 500xxx.</li>
<li>Click on the 'Opportunity Team' related list.</li>
<li>Click on 'Add Team Member'.</li>
<li>Select the user and set the role to 'Client Partner'.</li>
<li>Save the changes.</li>
</ol>

<br><b>USER SELF-SERVICE STEPS:</b>
<ol>
<li>Navigate to the Opportunity record.</li>
<li>Click the drop-down arrow and select 'Team Member Request'.</li>
<li>Select role 'Client Partner' and click 'Submit'.</li>
</ol>
```

**Formatting Logic:**
```python
def _format_steps(self, steps_text):
    lines = steps_text.strip().split("\n")
    html = ""
    in_list = False
    
    for line in lines:
        line = line.strip()
        if not line:
            continue
        
        # Detect section headers
        if "STEPS:" in line.upper():
            if in_list:
                html += "</ol>"
                in_list = False
            html += f"<br><b>{line}</b>"
        else:
            # Regular step
            if not in_list:
                html += "<ol>"
                in_list = True
            # Remove leading numbers/bullets
            clean = re.sub(r'^[\d\.\-\*\)]+\s*', '', line)
            html += f"<li>{clean}</li>"
    
    if in_list:
        html += "</ol>"
    
    return html
```

### C. Similar_Cases__c (Rich Text)

**File:** `lambda/case_processor/salesforce_client.py` (lines 160-180)

**Format:**
```html
<b>Top 10 most recent similar closed cases:</b><br>
• <a href="https://rax--inttest.sandbox.my.salesforce.com/500Pe00000WvzKTIAZ" target="_blank">Case 00144900</a>: Add Members to the opportunity<br>
• <a href="https://rax--inttest.sandbox.my.salesforce.com/500Pe00000WMDXGIA5" target="_blank">Case 00144588</a>: Ownership Update and Addition of Customer Success Manager...<br>
...
```

**Hyperlink Logic:**
```python
for case_num in similar_cases[:10]:
    # Fetch case ID from Salesforce
    result = self.sf.query(f"SELECT Id, Subject FROM Case WHERE CaseNumber = '{case_num}'")
    if result["records"]:
        case_id = result["records"][0]["Id"]
        subject = result["records"][0]["Subject"][:80]
        url = f"{self.instance_url}/{case_id}"
        html += f'• <a href="{url}" target="_blank">Case {case_num}</a>: {subject}<br>'
```

### D. Other Fields

```python
{
    "AI_Analysis_Status__c": "Completed",  # or "Failed"
    "Self_Resolvable__c": True,  # if user_steps exist after filtering
}
```

---

## 6. Complete Flow Diagram

```
┌─────────────────────────────────────────────────────────────────────────┐
│                         CASE ANALYSIS FLOW                               │
└─────────────────────────────────────────────────────────────────────────┘

SF Case Created
    ↓
Platform Event → Event Relay → EventBridge → SQS → Lambda (case_processor)
    ↓
┌───────────────────────────────────────────────────────────────────────┐
│ CASE PROCESSOR                                                         │
│                                                                        │
│ 1. Parse nested JSON (Payload__c)                                     │
│ 2. Deterministic KA search (SOQL on subject+reason+tool words)        │
│ 3. Build prompt with case_tool parameter                              │
│ 4. Invoke Bedrock Agent                                               │
└───────────────────────────────────────────────────────────────────────┘
    ↓
┌───────────────────────────────────────────────────────────────────────┐
│ BEDROCK AGENT                                                          │
│                                                                        │
│ A. Automatic Vector Search (72 SOP docs in S3)                        │
│ B. Call searchSimilarCases action                                     │
│    - Fetch 30 cases (Tool__c AND Support_Reason__c AND Closed)        │
│    - Rank by content score (comments*3 + emails*2 + closure_notes)    │
│    - Return top 10 with emails/comments/chatter                        │
│ C. Call searchKnowledgeArticles action                                 │
│    - SOQL LIKE on keywords + support_reason words                      │
│    - Return up to 5 KAs                                                │
│ D. Return JSON analysis                                                │
└───────────────────────────────────────────────────────────────────────┘
    ↓
┌───────────────────────────────────────────────────────────────────────┐
│ CASE PROCESSOR (POST-PROCESSING)                                      │
│                                                                        │
│ 1. Parse agent JSON                                                   │
│ 2. Merge deterministic + agent KAs, dedupe (case-insensitive)         │
│ 3. Score KAs by keyword overlap (threshold ≥2, fallback ≥1 top 3)     │
│ 4. Filter user_steps (remove "create a case" circular advice)         │
│ 5. Merge admin_steps + user_steps with section headers                │
│ 6. Set self_resolvable = true if user_steps exist                     │
│ 7. Format fields with HTML                                            │
│    - AI_Analysis__c: Summary, Root Cause, Recommendation, KB Sources  │
│    - AI_Suggestions__c: ADMIN STEPS + USER SELF-SERVICE STEPS         │
│    - Similar_Cases__c: Hyperlinked case numbers                       │
│ 8. Update Salesforce case                                             │
└───────────────────────────────────────────────────────────────────────┘
    ↓
SF Case Updated (AI_Analysis_Status__c = "Completed")
```

---

## Key Design Decisions

### 1. Why "case_tool" instead of "tool"?
**Problem:** Bedrock agents treat "tool" as a reserved word - agent always sends empty string.
**Solution:** Renamed to `case_tool` to avoid conflict.

### 2. Why deterministic KA search?
**Problem:** Nova Pro picks poor keywords (e.g., "the", "and", "for").
**Solution:** Case processor does SOQL search using subject+reason+tool words before agent invocation.

### 3. Why fetch 3x cases and rank?
**Problem:** Recent cases (2025+) have no emails/comments. Sorting by ClosedDate DESC returns empty cases.
**Solution:** Fetch 30 cases, score by content richness, return top 10 with actual resolution details.

### 4. Why filter "create a case" from user_steps?
**Problem:** Agent suggests "create a case" as self-service step - but case already exists (circular advice).
**Solution:** Post-process user_steps to strip any step mentioning case creation/submission.

### 5. Why only hyperlink real SF KAs?
**Problem:** SOP docs from Bedrock KB don't have Salesforce URLs.
**Solution:** Track which KAs came from deterministic search (real SF KAs), only hyperlink those. Show SOP docs as plain text.

### 6. Why score KB articles?
**Problem:** Agent returns irrelevant KAs (e.g., "Create a Salesforce Case" for every request).
**Solution:** Score by keyword overlap with case text. Only keep KAs with score ≥ 2 (or top 3 with ≥ 1).

---

## Performance Metrics

| Operation | Time |
|-----------|------|
| Event Relay → SQS | ~2s |
| SQS → Lambda trigger | ~1s |
| Deterministic KA search | ~0.3s |
| Bedrock Agent invocation | ~20-25s |
| - Vector search (automatic) | ~2s |
| - searchSimilarCases | ~3s |
| - searchKnowledgeArticles | ~0.3s |
| - Agent reasoning | ~15s |
| Post-processing | ~0.5s |
| Salesforce case update | ~0.5s |
| **Total E2E** | **~25-30s** |

---

## Logging Events

All events logged as JSON for CloudWatch analysis:

| Event | Lambda | Details |
|-------|--------|---------|
| `case_processing_started` | case_processor | case_id, case_number |
| `analyze_start` | case_processor | subject, support_reason, tool, keywords |
| `ka_search_deterministic` | case_processor | count, titles |
| `search_params` | action_group | keywords, support_reason, case_tool, max_results |
| `soql_query` | action_group | Full SOQL query |
| `similar_cases_found` | action_group | count, cases (with subject, tool, reason, comments/emails counts, closed date) |
| `kav_query` | action_group | SOQL query for KAs |
| `kav_results` | action_group | found count, titles |
| `agent_raw_response` | case_processor | response_length, 2000 char preview |
| `agent_parsed` | case_processor | fields, similar_cases, kb_articles, steps counts, self_resolvable |
| `user_steps_filtered` | case_processor | original vs kept count |
| `analyze_complete` | case_processor | final kb_articles, similar_cases, steps count, field presence |
| `case_updated` | case_processor | success/failure |

---

## Error Handling

### Common Errors

1. **Case_Closure_Notes__c can't be filtered**
   - Long Text Area fields can't be in WHERE clause
   - Solution: Filter in post-processing via content scoring

2. **Tool parameter always empty**
   - "tool" is reserved word in Bedrock
   - Solution: Renamed to "case_tool"

3. **Agent returns markdown code fences**
   - Sometimes wraps JSON in ```json ... ```
   - Solution: Regex to extract JSON from code fences

4. **Similar cases return wrong tool**
   - Agent wasn't sending case_tool parameter
   - Solution: Made case_tool required in schema + updated agent instruction

5. **KB articles irrelevant**
   - Agent picks bad keywords
   - Solution: Deterministic search + keyword overlap scoring

---

## Future Enhancements

1. **Re-add closed cases to KB** - AppFlow sync removed, only SOPs remain
2. **Transformation Lambda** - Convert AppFlow JSON → structured text for better chunking
3. **KB chunking optimization** - Increase to 800 tokens
4. **Metadata filtering** - Add Category, Priority, Tool filters to KB queries
5. **Resolution templates** - Pre-built templates for common request types
6. **Feedback analytics** - Track AI accuracy trends from AI_Feedback__c data
