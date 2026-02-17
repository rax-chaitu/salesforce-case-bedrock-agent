"""
Bedrock Agent Action Group - Case-specific Salesforce searches.
Routes: /searchSimilarCases, /searchKnowledgeArticles
Uses shared layers: rackspace_sf_auth (auth) + rackspace_sf_queries (query helpers)

NOTE: Generic SOQL queries (/querySalesforce) live in the shared action group
at lambda/shared_action_group/handler.py — reusable across all future agents.
"""

import json
import logging

from rackspace_sf_auth import SalesforceAuthClient

logger = logging.getLogger()
logger.setLevel(logging.INFO)

_sf_auth = None


def get_sf():
    """Lazy init SF connection from shared auth layer."""
    global _sf_auth
    if _sf_auth is None:
        _sf_auth = SalesforceAuthClient()
    return _sf_auth.get_connection()


def search_similar_cases(params):
    """
    Search Salesforce for similar closed cases with content-prioritized ranking.
    
    Flow:
    1. Build SOQL WHERE clause (Support_Reason__c AND Tool__c AND keywords AND Status=Closed)
    2. Fetch 3x requested cases (to find content-rich ones)
    3. Fetch subqueries: CaseComments, EmailMessages
    4. Batch-fetch Chatter FeedItems (can't use subquery)
    5. Score cases by content richness (comments*3 + emails*2 + closure_notes + resolution)
    6. Sort by score descending, return top N
    
    Why fetch 3x?
    - Recent cases (2025+) have no emails/comments
    - Older cases (2024) have rich email conversations
    - Fetching 30 and ranking ensures we get content-rich cases
    
    Example Input:
        {
            "keywords": "Add Client Partner",
            "support_reason": "Opportunity - Add/Change Team Member or Split",
            "case_tool": "Salesforce",
            "max_results": 10
        }
    
    Example SOQL:
        SELECT Id, CaseNumber, Subject, ..., 
               (SELECT CommentBody FROM CaseComments LIMIT 3),
               (SELECT Subject, TextBody FROM EmailMessages LIMIT 3)
        FROM Case
        WHERE Status = 'Closed'
          AND Support_Reason__c = 'Opportunity - Add/Change Team Member or Split'
          AND (Subject LIKE '%Add%' OR Subject LIKE '%Client%' OR Subject LIKE '%Partner%')
          AND Tool__c = 'Salesforce'
          AND ClosedDate != null
        ORDER BY ClosedDate DESC
        LIMIT 30
    
    Example Output:
        {
            "cases": [
                {
                    "case_number": "00144236",
                    "subject": "Please add name in OPPURTUNITY TEAM...",
                    "tool": "Salesforce",
                    "support_reason": "Opportunity - Add/Change Team Member or Split",
                    "comments": "Comment 1 | Comment 2",
                    "emails": "Subject: Re: ... Body: ...",
                    "chatter": "Chatter post 1 | Chatter post 2",
                    "closed_date": "2025-05-09T09:33:55.000+0000"
                }
            ],
            "total_found": 10
        }
    """
    keywords = params.get("keywords", "")
    support_reason = params.get("support_reason", "")
    tool = params.get("case_tool", "")
    max_results = min(int(params.get("max_results", 10)), 50)
    
    logger.info(json.dumps({"event": "search_params", "keywords": keywords, "support_reason": support_reason, "case_tool": tool, "max_results": max_results}))

    sf = get_sf()
    base_conditions = ["Status IN ('Closed', 'Closed Resolved')", "ClosedDate != null"]

    # Build WHERE clause: Support_Reason__c AND keywords AND Tool__c
    keyword_conditions = []
    for word in [w for w in keywords.split()[:5] if len(w) > 2]:
        safe = word.replace("'", "\\'")
        keyword_conditions.append(f"Subject LIKE '%{safe}%'")

    conditions = list(base_conditions)
    if support_reason:
        safe_reason = support_reason.replace("'", "\\'")
        conditions.append(f"Support_Reason__c = '{safe_reason}'")
        # If we also have keywords, add as AND to narrow within same reason
        if keyword_conditions:
            conditions.append(f"({' OR '.join(keyword_conditions)})")
    elif keyword_conditions:
        # No support_reason — use keywords only
        conditions.append(f"({' OR '.join(keyword_conditions)})")

    if tool:
        safe_tool = tool.replace("'", "\\'")
        conditions.append(f"Tool__c = '{safe_tool}'")

    where = " AND ".join(conditions)
    
    # ============================================================================
    # FETCH 3X CASES FOR CONTENT-PRIORITIZED RANKING
    # ============================================================================
    # Why: Recent cases have no emails/comments. Fetching 30 and ranking by content
    #      ensures we return cases with actual resolution details.
    # ============================================================================
    fetch_limit = max_results * 3
    def build_query(where_clause):
        return (
            f"SELECT Id, CaseNumber, Subject, Support_Reason__c, Description, "
            f"Case_Closure_Notes__c, ClosedDate, Close_Codes__c, Close_Reason__c, "
            f"Root_Cause_of_Inquiry__c, Tool__c, Department__c, Segment__c, "
            f"DP_Resolution__c, Admin_Notes__c, "
            f"(SELECT CommentBody FROM CaseComments ORDER BY CreatedDate DESC LIMIT 3), "
            f"(SELECT Subject, TextBody FROM EmailMessages ORDER BY CreatedDate DESC LIMIT 3) "
            f"FROM Case WHERE {where_clause} "
            f"ORDER BY ClosedDate DESC NULLS LAST LIMIT {fetch_limit}"
        )

    query = build_query(where)

    logger.info(json.dumps({"event": "soql_query", "query": query}))
    results = sf.query(query)
    all_records = results.get("records", [])

    # If keyword narrowing is too strict, retry once using support_reason/tool only.
    if not all_records and keyword_conditions and (support_reason or tool):
        fallback_conditions = list(base_conditions)
        if support_reason:
            safe_reason = support_reason.replace("'", "\\'")
            fallback_conditions.append(f"Support_Reason__c = '{safe_reason}'")
        if tool:
            safe_tool = tool.replace("'", "\\'")
            fallback_conditions.append(f"Tool__c = '{safe_tool}'")

        fallback_where = " AND ".join(fallback_conditions)
        fallback_query = build_query(fallback_where)
        logger.info(json.dumps({"event": "soql_query_fallback", "query": fallback_query}))
        results = sf.query(fallback_query)
        all_records = results.get("records", [])
    
    # ============================================================================
    # CONTENT-PRIORITIZED RANKING
    # ============================================================================
    # Why: Recent cases (2025+) have no emails/comments. Sorting by ClosedDate DESC
    #      returns empty cases. We need cases with actual resolution details.
    #
    # Scoring Formula:
    #   score = (comments * 3) + (emails * 2) + has_closure_notes + has_resolution
    #
    # Example:
    #   Case A (2025): 0 comments, 0 emails, no closure notes → score = 0
    #   Case B (2024): 0 comments, 3 emails, has closure notes → score = 0 + 6 + 1 = 7 ✅
    #   Case C (2024): 2 comments, 1 email, has closure notes → score = 6 + 2 + 1 = 9 ✅
    #
    # Result: Cases B and C ranked higher than A, even though A is more recent
    # ============================================================================
    def content_score(r):
        comments = len((r.get("CaseComments") or {}).get("records", []))
        emails = len((r.get("EmailMessages") or {}).get("records", []))
        has_closure = 1 if r.get("Case_Closure_Notes__c") else 0
        has_resolution = 1 if r.get("DP_Resolution__c") else 0
        return (comments * 3) + (emails * 2) + has_closure + has_resolution
    
    all_records.sort(key=content_score, reverse=True)
    all_records = all_records[:max_results]  # Take top N after ranking

    # Log each case with its child record counts
    case_summary = []
    for r in all_records:
        comments_count = len((r.get("CaseComments") or {}).get("records", []))
        emails_count = len((r.get("EmailMessages") or {}).get("records", []))
        case_summary.append({
            "case": r.get("CaseNumber", ""),
            "subject": (r.get("Subject") or "")[:80],
            "tool": r.get("Tool__c") or "",
            "reason": r.get("Support_Reason__c") or "",
            "comments": comments_count,
            "emails": emails_count,
            "closed": r.get("ClosedDate") or ""
        })
    logger.info(json.dumps({"event": "similar_cases_found", "count": len(all_records), "cases": case_summary}))

    # ============================================================================
    # BATCH-FETCH CHATTER FEEDITEMS
    # ============================================================================
    # Why: FeedItem doesn't support subqueries in SOQL
    # Solution: Fetch separately using ParentId IN (...) after getting case IDs
    #
    # Example:
    #   Case IDs: ['500Pe00000WvzKTIAZ', '500Pe00000WMDXGIA5']
    #   SOQL: SELECT ParentId, Body FROM FeedItem 
    #         WHERE ParentId IN ('500Pe00000WvzKTIAZ', '500Pe00000WMDXGIA5')
    #         AND Type = 'TextPost'
    #   Result: {
    #       '500Pe00000WvzKTIAZ': ['Chatter post 1', 'Chatter post 2'],
    #       '500Pe00000WMDXGIA5': ['Chatter post 3']
    #   }
    # ============================================================================
    chatter_map = {}
    case_ids = [r.get("Id", "") for r in all_records if r.get("Id")]
    if case_ids:
        try:
            id_list = "','".join(case_ids)
            fr = sf.query(
                f"SELECT ParentId, Body FROM FeedItem "
                f"WHERE ParentId IN ('{id_list}') AND Type = 'TextPost' "
                f"ORDER BY CreatedDate DESC"
            )
            for item in fr.get("records", []):
                pid = item.get("ParentId", "")
                if item.get("Body"):
                    chatter_map.setdefault(pid, []).append(item["Body"][:200])
        except Exception as e:
            logger.warning(f"Chatter fetch failed: {e}")

    cases = []
    for r in all_records:
        cid = r.get("Id", "")
        # Extract subquery results
        comment_recs = (r.get("CaseComments") or {}).get("records", [])
        comments = " | ".join(c.get("CommentBody", "") for c in comment_recs if c.get("CommentBody"))
        email_recs = (r.get("EmailMessages") or {}).get("records", [])
        emails = " | ".join(
            f"{e.get('Subject','')}: {(e.get('TextBody') or '')[:200]}" for e in email_recs
        )
        chatter = " | ".join(chatter_map.get(cid, [])[:3])

        cases.append({
            "case_number": r.get("CaseNumber", ""),
            "subject": r.get("Subject", ""),
            "support_reason": r.get("Support_Reason__c", ""),
            "description": (r.get("Description") or "")[:500],
            "closure_notes": r.get("Case_Closure_Notes__c") or "",
            "close_code": r.get("Close_Codes__c") or "",
            "close_reason": r.get("Close_Reason__c") or "",
            "root_cause": r.get("Root_Cause_of_Inquiry__c") or "",
            "tool": r.get("Tool__c") or "",
            "department": r.get("Department__c") or "",
            "segment": r.get("Segment__c") or "",
            "resolution": (r.get("DP_Resolution__c") or "")[:500],
            "admin_notes": (r.get("Admin_Notes__c") or "")[:500],
            "comments": comments[:500],
            "emails": emails[:500],
            "chatter": chatter[:500],
            "closed_date": r.get("ClosedDate") or "",
        })

    return {"cases": cases, "total_found": len(cases)}


