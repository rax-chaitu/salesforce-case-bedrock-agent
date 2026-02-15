# SF Agentic Case Resolver — Complete Project Context Document

Last Updated: February 10, 2026
Purpose: Portable context document for continuing this project in any AI assistant.

---

## A. PROJECT SUMMARY

### What This Project Is

The SF Agentic Case Resolver is an AI-powered system built by Venkata Chaitanya, a Salesforce Technical Lead at Rackspace. It automatically analyzes Salesforce support cases and provides solution recommendations by integrating Salesforce with AWS Bedrock.

Core Concept: When a support case is created in Salesforce, the system automatically sends it through an event-driven pipeline to an AWS Bedrock Agent, which searches a Knowledge Base of articles using semantic search (RAG), generates an analysis with recommended solutions, and writes the results back to the Salesforce case — all without human intervention.

### Goals

- Automate first-pass case analysis to reduce admin workload
- Achieve 50-60% case deflection through a three-tier strategy (native search → AI search → case creation)
- Demonstrate POC value to business stakeholders for Phase 2 funding
- Move from constrained AWS sandbox ($28 budget) to proper development infrastructure

### People Involved

- Venkata Chaitanya — Salesforce Technical Lead, project owner and developer
- Bryan — Colleague who contributed knowledge architecture guidance (SOP vs KB article structure)
- Business stakeholders — Approval authority for Phase 2 investment

### Current Status (as of Feb 2026)

- Phase: Proof of Concept (POC) — functional in sandbox environment
- Architecture: Finalized — Bedrock Agents with Knowledge Base (migrated away from AgentCore)
- Infrastructure: Managed via Terraform (IaC) with modular structure
- AI Model: Amazon Nova Pro v1 (upgraded from Claude 3 Haiku)
- Next milestone: Business presentation for stakeholder buy-in and Phase 2 approval

---

## B. CUSTOM INSTRUCTIONS (Reproduce in ChatGPT/Kiro)

### About the User

- Name: Venkata Chaitanya
- Role: Salesforce Technical Lead at Rackspace
- Experience: 6+ years Salesforce, newer to AWS Bedrock/AI services
- Learning style: Step-by-step with explanations of WHY, analogies for complex concepts
- Preferred tools: Terraform (IaC), AWS Console for learning, CLI for execution
- Environment: Rackspace Innovation Sandbox (us-east-1), budget-constrained

### How to Assist

- Explain concepts and terminology before diving into implementation
- Tell me WHY we're doing something, not just HOW
- Use analogies to explain complex AWS/AI concepts
- Warn me about common mistakes and gotchas
- Provide production-ready solutions with proper error handling
- Consider enterprise scalability, maintainability, and integration challenges
- Always fact-check technical information
- Python execution: use `python3` (not `python`)

### Technical Constraints

- AWS Region: us-east-1 (must be consistent across ALL services)
- Budget: Rackspace Innovation Sandbox with limited funding (~$28)
- AI Model: Amazon Nova Pro v1 (model ID: `amazon.nova-pro-v1:0`)
- Salesforce Environment: UAT Sandbox (inttest)
- Infrastructure: All Terraform-managed
- Architecture preference: Managed services over custom code, minimal Apex

---

## C. KEY KNOWLEDGE (From Project Files & Conversations)

### C1. Current Architecture (FINAL — Post-Migration)

The architecture evolved from complex AgentCore to simplified Bedrock Agents — a 60% complexity reduction with 47% cost savings.

```
CURRENT PRODUCTION ARCHITECTURE:

  SF Case Created
      ↓
  Apex Trigger → Platform Event (Integration_Event__e)
      ↓
  Event Relay (AWS_Integration_UAT_TEST — configured, running)
      ↓
  Amazon EventBridge (pattern matching: Object_Name__c = "Case", Type__c = "CREATE")
      ↓
  Amazon SQS (buffering, retry with DLQ, 3 max retries)
      ↓
  AWS Lambda (orchestrator — parses event, invokes Bedrock Agent)
      ↓
  Bedrock Agent (Amazon Nova Pro v1)
      ├── Knowledge Base (Salesforce Knowledge Articles via S3 Vectors)
      └── Writes back via Salesforce REST API (JWT Bearer Token)
      ↓
  Case updated with:
    • AI_Analysis__c (summary + recommendation)
    • AI_Suggestions__c (resolution steps)
    • Self_Resolvable__c (boolean)
    • Similar_Cases__c (related cases as HTML links)
    • AI_Analysis_Status__c (Completed/Failed)
    • AI_Analyzed_Date__c (timestamp)
```

