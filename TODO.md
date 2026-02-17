# TODO - Salesforce AI Case Analysis Agent

## ✅ Completed

- [x] Security fixes: CORS restricted, KMS wildcard removed, input validation
- [x] Lambda concurrency increased 2 → 20
- [x] Lazy client initialization, type hints, retry logic
- [x] Agent instructions with category-specific guidance + AI disclaimer
- [x] KB-first agent instructions + anti-hallucination rules
- [x] 11 additional case fields, description limit 32K
- [x] KB source citations (`kb_articles` with real SOP names)
- [x] JSON response parsing with regex fallback
- [x] Plain text formatting + HTML hyperlinks in Similar Cases
- [x] User permission awareness (admin vs self-service)
- [x] AI Feedback loop (`AI_Feedback__c` + `AI_Feedback_Comments__c`)
- [x] `AI_Analysis_Status__c` field (renamed from Agent_Analysis_Status__c)
- [x] Permission set `AI_Case_Analysis_User`
- [x] SF health check in `/health` endpoint (tests JWT auth)
- [x] Deployed to InttestJune25 sandbox
- [x] Resource naming refactored to `sf-case-analysis`
- [x] Sandbox Refresh Guide + .gitignore cleanup
- [x] Shared Lambda layers (`rackspace_sf_auth` + `rackspace_sf_queries`)
- [x] Shared action group (generic SOQL query Lambda)
- [x] Deterministic KA search (bypasses Nova Pro bad keyword selection)
- [x] kb_articles scoring (threshold ≥2, fallback ≥1 top 3)
- [x] Similar cases AND filter (`support_reason AND keywords`)
- [x] Dual-path steps (`admin_steps` + `user_steps` with section headers)
- [x] HTML step formatting (bold headers + numbered `<ol>` per section)
- [x] Guardrail tuning (`PROMPT_ATTACK` HIGH→LOW)
- [x] New sandbox deployment (account `783330585869`, profile `SANDBOX15FEB`)
- [x] Conditional EventBridge (skip when `salesforce_event_source` empty)
- [x] Guardrail `PROMPT_ATTACK` LOW in Terraform (no manual fix needed)
- [x] Case-insensitive KB article dedup (no caps duplicates)
- [x] Self_Resolvable auto-set true when `user_steps` exist
- [x] Enforced all JSON fields as REQUIRED in prompt (fixes Nova Pro inconsistency)
- [x] Raw agent response logging for debugging
- [x] SF Event Relay created for new sandbox (`Case_AI_Analysis_15Feb__chn`)
- [x] E2E flow verified on new sandbox (Client Partner test case — all fields populated)

---

## 🔴 High Priority

- [x] **Strip "create a case" user_steps in post-processing** — Completed (2026-02-17): post-processing now removes circular case-submission user steps and suppresses USER SELF-SERVICE section when filtered result is empty
- [x] **KB Sources hyperlinks fixed** — Query actual `UrlName` from SF KnowledgeArticleVersion, use pre-fetched URL map for hyperlinks (no more broken smart-quote URLs)
- [x] **Tool__c added to similar cases AND filter** — searchSimilarCases SOQL includes Tool__c as AND condition
- [x] **Code cleanup** — Duplicate Status bug fix, KB scoring refactor, guardrail cache, error logging, variable shadowing, contextlib removal, Optional→union syntax
- [x] **Test suite** — 66 tests (handler, salesforce_client, action_group) all passing
- [x] **Re-add closed cases to KB** — Not needed by design (2026-02-17): similar-case retrieval is handled via Salesforce action groups, not KB case ingestion
- [x] **AppFlow field optimization** — Not needed by design (2026-02-17): AppFlow closed-case pipeline is not used for agent similar-case retrieval
- [x] **Transformation Lambda** — Not needed by design (2026-02-17): no AppFlow JSON→KB case transformation path required

---

## 🟡 Medium Priority

- [ ] **KB chunking** — Increase chunk size to 800 tokens
- [ ] **Metadata filtering** — Add Category, Priority, Tool filters to KB queries
- [ ] **Delete old `Agent_Analysis_Status__c` field** — Replaced by `AI_Analysis_Status__c`, migrate data first
- [ ] **Salesforce field population** — Ensure Case_Type__c, Case_Closure_Notes__c filled consistently
- [ ] **API Gateway prod cutover decision** — During production deployment, either disable API Gateway entirely (event-driven only) or keep it with explicit hardening/ownership (IAM policy, usage plan/key strategy, monitoring, docs)

---

## 🟢 Low Priority

- [ ] Separate KB data sources (Cases, KAV, Emails)
- [ ] Resolution templates for common request types
- [ ] Monitoring dashboard for agent performance
- [ ] Feedback analytics — track AI accuracy trends from AI_Feedback__c data