def search_knowledge_articles(params):
    """Search SF KnowledgeArticleVersion by keywords. Filters results for relevance."""
    keywords = params.get("keywords", "")
    support_reason = params.get("support_reason", "")
    max_results = min(int(params.get("max_results", 5)), 10)

    # Use keywords + support_reason words for broader matching
    words = [w for w in keywords.split()[:5] if len(w) > 2]
    if support_reason:
        reason_words = [w for w in support_reason.replace("-", " ").replace("/", " ").split() if len(w) > 2]
        words = list(dict.fromkeys(words + reason_words))[:8]  # dedupe, cap at 8
    like_clauses = [f"Title LIKE '%{w.replace(chr(39), '')}%'" for w in words]
    where = " OR ".join(like_clauses) if like_clauses else "Title != null"

    query = (
        f"SELECT Title, UrlName, ArticleNumber, Summary "
        f"FROM KnowledgeArticleVersion "
        f"WHERE PublishStatus = 'Online' AND Language = 'en_US' AND ({where}) "
        f"ORDER BY LastModifiedDate DESC "
        f"LIMIT {max_results}"
    )

    logger.info(json.dumps({"event": "kav_query", "query": query}))
    sf = get_sf()
    results = sf.query(query)

    # Filter: only return articles where title contains at least one keyword
    lower_words = [w.lower() for w in words]
    articles = []
    for r in results.get("records", []):
        title = r.get("Title", "")
        title_lower = title.lower()
        if any(w in title_lower for w in lower_words):
            articles.append({
                "title": title,
                "url_name": r.get("UrlName", ""),
                "article_number": r.get("ArticleNumber", ""),
                "summary": (r.get("Summary") or "")[:300],
            })

    logger.info(json.dumps({"event": "kav_results", "found": len(articles),
                            "titles": [a["title"] for a in articles]}))
    return {"articles": articles, "total_found": len(articles)}