Why SQS between EventBridge and Lambda: Handles batch case creation spikes, provides automatic retries (up to 3), routes failures to Dead Letter Queue with CloudWatch alarm.

Why NOT AgentCore: AgentCore required ECR + Docker containers, 465+ lines of Lambda code, 8+ IAM policies. Bedrock Agents is config-driven, lower maintenance, and better for SF-focused teams.

### C2. Project Structure (Actual)

```
├── README.md                        # Main documentation
├── TODO.md                          # Active task tracking
├── .env.template                    # Reference only (not used)
├── .gitignore                       # Comprehensive ignore rules
├── salesforce.key                   # JWT private key (DO NOT COMMIT)
├── salesforce.crt                   # JWT certificate (upload to SF)
│
├── .kiro/
│   ├── steering/
│   │   └── salesforce-bedrock-agent.md  # Kiro steering rules
│   └── specs/
│       └── terraform-fundamentals/      # Learning curriculum spec
│           ├── requirements.md
│           ├── design.md
│           └── tasks.md
│
├── lambda/
│   ├── case_processor/              # Main Lambda function
│   │   ├── handler.py               # Dual-mode handler (SQS + API Gateway)
│   │   ├── bedrock_client.py        # Bedrock Agent client with retry logic
│   │   ├── salesforce_client.py     # SF JWT auth client (simple-salesforce)
│   │   ├── requirements.txt         # Python deps: boto3, simple-salesforce, PyJWT, cryptography, requests
│   │   ├── __init__.py
│   │   └── lambda_package/          # Built dependencies (gitignored)
│   └── appflow_ka_transformer/      # Planned: KB data transformation Lambda (empty)
│
├── salesforce/
│   └── force-app/main/default/
│       └── objects/
│           └── Integration_Event__e/  # Platform Event metadata (fields dir empty in repo)
│
├── scripts/
│   └── generate_ka_from_sops.py     # SOP-to-Knowledge-Article converter (docx → CSV)
│
├── presentation/
│   └── index.html                   # Business stakeholder presentation (10-slide deck)
│
├── terraform/
│   ├── main.tf                      # Root module — wires all modules together
│   ├── variables.tf                 # All variable definitions
│   ├── terraform.tfvars.example     # Template for tfvars
│   ├── terraform.tfvars             # Actual values (gitignored)
│   ├── locals.tf                    # Computed values, common tags
│   ├── api_gateway.tf               # REST API for testing (IAM auth, throttling)
│   ├── step_functions.tf            # AppFlow + KB sync orchestration
│   ├── scheduled_sync.tf            # EventBridge schedule for KB sync
│   ├── aws-auth.sh                  # AWS credential helper script
│   ├── test-agent.sh                # API testing script (awscurl/Lambda direct)
│   └── modules/
│       ├── bedrock_agent/           # Agent + KB association + aliases (DEV/PROD) + prepare_agent
│       │   ├── main.tf
│       │   └── outputs.tf
│       ├── lambda/                  # Function + SQS trigger + IAM + pip install
│       │   └── main.tf
│       ├── sqs/                     # Queue + DLQ + CloudWatch alarm
│       │   └── main.tf
│       ├── eventbridge/             # Partner event bus + rule + SQS target
│       │   └── main.tf
│       ├── secrets/                 # SF JWT secret (create or reference existing)
│       │   └── main.tf
│       └── knowledge_base/          # Empty (KB created manually in console)
│
└── docs/                            # Comprehensive documentation
    ├── analysis/                    # Data analysis reports
    ├── architecture/                # System design docs
    ├── deployment/                  # Deploy & terraform guides
    ├── knowledge-base/              # KB setup & improvement
    └── salesforce/                  # SF config & auth
```

