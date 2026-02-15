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
    """Search SF for similar closed cases by keywords and/or support reason."""
    keywords = params.get("keywords", "")
    support_reason = params.get("support_reason", "")
    tool = params.get("tool", "")
    max_results = min(int(params.get("max_results", 10)), 50)

    sf = get_sf()
    conditions = ["Status IN ('Closed', 'Closed Resolved')"]

    # Require support_reason match (primary filter) + keyword match (relevance)
    keyword_conditions = []
    for word in [w for w in keywords.split()[:5] if len(w) > 2]:
        safe = word.replace("'", "\\'")
        keyword_conditions.append(f"Subject LIKE '%{safe}%'")

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
    query = (
        f"SELECT Id, CaseNumber, Subject, Support_Reason__c, Description, "
        f"Case_Closure_Notes__c, ClosedDate, Close_Codes__c, Close_Reason__c, "
        f"Root_Cause_of_Inquiry__c, Tool__c, Department__c, Segment__c, "
        f"DP_Resolution__c, Admin_Notes__c, "
        f"(SELECT CommentBody FROM CaseComments ORDER BY CreatedDate DESC LIMIT 3), "
        f"(SELECT Subject, TextBody FROM EmailMessages ORDER BY CreatedDate DESC LIMIT 3) "
        f"FROM Case WHERE {where} "
        f"ORDER BY ClosedDate DESC NULLS LAST LIMIT {max_results}"
    )

    logger.info(json.dumps({"event": "soql_query", "query": query}))
    results = sf.query(query)
    all_records = results.get("records", [])
    logger.info(json.dumps({"event": "similar_cases_found", "count": len(all_records)}))

    logger.info(json.dumps({"event": "similar_cases_found", "count": len(all_records)}))

    # Batch-fetch Chatter (FeedItem doesn't support subqueries)
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
            for f in fr.get("records", []):
                pid = f.get("ParentId", "")
                if f.get("Body"):
                    chatter_map.setdefault(pid, []).append(f["Body"][:200])
        except Exception:
            pass

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