def lambda_handler(event, context):
    """Handle Bedrock Agent action group invocations."""
    api_path = event.get("apiPath", "")
    logger.info(json.dumps({"event": "action_group_invoked", "api_path": api_path}))

    params = {}
    try:
        props = event.get("requestBody", {}).get("content", {}).get("application/json", {}).get("properties", [])
        for p in props:
            params[p["name"]] = p["value"]
    except (KeyError, TypeError):
        pass

    if api_path == "/searchSimilarCases":
        try:
            result = search_similar_cases(params)
            body = json.dumps(result)
        except Exception as e:
            logger.error(f"Action group error: {e}")
            body = json.dumps({"cases": [], "total_found": 0, "error": str(e)})
    elif api_path == "/searchKnowledgeArticles":
        try:
            result = search_knowledge_articles(params)
            body = json.dumps(result)
        except Exception as e:
            logger.error(f"KAV search error: {e}")
            body = json.dumps({"articles": [], "total_found": 0, "error": str(e)})
    else:
        body = json.dumps({"error": f"Unknown path: {api_path}"})

    return {
        "messageVersion": "1.0",
        "response": {
            "actionGroup": event.get("actionGroup", ""),
            "apiPath": api_path,
            "httpMethod": event.get("httpMethod", "POST"),
            "httpStatusCode": 200,
            "responseBody": {"application/json": {"body": body}},
        },
    }