### C3. Lambda Handler — Dual-Mode Architecture

The Lambda (`handler.py`, ~350 lines) operates in two modes:

**Production Mode (SQS):** Salesforce → Platform Event → Event Relay → EventBridge → SQS → Lambda
- Parses double-nested JSON from Event Relay (`detail.payload.Payload__c` is a JSON string)
- Extracts 17+ case fields: Subject, Description, Type, Priority, Tool__c, Support_Reason__c, Reason, Record_Type__c, Status, Origin, Root_Cause_of_Inquiry__c, Case_Type__c, Department__c, Segment__c, OpportunityNumber__c
- Idempotency check: skips cases already analyzed today
- Returns `batchItemFailures` for SQS partial batch failure handling
- Trusted data from Salesforce — no input sanitization needed

**Development Mode (API Gateway):** REST API endpoints for testing
- `GET /health` — Health check (agent ID, SF configured status)
- `POST /agent/invoke` — Direct agent invocation
- `POST /case/analyze` — Case analysis with all 17+ fields
- `POST /kb/search` — Direct Knowledge Base vector search
- Input validation: Salesforce ID pattern check, string sanitization, length limits
- CORS restricted to specific Salesforce domains

**Key Features:**
- Lazy client initialization (reduces cold start)
- Structured JSON logging for CloudWatch Insights
- Reserved concurrency: 20 (up from 2, ~4,800 cases/hour capacity)
- Lambda timeout: 300s (5 min)
- Memory: 512MB
- Runtime: Python 3.11

### C4. Bedrock Client

`bedrock_client.py` handles:
- Agent invocation with streaming EventStream response processing
- Exponential backoff retry (3 attempts, 2/4/8s delays)
- Retryable errors: ThrottlingException, ServiceUnavailableException, InternalServerException
- Custom `BedrockAgentError` exception with error_code and retryable flag
- Direct Knowledge Base vector search (`retrieve` API)

### C5. Salesforce Client — JWT Bearer Token Flow

