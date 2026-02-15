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

---

## 🔴 High Priority

- [ ] **Re-add closed cases to KB** — AppFlow sync removed, only SOPs remain. `similar_cases` always empty until case data is re-ingested
- [ ] **AppFlow field optimization** — Select only needed fields (CaseNumber, Subject, Description, Close_Codes__c, etc.) instead of all 177
- [ ] **Transformation Lambda** — Convert AppFlow JSON → structured text for better KB chunking
- [ ] **Complete inttest E2E verification** — Start Event Relay, test full case flow

---

## 🟡 Medium Priority

- [ ] **KB chunking** — Increase chunk size to 800 tokens
- [ ] **Metadata filtering** — Add Category, Priority, Tool filters to KB queries
- [ ] **Delete old `Agent_Analysis_Status__c` field** — Replaced by `AI_Analysis_Status__c`, migrate data first
- [ ] **Salesforce field population** — Ensure Case_Type__c, Case_Closure_Notes__c filled consistently

---

## 🟢 Low Priority

- [ ] Separate KB data sources (Cases, KAV, Emails)
- [ ] Resolution templates for common request types
- [ ] Monitoring dashboard for agent performance
- [ ] Feedback analytics — track AI accuracy trends from AI_Feedback__c data