`salesforce_client.py` implements:
- JWT Bearer Token flow (NOT Client Credentials — Salesforce doesn't support it)
- Credentials from AWS Secrets Manager: `{ "client_id", "username", "private_key" }`
- Secret naming matches Glue job pattern: `salesforce-{env}-sandbox-jwt` or `salesforce-production-jwt`
- Auth URL: `https://test.salesforce.com` (sandbox) or `https://login.salesforce.com` (prod)
- Uses `simple-salesforce` library (v62.0 API)
- Idempotency: `is_already_analyzed()` checks `AI_Analysis_Status__c = 'Completed'` AND `AI_Analyzed_Date__c` is today
- Case update writes: AI_Analysis__c, AI_Suggestions__c, Self_Resolvable__c, Similar_Cases__c, AI_Analyzed_Date__c, AI_Analysis_Status__c
- Similar cases formatted as HTML hyperlinks with Case ID lookup
- Failure handling: writes "Failed" status + error message on exception

### C6. Bedrock Agent Instructions (Comprehensive)

The agent instructions in `terraform/modules/bedrock_agent/main.tf` are extensive (~200 lines). Key aspects:

**Context:** Internal SF admin requests (NOT customer support tickets)
- Opportunity changes (36%), User Access (8%), Account/Company (7%), Data Updates (7%), Pricing (6%), Configuration (5%), Integration (1.4%)

**Integration Systems:** QM (Quote Management), Raptor (data sync), JIRA, WorkSpan, Financial Force

**Analysis Approach:**
1. Identify request type
2. ALWAYS search Knowledge Base FIRST
3. Use KB content as primary source (not generic advice)
4. Fall back to general knowledge only if KB has no results
5. Provide actionable guidance with tool/process names from KB

**Response Format:** Structured JSON with: summary, category, severity, root_cause, steps, self_resolvable, similar_cases, kb_articles, estimated_resolution, recommendation, escalation_needed, escalation_reason, ai_disclaimer

**User Access Limitations:** Agent understands that most requestors are regular users with LIMITED permissions — never suggests admin-only actions to users.

**Memory:** Enabled with SESSION_SUMMARY (30 days, 20 recent sessions)

**Agent Aliases:** DEV (auto-versions on instruction change) and PROD (routing config ignored for manual promotion)

### C7. Terraform Infrastructure

**Root Configuration (`terraform/main.tf`):**
- Provider: AWS >= 5.0, Terraform >= 1.2
- 5 modules: bedrock_agent, secrets, sqs, eventbridge, lambda
- API Gateway defined in `api_gateway.tf` (separate from modules)
- Step Functions in `step_functions.tf`, scheduled sync in `scheduled_sync.tf`
- Outputs: api_gateway_url, bedrock_agent_id, dev/prod alias IDs, lambda_function_name, sqs_queue_url, sqs_dlq_url, kb_id, sfn_state_machine_arn

**Module Details:**

| Module | Key Resources | Notes |
|--------|--------------|-------|
| `bedrock_agent` | Agent, KB association, DEV/PROD aliases, IAM role, prepare_agent (null_resource) | Model permissions for Nova Pro, Nova Lite, Titan Embed v2 |
| `lambda` | Function, SQS trigger, IAM role (6 policies), CloudWatch logs, pip_install (null_resource) | Builds lambda_package via pip3 with manylinux2014_x86_64 platform |
| `sqs` | Main queue, DLQ, queue policy (EventBridge), CloudWatch alarm on DLQ | Visibility timeout = lambda_timeout + 30, 14-day retention |
| `eventbridge` | Partner event bus, event rule (Case/CREATE pattern), SQS target | Depends on salesforce_event_source variable |
| `secrets` | Secret (create or reference existing), secret version | Naming: salesforce-{env}-sandbox-jwt |

**API Gateway (`api_gateway.tf`):**
- REST API with proxy resource (catch-all routing)
- IAM authorization on all methods
- OPTIONS (CORS) with NONE auth for preflight
- Usage plan: 50 burst, 100 rps, 10,000/day quota
- Stage: `prod`

**Step Functions (`step_functions.tf`):**
- State machine: StartAppFlow → Poll (30s) → CheckStatus → StartKBSync → Poll (60s) → CheckStatus → Success/Fail
- IAM: AppFlow permissions, Bedrock KB permissions, CloudWatch logs
- Prerequisite: AppFlow flow must be created manually (OAuth requires interactive auth)

**Scheduled Sync (`scheduled_sync.tf`):**
- Conditional creation (`enable_scheduled_sync` variable, default false)
- EventBridge schedule → Step Functions state machine
- Default: `cron(0 2 * * ? *)` (daily 2am UTC)

**Key Variables:**
- `project_name`: default "sf-case-analysis" (but README references "salesforceagent" — naming refactor pending)
- `foundation_model`: default "amazon.nova-pro-v1:0"
- `knowledge_base_id`: required, no default
- `salesforce_event_source`: default "" (set when Event Relay configured)
- `salesforce_environment`: default "inttest"
- `create_sf_secret`: default true
- `appflow_flow_name`: default "SYNCCASESWITHS3"
- `enable_scheduled_sync`: default false

### C8. Cost Breakdown (400 Cases/Month)

| Component | Monthly Cost | % of Total |
|-----------|-------------|-----------|
| OpenSearch Serverless (Vector Store) | $175.00 | 97.8% |
| Other AWS (Secrets, CloudWatch, Transfer) | $2.00 | 1.1% |
| AI Analysis (Nova Pro) | ~$0.60 | 0.3% |
| Lambda + EventBridge + SQS | ~$0.17 | 0.1% |
| KB Embeddings | $0.01 | 0.01% |
| **TOTAL** | **~$178/month** | |

Key insight: 98% of cost is OpenSearch Serverless (always-on). The actual AI work costs ~$1/month for 400 cases.

Note: README lists ~$14/month which excludes OpenSearch Serverless (the KB vector store). The $178 figure includes the always-on vector store.

### C9. Three-Tier Case Deflection Strategy (Future)

```
TIER 1: FREE — Salesforce Native Search (as user types)
  → LWC calls SOSL/SOQL in real-time, shows matching Knowledge Articles
  → No cost, no credits consumed
  → Expected deflection: 30-35%

TIER 2: AI POWERED — Bedrock Agent (on button click, consumes 1 credit)
  → Apex → API Gateway → Lambda → Bedrock Agent
  → Returns human-friendly AI response with semantic search
  → Rate-limited per user (monthly quota) to control costs
  → Expected additional deflection: 20-25%

TIER 3: CASE CREATION — Only When Needed
  → Case created with articles already viewed + AI response attached
  → Existing EventBridge → SQS → Lambda → Agent flow kicks in
  → Agent knows what user already tried
```

Credit System (cost control):
- Custom fields on User: AI_Credits_Monthly_Limit__c, AI_Credits_Used_This_Month__c
- Scheduled Apex resets credits monthly
- Different limits by role (Tier 1 Support: 50/mo, End Users: 10/mo, Admins: unlimited)

### C10. Knowledge Base Optimization

**Problem:** Raw AppFlow data pollutes vector embeddings
- AppFlow was pulling 323,000 documents instead of expected 46 articles
- Connector crawled unintended objects (Attachments, Share objects, custom objects)
- System IDs and noisy fields degrading search quality

**Solution:** Clean markdown transformation pipeline (planned, `lambda/appflow_ka_transformer/` is empty)
```
AppFlow (with filters: PublishStatus=Online, IsLatestVersion=true)
  → S3 /raw/ prefix
  → Lambda (parse, dedup by KnowledgeArticleId, strip HTML, generate .md + .metadata.json)
  → S3 /processed/ prefix
  → Bedrock KB Sync
  → Clean vectors
```

**Current KB Issues (from TODO.md):**
- AppFlow outputs 177 fields as raw JSON
- Bedrock chunks JSON into meaningless fragments
- Low relevance scores (0.4-0.5 instead of 0.7+)
- Need to select only needed fields and transform to structured text format

### C11. SOP-to-Knowledge-Article Converter

`scripts/generate_ka_from_sops.py` — Converts Word (.docx) SOP documents to Salesforce Knowledge Article CSV:
- Reads from `~/Downloads/SFDC SOP Files`
- Extracts structured content: paragraphs, tables, steps, notes, links
- Auto-categorizes by folder: Accounts, Companies, Opportunities, Leads, Tools Access, Users
- Generates: Title, UrlName, Question__c, Answer__c, Summary, Category
- Pattern-matching for question generation (creation, sync, merge, approval, etc.)
- Outputs timestamped CSV for Salesforce Data Loader import
- Requires `python-docx` library

### C12. Business Presentation

`presentation/index.html` — 10-slide HTML presentation for stakeholders:
1. Title slide
2. What Is This? (Today vs With POC)
3. Systems Involved (Salesforce + AWS)
4. Architecture (animated flow diagram)
5. Demo — What Happens (mock case with AI output)
6. What the AI Provides (structured output fields)
7. Who Benefits? (Admins, Sellers, Business)
8. Knowledge Articles (data quality importance)
9. What We've Built (POC summary)
10. (Remaining slides: asks/next steps)

### C13. Salesforce Configuration

**Platform Event:** `Integration_Event__e`
- Fields: Object_Name__c, Type__c, Record_Id__c, Payload__c (Long Text 32000)

**Custom Fields on Case:**
- AI_Analysis__c (Long Text Area 32000)
- AI_Suggestions__c (Long Text Area)
- Self_Resolvable__c (Checkbox)
- Similar_Cases__c (Rich Text — HTML hyperlinks)
- AI_Analyzed_Date__c (DateTime)
- AI_Analysis_Status__c (Picklist: Pending, Analyzing, Completed, Failed)

**Connected App:** AWS Bedrock Integration
- JWT Bearer Token flow with X.509 certificate
- Credentials stored in AWS Secrets Manager

**Event Relay:** AWS_Integration_UAT_TEST (status: RUN)
- Forwards Integration_Event__e to AWS EventBridge

### C14. Bryan's Knowledge Architecture Guidance

Bryan recommended a "teach it like a new Racker" approach with two-tier documentation:

| Type | Audience | Purpose |
|------|----------|---------|
| Agent Playbooks/SOPs | AI Agent | Decision trees, tool usage rules, approval workflows |
| KB Articles | End Users | Self-service instructions users follow themselves |

Key pattern: Human-in-the-loop — agent posts case comment before making system changes, waits for approval.

### C15. Kiro IDE Configuration

**Steering file** (`.kiro/steering/salesforce-bedrock-agent.md`):
- AWS authentication workflow (profile selection, token refresh)
- Known issues & solutions (6 documented)
- Key files reference
- Quick commands for Terraform, Lambda deployment, logs, KB sync, API testing
- Architecture quick reference
- Terraform drift workflow
- SF JWT setup checklist

**Spec** (`.kiro/specs/terraform-fundamentals/`):
- 9-module Terraform learning curriculum for Salesforce developers
- Uses Salesforce analogies throughout
- Practical exercises using the actual project
- Status: Spec defined (requirements, design, tasks), implementation pending

---

## D. WORK HISTORY (Chronological)

- **Jan 18, 2026** — Project kickoff, AWS sandbox setup, Claude 3 Haiku model access
- **Jan 19, 2026** — AgentCore deep dive, Python venv setup, S3 bucket for KB
- **Jan 20, 2026** — SF Connected App (OAuth 2.0), cost analysis ($175/mo OpenSearch), event-driven flow mapping
- **Jan 21, 2026** — First agent deployment, SCP restrictions resolved, KB ID established (X9LJCDTMV3)
- **Jan 22, 2026** — Architecture simplification: AgentCore → Bedrock Agents (60% complexity reduction)
- **Jan 27, 2026** — KB optimization: discovered 323K docs issue, AppFlow filters, Step Functions pipeline
- **Jan 29, 2026** — Security fixes (CORS, input validation), Lambda concurrency 2→20, retry logic, case data analysis (2000 cases)
- **Feb 3, 2026** — Bryan's SOP/KB architecture guidance, content categorization
- **Feb 7, 2026** — Three-tier deflection strategy, credit system, LWC mockup, business presentation
- **Feb 10, 2026** — Model upgraded to Amazon Nova Pro v1, SOP-to-KA converter script, project context refresh

---

## E. CURRENT STATE

### What's Working

- ✅ Bedrock Agent functional with Knowledge Base (POC proven)
- ✅ Event-driven pipeline: SF → EventBridge → SQS → Lambda → Bedrock Agent → SF update
- ✅ Terraform infrastructure as code (modular: 5 modules + API Gateway + Step Functions)
- ✅ Salesforce JWT Bearer Token authentication (simple-salesforce)
- ✅ Event Relay configured and running (AWS_Integration_UAT_TEST)
- ✅ Knowledge Base with S3 data source
- ✅ Dual-mode Lambda: SQS (production) + API Gateway (testing)
- ✅ Security: CORS restricted, input validation, IAM auth on API
- ✅ Retry logic with exponential backoff
- ✅ Idempotency check (skip already-analyzed cases)
- ✅ Lambda concurrency scaled to 20 (~4,800 cases/hour)
- ✅ DLQ with CloudWatch alarm for failed messages
- ✅ Step Functions pipeline for AppFlow + KB sync orchestration
- ✅ Business presentation (10-slide HTML deck)
- ✅ SOP-to-Knowledge-Article converter script
- ✅ Kiro steering file and Terraform learning spec

### What's In Progress

- 🔄 Business stakeholder presentation (React/HTML slide deck built)
- 🔄 Knowledge Base data quality optimization (cleaning AppFlow output)
- 🔄 AppFlow transformer Lambda (`lambda/appflow_ka_transformer/` — empty, planned)
- 🔄 Terraform fundamentals curriculum (spec defined, content not yet written)

### What's Blocked

- ⛔ AWS Account: Sandbox limited to $28 — need business approval for proper dev environment
- ⛔ Knowledge Articles: Too few articles in Salesforce — AI effectiveness limited
- ⛔ Article Quality: Existing articles not optimized for AI search
- ⛔ Salesforce metadata incomplete in repo: `force-app` only has Integration_Event__e object (fields dir empty), no Apex classes, no Case custom fields

---

## F. REMAINING WORK

### Immediate Priority (Phase 2 — Needs Business Approval)

1. Present POC to stakeholders — Get buy-in for continued investment
2. Secure proper AWS account — Options: dedicated Innovation account, existing Rackspace account, or extended sandbox
3. Knowledge Article initiative — Team/process for creating articles from closed cases
4. Article quality standards — Clear titles, detailed solutions, consistent formatting

### High Priority — KB Improvements (from TODO.md)

1. Update AppFlow to select only needed fields (CaseNumber, Subject, Description, Priority, Case_Type__c, Close_Codes__c, Case_Closure_Notes__c, Tool__c, Support_Reason__c, Department__c)
2. Create transformation Lambda (`appflow_ka_transformer`) to convert JSON → structured text
3. Reconfigure KB chunking — increase chunk size to 800 tokens
4. Add metadata filtering for Category, Priority, Tool

### Medium Priority — Before Production

1. Resource naming refactor: `salesforceagent` → `sf-case-analysis` (update tfvars, plan recreations, update Event Relay)
2. Salesforce field population: ensure Case_Type__c, Case_Closure_Notes__c are consistently filled
3. Complete Salesforce metadata in repo (Apex trigger, Case custom fields, Event Relay config)

### Phase 3: Case Deflection

- Build LWC case submission with three-tier search
- Implement credit/rate-limiting system
- Native SF search → AI search → Case creation flow
- Deflection metrics and reporting dashboards

### Phase 4: Production

- Security review and hardening
- Performance testing at scale
- User training and change management
- Go-live with monitoring and feedback loop

---

## G. RULES & PATTERNS

### Naming Conventions

- AWS resources: `sf-{object}-{function}` prefix (target), currently `salesforceagent` (pending refactor)
- Terraform files: Descriptive names (agent.tf, knowledge_bases.tf, step_functions.tf)
- S3 paths: /raw/ for AppFlow output, /processed/ for clean KB files
- Secrets: `salesforce-{env}-sandbox-jwt` or `salesforce-production-jwt`
- Terraform tags: Project + ManagedBy on all resources

### Technical Standards

- Region: Always us-east-1
- IaC: Everything in Terraform — no manual console-only resources in production
- Salesforce: Minimal custom Apex — keep SF as passive data consumer
- Architecture: Managed services over custom implementations
- Agent model: Amazon Nova Pro v1 (`amazon.nova-pro-v1:0`)
- KB embeddings: Amazon Titan Embed Text v2
- Python: 3.11 runtime, use `python3` for execution
- Lambda packaging: pip3 with `--platform manylinux2014_x86_64 --python-version 3.11 --only-binary=:all:`

### Key Lessons Learned

1. OpenSearch Serverless is the cost driver — not AI. Budget around $175/mo minimum.
2. AgentCore is overkill for this use case — Bedrock Agents is simpler and cheaper.
3. Memory is not needed for one-shot case analysis (but enabled for session summaries).
4. OAuth Client Credentials flow doesn't work with Salesforce — use JWT Bearer Token.
5. SCP restrictions in sandbox were model-specific, not blanket Bedrock blocks.
6. AppFlow filter configuration is critical — without filters, connector crawls everything.
7. File size limit of 50MB for Bedrock KB — partition large AppFlow outputs.
8. `prepare_agent` must be called after creating/updating a Bedrock Agent.
9. Lambda streaming response handling requires careful byte decoding.
10. KB data quality directly impacts AI quality — clean data in = good recommendations out.
11. Event Relay payload has double-nested JSON — `Payload__c` is a JSON string inside JSON.
12. Recreate secrets with AWS-managed key (not custom KMS) to avoid Lambda decrypt errors.

### Things to Avoid

- Don't put system IDs or metadata fields in KB article content (pollutes embeddings)
- Don't skip SQS between EventBridge and Lambda (loses retry/DLQ capability)
- Don't write one S3 file per record for large volumes (expensive PUT requests)
- Don't use AgentCore when Bedrock Agents suffices (unnecessary complexity)
- Don't create OpenSearch Serverless and leave it running unused (costs $175/mo 24/7)
- Don't use `client_credentials` grant type with Salesforce (not supported)
- Don't manually edit terraform.tfstate

---

## H. IMPORTANT CONTEXT

### This Is NOT a Chatbot

The system is a fully automated background process. Each case is analyzed exactly once with no follow-up interactions. There is no user-facing chat interface with the AI agent. Cases flow through the pipeline automatically.

### The Three-Tier Deflection Strategy Is Essential

The case deflection approach (native search → AI → case creation) isn't a nice-to-have — it's cost control. Without rate limiting, users could overuse the AI service and drive up AWS costs unpredictably.

### Business Context

Chaitanya is building this within Rackspace's Innovation Sandbox with tight budget constraints. The POC must demonstrate enough value to justify moving to a proper development environment with adequate resources. The business presentation is the critical gate for Phase 2.

### Stakeholder Asks (for the presentation)

- Which AWS account to use (sandbox is only $28)
- Knowledge article creation team/process
- Article quality standards
- Adding closed cases as KB data source
- Approval to proceed to Phase 2

### Key AWS Resource IDs

- Knowledge Base ID: X9LJCDTMV3
- Knowledge Base Name: "SF-Case-Knowledge-Base"
- AppFlow Flow Name: "SYNCCASESWITHS3"
- Secrets Manager Secret: `salesforce-inttest-sandbox-jwt`
- Event Relay Name: "AWS_Integration_UAT_TEST"
- Agent Framework: Bedrock Agents (NOT AgentCore)
- Model: Amazon Nova Pro v1 (`amazon.nova-pro-v1:0`)
- Lambda Function: `salesforceagent-api` (pending rename to `sf-case-analysis-api`)
- SQS Queue: `salesforceagent-case-analysis` (pending rename)

### Model Change Note

The original context document referenced Claude 3 Haiku (`anthropic.claude-haiku-4-5-20251001-v1:0`). The current Terraform configuration uses Amazon Nova Pro v1 (`amazon.nova-pro-v1:0`) as the foundation model, with Nova Lite as a fallback model in IAM permissions.

### Colleague Input

Bryan recommended structuring knowledge as "Agent Playbooks" (AI decision trees) separate from user-facing KB articles, following a "teach it like a new Racker" philosophy. This is a key architectural principle for content organization.

---

## I. DOCUMENTATION REFERENCE

| Topic | File |
|-------|------|
| Main README | `README.md` |
| Active TODOs | `TODO.md` |
| Full deployment | `docs/deployment/DEPLOYMENT_GUIDE.md` |
| Quick redeploy | `docs/deployment/QUICK_REDEPLOY.md` |
| Troubleshooting | `docs/IMPLEMENTATION_NOTES.md` |
| Event architecture | `docs/architecture/EVENT_DRIVEN_ARCHITECTURE.md` |
| AppFlow KB sync | `docs/knowledge-base/APPFLOW_KB_SYNC_SETUP.md` |
| KB improvement | `docs/knowledge-base/KB_IMPROVEMENT_GUIDE.md` |
| Terraform basics | `docs/deployment/TERRAFORM_BASICS.md` |
| Naming conventions | `docs/NAMING_CONVENTIONS.md` |
| API endpoints | `docs/API_SUMMARY.md` |
| SF auth | `docs/salesforce/SALESFORCE_AUTH_IMPLEMENTATION.md` |
| SF Connected App | `docs/salesforce/SALESFORCE_CONNECTED_APP_GUIDE.md` |
| Case data analysis | `docs/analysis/CASE_DATA_ANALYSIS_REPORT.md` |
| AgentCore comparison | `docs/architecture/AGENTCORE_VS_BEDROCK_AGENTS.md` |
| Kiro steering | `.kiro/steering/salesforce-bedrock-agent.md` |
| Terraform learning spec | `.kiro/specs/terraform-fundamentals/` |
